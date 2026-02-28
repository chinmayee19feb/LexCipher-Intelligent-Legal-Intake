import os
import json
import re
import logging
import boto3
from botocore.exceptions import ClientError
import anthropic

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    """Robustly extract JSON from Claude's response (handles markdown fences)."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise json.JSONDecodeError("No valid JSON found in response", text, 0)

s3        = boto3.client("s3")
PDF_BUCKET = os.environ.get("PDF_BUCKET", "lexcipher-police-reports")
MODEL     = "claude-haiku-4-5"

_client = None

def _get_client():
    global _client
    if _client is None:
        # Lazy init — avoid cold-start SSM failure
        ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        try:
            resp = ssm.get_parameter(Name="/lexcipher/anthropic/api_key", WithDecryption=True)
            api_key = resp["Parameter"]["Value"]
        except Exception:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ── Fetch PDF from S3 ──────────────────────────────────────────────────────

def fetch_pdf_from_s3(s3_key: str) -> bytes | None:
    """Download a PDF from S3 and return raw bytes."""
    try:
        response = s3.get_object(Bucket=PDF_BUCKET, Key=s3_key)
        return response["Body"].read()
    except ClientError as e:
        logger.error(f"Failed to fetch PDF from S3 {s3_key}: {e}")
        return None


# ── Clio Field Extraction ──────────────────────────────────────────────────

CLIO_EXTRACTION_SYSTEM_PROMPT = """You are a legal intake specialist for Richards & Law, a personal injury law firm in New York.

Your job is to extract specific information from a police report to populate a Clio matter management system.

Extract ONLY the following fields. If a field cannot be found, use null.
Dates must be in YYYY-MM-DD format.
Dollar amounts should be numbers only (no $ sign).

You MUST respond with valid JSON only. No explanation, no markdown, no extra text.

{
  "accident_date": "<YYYY-MM-DD or null>",
  "accident_location": "<full address or intersection or null>",
  "police_report_number": "<report number or null>",
  "client_vehicle_make_model": "<year make model or null>",
  "client_vehicle_plate": "<plate number or null>",
  "client_injuries": "<injuries noted in report or null>",
  "opposing_party_name": "<full name or null>",
  "opposing_party_address": "<address or null>",
  "opposing_party_vehicle": "<year make model or null>",
  "opposing_party_plate": "<plate number or null>",
  "opposing_party_insurance_company": "<insurance company name or null>",
  "opposing_party_insurance_policy": "<policy number or null>",
  "fault_determination": "<at fault party or null>",
  "charges_filed": "<charges or null>",
  "narrative": "<2-3 sentence factual summary of the accident>",
  "sol_date": "<YYYY-MM-DD statute of limitations deadline — 3 years from accident date or null>"
}"""


def extract_for_clio(pdf_bytes: bytes) -> dict:
    """
    Extract structured data from a police report PDF specifically
    formatted for Clio custom fields.
    Returns a dict ready to be passed to the Clio API.
    """
    import base64

    try:
        pdf_base64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

        response = _get_client().messages.create(
            model=MODEL,
            max_tokens=1024,
            system=CLIO_EXTRACTION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Extract the required fields from this police report for our Clio matter system. Respond with JSON only.",
                        },
                    ],
                }
            ],
        )

        raw    = response.content[0].text.strip()
        logger.info(f"Clio extraction raw: {raw[:500]}")
        result = _extract_json(raw)
        logger.info(f"Clio extraction complete: report# {result.get('police_report_number', 'unknown')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Clio extraction JSON: {e}")
        return _fallback_extraction()
    except Exception as e:
        logger.error(f"Clio extraction error: {e}")
        return _fallback_extraction()


def extract_for_clio_from_s3(s3_key: str) -> dict:
    """
    Convenience function — fetch PDF from S3 then extract for Clio.
    Used by the Clio handler when paralegal approves an intake.
    """
    pdf_bytes = fetch_pdf_from_s3(s3_key)

    if not pdf_bytes:
        logger.error(f"Could not fetch PDF from S3: {s3_key}")
        return _fallback_extraction()

    return extract_for_clio(pdf_bytes)


def _fallback_extraction() -> dict:
    """Safe defaults when extraction fails — Clio fields will be blank."""
    return {
        "accident_date":                    None,
        "accident_location":                None,
        "police_report_number":             None,
        "client_vehicle_make_model":        None,
        "client_vehicle_plate":             None,
        "client_injuries":                  None,
        "opposing_party_name":              None,
        "opposing_party_address":           None,
        "opposing_party_vehicle":           None,
        "opposing_party_plate":             None,
        "opposing_party_insurance_company": None,
        "opposing_party_insurance_policy":  None,
        "fault_determination":              None,
        "charges_filed":                    None,
        "narrative":                        "Extraction failed — manual review required.",
        "sol_date":                         None,
    }