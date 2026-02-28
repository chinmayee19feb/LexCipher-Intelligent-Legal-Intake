import os
import json
import base64
import logging
import cgi
import io

import boto3
from botocore.exceptions import ClientError

from ai_classifier import classify_case, extract_police_report
from db import save_intake
from emailer import send_client_confirmation, send_attorney_alert

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3          = boto3.client("s3")
PDF_BUCKET  = os.environ.get("PDF_BUCKET", "lexcipher-police-reports")
MAX_PDF_SIZE = 10 * 1024 * 1024  # 10MB


# ── CORS headers ───────────────────────────────────────────────────────────
CORS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
}


def lambda_handler(event, context):
    # Handle CORS preflight
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": CORS, "body": ""}

    if event.get("httpMethod") != "POST":
        return _error(405, "Method not allowed")

    try:
        # ── Always JSON — PDF arrives as base64 string ───────────────────
        body = json.loads(event.get("body") or "{}")

        client_name    = body.get("client_name",    "").strip()
        client_email   = body.get("client_email",   "").strip()
        client_phone   = body.get("client_phone",   "").strip()
        incident_date  = body.get("incident_date",  "").strip()
        prior_attorney = bool(body.get("prior_attorney", False))
        description    = body.get("description",    "").strip()

        # Decode PDF if provided as base64
        pdf_bytes = None
        pdf_b64   = body.get("police_report_base64", "")
        if pdf_b64:
            pdf_bytes = base64.b64decode(pdf_b64)

        # ── Validate required fields ───────────────────────────────────────
        missing = [f for f, v in {
            "client_name":   client_name,
            "client_email":  client_email,
            "client_phone":  client_phone,
            "incident_date": incident_date,
            "description":   description,
        }.items() if not v]

        if missing:
            return _error(400, f"Missing required fields: {', '.join(missing)}")

        # ── Upload PDF to S3 ───────────────────────────────────────────────
        pdf_s3_key        = None
        police_report     = None
        has_police_report = False

        if pdf_bytes:
            if len(pdf_bytes) > MAX_PDF_SIZE:
                return _error(400, "PDF file exceeds 10MB limit")

            # Store in S3
            safe_name  = client_name.lower().replace(" ", "_")
            pdf_s3_key = f"police-reports/{incident_date}/{safe_name}_{context.aws_request_id}.pdf"

            try:
                s3.put_object(
                    Bucket=PDF_BUCKET,
                    Key=pdf_s3_key,
                    Body=pdf_bytes,
                    ContentType="application/pdf",
                    ServerSideEncryption="AES256",
                )
                logger.info(f"PDF uploaded to s3://{PDF_BUCKET}/{pdf_s3_key}")
                has_police_report = True
            except ClientError as e:
                logger.error(f"S3 upload failed: {e}")
                # Continue without PDF rather than failing the whole intake
                pdf_s3_key = None

            # Extract police report data from PDF
            if has_police_report:
                pdf_base64    = base64.standard_b64encode(pdf_bytes).decode("utf-8")
                police_report = extract_police_report(pdf_base64)

        # ── Classify case ──────────────────────────────────────────────────
        classification = classify_case(
            client_name=client_name,
            description=description,
            incident_date=incident_date,
            prior_attorney=prior_attorney,
        )

        # ── Save to DynamoDB ───────────────────────────────────────────────
        intake_id, portal_token = save_intake(
            client_name=client_name,
            client_email=client_email,
            client_phone=client_phone,
            incident_date=incident_date,
            prior_attorney=prior_attorney,
            description=description,
            classification=classification,
            has_police_report=has_police_report,
            pdf_s3_key=pdf_s3_key,
            police_report=police_report,
        )

        # ── Send emails ────────────────────────────────────────────────────
        send_client_confirmation(
            client_name=client_name,
            client_email=client_email,
            intake_id=intake_id,
            portal_token=portal_token,
            acknowledgment=classification.get("client_acknowledgment", ""),
            case_type=classification.get("case_type", ""),
            has_police_report=has_police_report,
        )

        send_attorney_alert(
            intake_id=intake_id,
            client_name=client_name,
            client_email=client_email,
            client_phone=client_phone,
            incident_date=incident_date,
            case_type=classification.get("case_type", ""),
            viability_score=classification.get("viability_score", 0),
            urgency=classification.get("urgency", "low"),
            sol_flag=classification.get("sol_flag", False),
            key_facts=classification.get("key_facts", []),
            recommended_action=classification.get("recommended_action", ""),
            has_police_report=has_police_report,
            prior_attorney=prior_attorney,
        )

        logger.info(f"Intake complete: {intake_id} | {classification.get('case_type')} | {classification.get('urgency')}")

        return {
            "statusCode": 200,
            "headers": CORS,
            "body": json.dumps({
                "intake_id":   intake_id,
                "case_type":   classification.get("case_type"),
                "urgency":     classification.get("urgency"),
                "message":     "Intake received successfully",
            }),
        }

    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        return _error(500, "Internal server error")


# ── Multipart parser ───────────────────────────────────────────────────────

def _parse_multipart(event: dict, content_type: str) -> tuple[dict, bytes | None]:
    """
    Parse a multipart/form-data request from API Gateway.
    Returns (fields_dict, pdf_bytes_or_None)
    """
    body = event.get("body", "")
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body)
    else:
        body = body.encode("utf-8") if isinstance(body, str) else body

    # Build a fake environ for cgi.FieldStorage
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE":   content_type,
        "CONTENT_LENGTH": str(len(body)),
    }

    fp      = io.BytesIO(body)
    storage = cgi.FieldStorage(fp=fp, environ=environ, keep_blank_values=True)

    fields    = {}
    pdf_bytes = None

    for key in storage.keys():
        item = storage[key]
        if isinstance(item, list):
            fields[key] = item[0].value
        elif hasattr(item, "filename") and item.filename:
            # This is a file upload
            if key == "police_report":
                pdf_bytes = item.file.read()
        else:
            fields[key] = item.value

    return fields, pdf_bytes


# ── Error helper ───────────────────────────────────────────────────────────

def _error(status: int, message: str) -> dict:
    return {
        "statusCode": status,
        "headers": CORS,
        "body": json.dumps({"error": message}),
    }