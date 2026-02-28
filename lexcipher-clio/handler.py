import os
import json
import logging
import boto3
import requests
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from botocore.exceptions import ClientError

from extractor import extract_for_clio_from_s3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Clio Constants (real IDs from setup) ─────────────────────────────────────
CLIO_BASE_URL  = "https://app.clio.com/api/v4"
MATTER_ID      = 1767082208       # 00001-Reyes
CONTACT_ID     = 2344505663       # Guillermo Reyes
USER_ID        = 358936313        # Andrew Richards

FIELD_IDS = {
    "Accident Date":               18803993,
    "Accident Location":           18804008,
    "Accident Description":        18804023,
    "Client Vehicle":              18804038,
    "Opposing Party Name":         18804053,
    "Opposing Party Vehicle":      18804068,
    "Police Report Number":        18804083,
    "Statute of Limitations Date": 18804098,
}

# ── Email constants ───────────────────────────────────────────────────────────
FROM_EMAIL       = "intake@richardsandlaw.com"
# ⚠️  BEFORE FINAL SUBMISSION change to:
# AUTOMATION_EMAIL = "talent.legal-engineer.hackathon.automation-email@swans.co"
AUTOMATION_EMAIL = "chinmayee.ohmaws@gmail.com"

# Seasonal booking links (February = winter)
BOOKING_LINKS = {
    "winter": "https://calendly.com/richardsandlaw/consultation-winter",
    "spring": "https://calendly.com/richardsandlaw/consultation-spring",
    "summer": "https://calendly.com/richardsandlaw/consultation-summer",
    "fall":   "https://calendly.com/richardsandlaw/consultation-fall",
}

CORS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

ssm    = boto3.client("ssm")
ses    = boto3.client("ses", region_name="us-east-1")
dynamo = boto3.resource("dynamodb")
TABLE  = dynamo.Table(os.environ.get("DYNAMODB_TABLE", "lexcipher-intakes"))


# ── Lambda Entry Point ────────────────────────────────────────────────────────

def handler(event, context):
    """
    Triggered by the dashboard when paralegal clicks Approve.

    Expected JSON body:
    {
        "intake_id":    "<uuid>",
        "verified_data": {
            "accident_date":                    "2018-12-06",
            "accident_location":                "Flatbush Avenue...",
            "client_vehicle_make_model":        "2010 Freightliner Box Truck",
            "opposing_party_name":              "Lionel Francois",
            "opposing_party_vehicle":           "2011 Ford Van",
            "police_report_number":             "MV-2018-078-002001",
            "sol_date":                         "2026-12-06",
            "opposing_party_insurance_company": "...",
            "fault_determination":              "...",
            "narrative":                        "..."
        },
        "client_name":  "Guillermo Reyes",
        "client_email": "...",
        "incident_date":"2018-12-06"
    }
    """
    method = event.get("httpMethod", "")
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS, "body": ""}

    try:
        body           = json.loads(event.get("body") or "{}")
        intake_id      = body.get("intake_id")
        verified_data  = body.get("verified_data", {})
        client_name    = body.get("client_name", "Valued Client")
        client_email   = body.get("client_email", AUTOMATION_EMAIL)
        incident_date  = body.get("incident_date", "")

        if not intake_id:
            return _error(400, "intake_id is required")

        logger.info(f"Clio sync triggered for intake_id={intake_id}")

        # ── 1. Load Clio access token from SSM ────────────────────────────────
        access_token = _get_access_token()
        headers      = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json",
        }

        # ── 2. Update Clio Matter custom fields ───────────────────────────────
        field_updates = _build_custom_field_updates(verified_data)
        matter_result = _update_matter_custom_fields(headers, field_updates)
        logger.info(f"Matter updated: {matter_result}")

        # ── 3. Update Matter status → Active ──────────────────────────────────
        _update_matter_status(headers, "Active")

        # ── 4. Create SOL calendar event ──────────────────────────────────────
        sol_date     = verified_data.get("sol_date") or _calculate_sol(incident_date)
        calendar_id  = _create_sol_calendar_event(headers, sol_date, client_name)
        logger.info(f"Calendar event created: {calendar_id}")

        # ── 5. Send personalized client email ─────────────────────────────────
        booking_link = _get_seasonal_booking_link()
        _send_retainer_email(
            client_name    = client_name,
            client_email   = client_email,
            verified_data  = verified_data,
            booking_link   = booking_link,
            sol_date       = sol_date,
        )
        logger.info(f"Retainer email sent to {client_email}")

        # ── 6. Mark intake as clio_synced in DynamoDB ─────────────────────────
        _mark_synced(intake_id, calendar_id)

        return {
            "statusCode": 200,
            "headers":    CORS,
            "body":       json.dumps({
                "success":      True,
                "matter_id":    MATTER_ID,
                "calendar_id":  calendar_id,
                "sol_date":     sol_date,
                "email_sent_to": client_email,
            }),
        }

    except Exception as e:
        logger.error(f"Clio handler error: {e}", exc_info=True)
        return _error(500, str(e))


# ── Clio API Helpers ──────────────────────────────────────────────────────────

def _get_access_token() -> str:
    """Fetch Clio access token from SSM Parameter Store."""
    try:
        resp = ssm.get_parameter(
            Name            = "/lexcipher/clio/access_token",
            WithDecryption  = True,
        )
        return resp["Parameter"]["Value"]
    except ClientError:
        # Fallback to env var for local testing
        token = os.environ.get("CLIO_ACCESS_TOKEN", "")
        if not token:
            raise RuntimeError("CLIO_ACCESS_TOKEN not found in SSM or environment")
        return token


def _build_custom_field_updates(verified_data: dict) -> list:
    """
    Map verified_data keys → Clio custom_field_values format.
    Returns list ready for the PATCH /matters payload.
    """
    mapping = {
        "accident_date":             ("Accident Date",               "date"),
        "accident_location":         ("Accident Location",           "text"),
        "narrative":                 ("Accident Description",        "text"),
        "client_vehicle_make_model": ("Client Vehicle",              "text"),
        "opposing_party_name":       ("Opposing Party Name",         "text"),
        "opposing_party_vehicle":    ("Opposing Party Vehicle",      "text"),
        "police_report_number":      ("Police Report Number",        "text"),
        "sol_date":                  ("Statute of Limitations Date", "date"),
    }

    updates = []
    for data_key, (field_name, field_type) in mapping.items():
        value = verified_data.get(data_key)
        if value is None:
            continue

        field_id = FIELD_IDS.get(field_name)
        if not field_id:
            logger.warning(f"No field_id found for {field_name}")
            continue

        updates.append({
            "id":    field_id,
            "value": value,    # dates should already be "YYYY-MM-DD"
        })

    return updates


def _update_matter_custom_fields(headers: dict, field_updates: list) -> dict:
    """PATCH the matter with new custom field values."""
    if not field_updates:
        logger.warning("No field updates to apply")
        return {}

    payload = {
        "data": {
            "custom_field_values": field_updates
        }
    }

    r = requests.patch(
        f"{CLIO_BASE_URL}/matters/{MATTER_ID}",
        headers = headers,
        json    = payload,
    )
    r.raise_for_status()
    return r.json()


def _update_matter_status(headers: dict, status: str = "Active") -> None:
    """Set matter status to Active once case is accepted."""
    payload = {"data": {"status": status}}
    r = requests.patch(
        f"{CLIO_BASE_URL}/matters/{MATTER_ID}",
        headers = headers,
        json    = payload,
    )
    r.raise_for_status()
    logger.info(f"Matter status → {status}")


def _create_sol_calendar_event(headers: dict, sol_date: str, client_name: str) -> int | None:
    """
    Create a calendar event in Clio for the Statute of Limitations deadline.
    Returns the calendar entry id or None if it fails.
    """
    if not sol_date:
        logger.warning("No SOL date — skipping calendar event")
        return None

    # Build ISO datetime strings for the event (all-day = start == end)
    start_dt = f"{sol_date}T09:00:00Z"
    end_dt   = f"{sol_date}T10:00:00Z"

    payload = {
        "data": {
            "summary":     f"⚠️ SOL DEADLINE — {client_name} (Reyes v Francois)",
            "description": (
                f"STATUTE OF LIMITATIONS DEADLINE\n"
                f"Client: {client_name}\n"
                f"Matter: Reyes v Francois — Personal Injury\n"
                f"Matter ID: {MATTER_ID}\n\n"
                f"The statute of limitations expires on {sol_date}.\n"
                f"A lawsuit MUST be filed before this date or the right to sue is permanently lost."
            ),
            "start_at":    start_dt,
            "end_at":      end_dt,
            "all_day":     False,
            "matter":      {"id": MATTER_ID},
        }
    }

    try:
        r = requests.post(
            f"{CLIO_BASE_URL}/calendar_entries",
            headers = headers,
            json    = payload,
        )
        r.raise_for_status()
        result = r.json()
        return result.get("data", {}).get("id")
    except Exception as e:
        logger.error(f"Calendar event creation failed: {e}")
        return None


# ── Email ─────────────────────────────────────────────────────────────────────

def _get_seasonal_booking_link() -> str:
    """Return the right booking link based on current month."""
    month = datetime.now().month
    if month in (12, 1, 2):
        return BOOKING_LINKS["winter"]
    elif month in (3, 4, 5):
        return BOOKING_LINKS["spring"]
    elif month in (6, 7, 8):
        return BOOKING_LINKS["summer"]
    else:
        return BOOKING_LINKS["fall"]


def _calculate_sol(incident_date: str, years: int = 8) -> str | None:
    """Calculate SOL date = incident_date + years. Returns YYYY-MM-DD or None."""
    try:
        dt = datetime.strptime(incident_date, "%Y-%m-%d")
        sol = dt + relativedelta(years=years)
        return sol.strftime("%Y-%m-%d")
    except Exception:
        return None


def _send_retainer_email(
    client_name:   str,
    client_email:  str,
    verified_data: dict,
    booking_link:  str,
    sol_date:      str | None,
) -> None:
    """Send warm personalized email to client confirming case acceptance."""

    first_name     = client_name.split()[0] if client_name else "Guillermo"
    accident_date  = verified_data.get("accident_date", "")
    accident_loc   = verified_data.get("accident_location", "")
    opposing_party = verified_data.get("opposing_party_name", "the other driver")
    report_no      = verified_data.get("police_report_number", "")
    narrative      = verified_data.get("narrative", "")
    sol_display    = sol_date or "Date to be confirmed"
    month_name     = datetime.now().strftime("%B")

    subject = f"Richards & Law Has Accepted Your Case — Next Steps Inside"

    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: Georgia, serif; background: #f5f1eb; margin: 0; padding: 0; }}
  .wrapper {{ max-width: 600px; margin: 32px auto; background: #fff; border-radius: 4px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,.12); }}
  .header {{ background: #1B3A6B; padding: 32px 40px; text-align: center; }}
  .seal {{ width: 56px; height: 56px; border-radius: 50%; border: 2px solid #C9A84C; display: inline-flex; align-items: center; justify-content: center; margin-bottom: 12px; }}
  .firm-name {{ color: #fff; font-size: 22px; font-family: Georgia, serif; letter-spacing: .04em; margin: 0; }}
  .tagline {{ color: #C9A84C; font-size: 11px; letter-spacing: .12em; margin: 4px 0 0; text-transform: uppercase; }}
  .body {{ padding: 40px; color: #333; line-height: 1.7; font-size: 15px; }}
  h2 {{ color: #1B3A6B; font-size: 18px; margin-top: 0; }}
  .case-box {{ background: #f0f4fa; border-left: 4px solid #1B3A6B; padding: 16px 20px; border-radius: 0 4px 4px 0; margin: 24px 0; font-size: 13px; }}
  .case-box table {{ width: 100%; border-collapse: collapse; }}
  .case-box td {{ padding: 4px 0; vertical-align: top; }}
  .case-box td:first-child {{ color: #666; width: 42%; font-weight: bold; }}
  .sol-box {{ background: #fff8e6; border: 1px solid #f0c040; border-radius: 4px; padding: 14px 20px; margin: 20px 0; font-size: 13px; }}
  .cta {{ text-align: center; margin: 32px 0; }}
  .cta a {{ background: #1B3A6B; color: #fff !important; text-decoration: none; padding: 14px 32px; border-radius: 3px; font-size: 15px; display: inline-block; }}
  .footer {{ background: #f5f1eb; padding: 20px 40px; font-size: 11px; color: #888; text-align: center; border-top: 1px solid #e0d9d0; }}
  .gold {{ color: #C9A84C; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <div style="color:#fff; font-size:26px; font-weight:bold; font-family:Georgia,serif;">
      R<span class="gold">&amp;</span>L
    </div>
    <p class="firm-name">Richards <span class="gold">&amp;</span> Law</p>
    <p class="tagline">Personal Injury Attorneys &middot; New York</p>
  </div>
  <div class="body">
    <h2>Dear {first_name},</h2>
    <p>
      We have carefully reviewed your case and I am pleased to inform you that
      <strong>Richards &amp; Law has accepted your representation</strong>.
    </p>
    <p>
      Our team has reviewed Police Report <strong>{report_no}</strong> and the
      circumstances of your accident on {accident_date}. Based on our initial
      assessment, we believe you have strong grounds to pursue compensation.
    </p>

    <div class="case-box">
      <table>
        <tr><td>Matter:</td><td><strong>Reyes v Francois</strong></td></tr>
        <tr><td>Incident Date:</td><td>{accident_date}</td></tr>
        <tr><td>Location:</td><td>{accident_loc}</td></tr>
        <tr><td>Opposing Party:</td><td>{opposing_party}</td></tr>
        <tr><td>Police Report:</td><td>{report_no}</td></tr>
        {"<tr><td>Summary:</td><td>" + narrative + "</td></tr>" if narrative else ""}
      </table>
    </div>

    <div class="sol-box">
      ⚠️ <strong>Important Deadline</strong> — Your Statute of Limitations expires on
      <strong>{sol_display}</strong>. We have added this to our calendar and will ensure
      all filings are made well in advance.
    </div>

    <p>
      Your Retainer Agreement has been prepared and our team will send it
      to you shortly for signature. This agreement formalizes our representation
      on a <strong>contingency fee basis</strong> — you pay nothing upfront and
      we only get paid when you win.
    </p>

    <p>Please book your initial consultation below so we can review the full
    details of your case with you in person:</p>

    <div class="cta">
      <a href="{booking_link}">Book Your {month_name} Consultation &rarr;</a>
    </div>

    <p>
      If you have any questions before your appointment, please do not hesitate
      to contact our office directly. We are here for you every step of the way.
    </p>

    <p>Warm regards,</p>
    <p>
      <strong>Andrew Richards</strong><br>
      <span style="color:#666;">Managing Partner</span><br>
      Richards &amp; Law — Personal Injury Attorneys<br>
      <span class="gold">New York, NY</span>
    </p>
  </div>
  <div class="footer">
    &copy; 2026 Richards &amp; Law. All rights reserved.<br>
    This communication is attorney-client privileged and confidential.
  </div>
</div>
</body>
</html>"""

    text_body = (
        f"Dear {first_name},\n\n"
        f"Richards & Law has accepted your case (Reyes v Francois).\n\n"
        f"Incident: {accident_date} at {accident_loc}\n"
        f"Opposing Party: {opposing_party}\n"
        f"Police Report: {report_no}\n\n"
        f"IMPORTANT: Your Statute of Limitations expires {sol_display}.\n\n"
        f"Book your consultation: {booking_link}\n\n"
        f"Andrew Richards\nRichards & Law"
    )

    ses.send_email(
        Source      = FROM_EMAIL,
        Destination = {"ToAddresses": [client_email]},
        Message     = {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body":    {
                "Html": {"Data": html_body,  "Charset": "UTF-8"},
                "Text": {"Data": text_body,  "Charset": "UTF-8"},
            },
        },
    )


# ── DynamoDB ──────────────────────────────────────────────────────────────────

def _mark_synced(intake_id: str, calendar_id: int | None) -> None:
    """Mark the DynamoDB intake record as synced to Clio."""
    update_expr = "SET clio_synced = :s, clio_matter_id = :m, clio_calendar_id = :c, updated_at = :u"
    TABLE.update_item(
        Key       = {"intake_id": intake_id},
        UpdateExpression = update_expr,
        ExpressionAttributeValues = {
            ":s": True,
            ":m": str(MATTER_ID),
            ":c": str(calendar_id) if calendar_id else "N/A",
            ":u": datetime.utcnow().isoformat(),
        },
    )


# ── CORS error helper ─────────────────────────────────────────────────────────

def _error(status: int, message: str) -> dict:
    return {
        "statusCode": status,
        "headers":    CORS,
        "body":       json.dumps({"error": message}),
    }