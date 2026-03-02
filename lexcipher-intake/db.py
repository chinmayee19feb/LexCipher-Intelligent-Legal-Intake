import os
import uuid
import logging
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ── DynamoDB setup ─────────────────────────────────────────────────────────
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "lexcipher-intakes")
dynamodb   = boto3.resource("dynamodb")
table      = dynamodb.Table(TABLE_NAME)


# ── Save new intake ────────────────────────────────────────────────────────

def save_intake(
    client_name:    str,
    client_email:   str,
    client_phone:   str,
    incident_date:  str,
    prior_attorney: bool,
    description:    str,
    classification: dict,
    has_police_report: bool         = False,
    pdf_s3_key:        str | None   = None,
    police_report:     dict | None  = None,
) -> str:
    """
    Save a new intake record to DynamoDB.
    Returns the generated intake_id.
    """
    intake_id    = str(uuid.uuid4())
    portal_token = str(uuid.uuid4())
    now          = datetime.now(timezone.utc).isoformat()

    item = {
        # Keys
        "intake_id":    intake_id,
        "portal_token": portal_token,

        # Client info
        "client_name":    client_name,
        "client_email":   client_email,
        "client_phone":   client_phone,
        "incident_date":  incident_date,
        "prior_attorney": prior_attorney,
        "description":    description,

        # AI classification
        "case_type":             classification.get("case_type", "Out of Scope"),
        "viability_score":       classification.get("viability_score", 0),
        "urgency":               classification.get("urgency", "low"),
        "sol_flag":              classification.get("sol_flag", False),
        "key_facts":             classification.get("key_facts", []),
        "recommended_action":    classification.get("recommended_action", ""),
        "client_acknowledgment": classification.get("client_acknowledgment", ""),

        # Police report
        "has_police_report": has_police_report,
        "pdf_s3_key":        pdf_s3_key,

        # Status & timestamps
        "status":     "new",
        "created_at": now,
        "updated_at": now,
    }

    # Flatten police report fields into the item if present
    if has_police_report and police_report:
        item["accident_date"]             = police_report.get("accident_date")
        item["accident_time"]             = police_report.get("accident_time")
        item["accident_location"]         = police_report.get("accident_location")
        item["police_report_number"]      = police_report.get("police_report_number")
        item["reporting_officer"]         = police_report.get("reporting_officer")
        item["client_vehicle"]            = police_report.get("client_vehicle")
        item["client_vehicle_plate"]      = police_report.get("client_vehicle_plate")
        item["client_injuries_noted"]     = police_report.get("client_injuries_noted")
        item["opposing_party_name"]       = police_report.get("opposing_party_name")
        item["opposing_party_vehicle"]    = police_report.get("opposing_party_vehicle")
        item["opposing_party_plate"]      = police_report.get("opposing_party_plate")
        item["opposing_party_insurance"]  = police_report.get("opposing_party_insurance")
        item["fault_determination"]       = police_report.get("fault_determination")
        item["witnesses"]                 = police_report.get("witnesses", [])
        item["charges_filed"]             = police_report.get("charges_filed")
        item["narrative_summary"]         = police_report.get("narrative_summary") or police_report.get("narrative")
        item["sol_date"]                  = police_report.get("sol_date")
        item["client_pronoun"]            = police_report.get("client_pronoun")
        item["client_gender"]             = police_report.get("client_gender")
        item["client_dob"]                = police_report.get("client_dob")
        item["client_age"]                = police_report.get("client_age")
        item["client_licensed"]           = police_report.get("client_licensed")
        item["client_license_id"]         = police_report.get("client_license_id")
        item["client_insurance_code"]     = police_report.get("client_insurance_code")
        item["number_injured"]            = police_report.get("number_injured")
        item["opposing_party_dob"]        = police_report.get("opposing_party_dob")
        item["opposing_party_age"]        = police_report.get("opposing_party_age")
        item["opposing_party_licensed"]   = police_report.get("opposing_party_licensed")
        item["opposing_party_license_id"] = police_report.get("opposing_party_license_id")
        item["opposing_insurance_code"]   = police_report.get("opposing_insurance_code")

    # Remove None values — DynamoDB doesn't accept nulls
    item = {k: v for k, v in item.items() if v is not None}

    try:
        table.put_item(Item=item)
        logger.info(f"Saved intake {intake_id} for {client_name}")
        return intake_id, portal_token
    except ClientError as e:
        logger.error(f"DynamoDB save failed: {e}")
        raise


# ── Get intake by ID ───────────────────────────────────────────────────────

def get_intake(intake_id: str) -> dict | None:
    """Fetch a single intake record by intake_id."""
    try:
        response = table.get_item(Key={"intake_id": intake_id})
        return response.get("Item")
    except ClientError as e:
        logger.error(f"DynamoDB get failed: {e}")
        return None


# ── Get intake by portal token ─────────────────────────────────────────────

def get_intake_by_token(portal_token: str) -> dict | None:
    """Fetch intake record using the client's magic link token."""
    try:
        response = table.query(
            IndexName="portal_token-index",
            KeyConditionExpression=Key("portal_token").eq(portal_token),
        )
        items = response.get("Items", [])
        return items[0] if items else None
    except ClientError as e:
        logger.error(f"DynamoDB token query failed: {e}")
        return None


# ── Update intake status ───────────────────────────────────────────────────

def update_status(intake_id: str, status: str, notes: str = None) -> bool:
    """
    Update the status of an intake.
    Valid statuses: pending, active, declined, closed
    """
    now = datetime.now(timezone.utc).isoformat()

    update_expr  = "SET #s = :status, updated_at = :updated_at"
    expr_names   = {"#s": "status"}
    expr_values  = {":status": status, ":updated_at": now}

    if notes:
        update_expr += ", attorney_notes = :notes"
        expr_values[":notes"] = notes

    try:
        table.update_item(
            Key={"intake_id": intake_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )
        logger.info(f"Updated intake {intake_id} → {status}")
        return True
    except ClientError as e:
        logger.error(f"DynamoDB update failed: {e}")
        return False


# ── Mark Clio sync complete ────────────────────────────────────────────────

def mark_clio_synced(intake_id: str, clio_matter_id: str, clio_contact_id: str) -> bool:
    """Record that this intake has been synced to Clio."""
    now = datetime.now(timezone.utc).isoformat()

    try:
        table.update_item(
            Key={"intake_id": intake_id},
            UpdateExpression=(
                "SET clio_synced = :synced, "
                "clio_matter_id = :matter, "
                "clio_contact_id = :contact, "
                "clio_synced_at = :now, "
                "updated_at = :now"
            ),
            ExpressionAttributeValues={
                ":synced":  True,
                ":matter":  clio_matter_id,
                ":contact": clio_contact_id,
                ":now":     now,
            },
        )
        logger.info(f"Clio sync recorded for intake {intake_id}")
        return True
    except ClientError as e:
        logger.error(f"DynamoDB clio sync update failed: {e}")
        return False


# ── Get recent intakes for dashboard ──────────────────────────────────────

def get_recent_intakes(limit: int = 50) -> list:
    """Scan for recent intakes — used by the dashboard."""
    try:
        response = table.scan(Limit=limit)
        items = response.get("Items", [])
        # Sort by created_at descending
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return items
    except ClientError as e:
        logger.error(f"DynamoDB scan failed: {e}")
        return []