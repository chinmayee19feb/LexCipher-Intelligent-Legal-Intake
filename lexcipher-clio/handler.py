import os
import io
import json
import logging
import boto3
import requests
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

from extractor import extract_for_clio_from_s3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ── Clio Constants ────────────────────────────────────────────────────────
CLIO_BASE_URL  = "https://app.clio.com/api/v4"
USER_ID        = 358936313        # Andrew Richards (responsible attorney)

FIELD_IDS = {
    "Accident Date":               18803993,
    "Accident Location":           18804008,
    "Accident Description":        18804023,
    "Client Vehicle":              18804038,
    "Opposing Party Name":         18804053,
    "Opposing Party Vehicle":      18804068,
    "Police Report Number":        18804083,
    "Statute of Limitations Date": 18804098,
    "Client Vehicle Plate":        18807653,
    "Client Pronoun":              18807668,
    "Number Injured":              18807683,
}

# ── Email constants ───────────────────────────────────────────────────────────
FROM_EMAIL       = os.environ.get("FROM_EMAIL", "ch.pradhan606@gmail.com")
AUTOMATION_EMAIL = os.environ.get("ATTORNEY_EMAIL", "lexcipher.submission@gmail.com")

# Seasonal booking links (per Andrew's request)
# March-August = in-office (summer-spring), September-February = virtual (winter-autumn)
BOOKING_LINKS = {
    "in_office": "https://calendly.com/swans-santiago-p/summer-spring",
    "virtual":   "https://calendly.com/swans-santiago-p/winter-autumn",
}

# Clio Document IDs
DOCUMENT_TEMPLATE_ID = 9157148

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
        client_email   = body.get("client_email") or AUTOMATION_EMAIL
        incident_date  = body.get("incident_date", "")
        logger.info(f"Resolved client_email: {client_email}")

        if not intake_id:
            return _error(400, "intake_id is required")

        logger.info(f"Clio sync triggered for intake_id={intake_id}")

        # ── 1. Clio API sync (non-fatal — don't block email/DB on Clio errors) ──
        calendar_id = None
        clio_success = False
        matter_id = None
        opposing_name = verified_data.get("opposing_party_name", "Unknown")
        try:
            access_token = _get_access_token()
            headers      = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type":  "application/json",
            }

            # Create Contact in Clio
            contact_id = _create_contact(headers, client_name, client_email)
            logger.info(f"Contact created: {contact_id}")

            # Create Matter in Clio
            matter_desc = f"{client_name.split()[-1]} v {opposing_name.split(',')[0].strip()} - Personal Injury"
            matter_id = _create_matter(headers, contact_id, matter_desc)
            logger.info(f"Matter created: {matter_id}")

            # Update Clio Matter custom fields
            field_updates = _build_custom_field_updates(verified_data)
            matter_result = _update_matter_custom_fields(headers, field_updates, matter_id)
            logger.info(f"Matter updated: {matter_result}")

            # Update Matter status to Open
            _update_matter_status(headers, "Open", matter_id)

            # Create SOL calendar event
            sol_date     = verified_data.get("sol_date") or _calculate_sol(incident_date)
            calendar_id  = _create_sol_calendar_event(headers, sol_date, client_name, matter_id, matter_desc)
            logger.info(f"Calendar event created: {calendar_id}")
            clio_success = True

        except Exception as clio_err:
            logger.warning(f"Clio API sync failed (non-fatal): {clio_err}")
            sol_date = verified_data.get("sol_date") or _calculate_sol(incident_date)

        # ── 2. Generate Retainer Agreement PDF ─────────────────────────────────
        retainer_pdf = None
        try:
            retainer_pdf = _generate_retainer_pdf(
                client_name   = client_name,
                verified_data = verified_data,
                sol_date      = sol_date,
            )
            logger.info("Retainer PDF generated")
        except Exception as pdf_err:
            logger.error(f"Retainer PDF generation failed: {pdf_err}")

        # ── 3. Upload retainer to Clio Matter Documents ──────────────────────
        clio_doc_id = None
        if retainer_pdf and clio_success and matter_id:
            try:
                clio_doc_id = _upload_document_to_clio(
                    headers   = headers,
                    pdf_bytes = retainer_pdf,
                    filename  = f"Retainer_Agreement_{client_name.replace(' ', '_')}",
                    matter_id = matter_id,
                )
                logger.info(f"Retainer uploaded to Clio: doc_id={clio_doc_id}")
            except Exception as upload_err:
                logger.error(f"Clio document upload failed: {upload_err}")

        # ── 4. Send personalized client email with retainer attached ─────────
        try:
            booking_link = _get_seasonal_booking_link()
            _send_retainer_email(
                client_name    = client_name,
                client_email   = client_email,
                verified_data  = verified_data,
                booking_link   = booking_link,
                sol_date       = sol_date,
                retainer_pdf   = retainer_pdf,
            )
            logger.info(f"Retainer email sent to {client_email}")
        except Exception as email_err:
            logger.error(f"Retainer email failed: {email_err}")

        # ── 5. Mark intake as synced in DynamoDB (always runs) ────────────────
        _mark_synced(intake_id, calendar_id, matter_id)

        return {
            "statusCode": 200,
            "headers":    CORS,
            "body":       json.dumps({
                "success":      True,
                "matter_id":    matter_id,
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


def _create_contact(headers: dict, client_name: str, client_email: str) -> int:
    """Create a new Contact in Clio for the client. Returns contact_id."""
    name_parts = client_name.strip().split()
    first_name = name_parts[0] if name_parts else client_name
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    payload = {
        "data": {
            "first_name": first_name,
            "last_name": last_name,
            "type": "Person",
        }
    }

    # Add email if provided
    if client_email:
        payload["data"]["email_addresses"] = [
            {"name": "Work", "address": client_email, "default_email": True}
        ]

    r = requests.post(
        f"{CLIO_BASE_URL}/contacts",
        headers=headers,
        json=payload,
    )
    r.raise_for_status()
    contact_id = r.json()["data"]["id"]
    logger.info(f"Created Clio contact: {contact_id} ({client_name})")
    return contact_id


def _create_matter(headers: dict, contact_id: int, description: str) -> int:
    """Create a new Matter in Clio linked to the contact. Returns matter_id."""
    payload = {
        "data": {
            "client": {"id": contact_id},
            "description": description,
            "status": "Pending",
            "responsible_attorney": {"id": USER_ID},
        }
    }

    r = requests.post(
        f"{CLIO_BASE_URL}/matters",
        headers=headers,
        json=payload,
    )
    r.raise_for_status()
    matter_id = r.json()["data"]["id"]
    logger.info(f"Created Clio matter: {matter_id} ({description})")
    return matter_id


def _build_custom_field_updates(verified_data: dict) -> list:
    """
    Map verified_data keys → Clio custom_field_values format.
    Returns list ready for the PATCH /matters payload.
    """
    mapping = {
        "accident_date":                    ("Accident Date",               "date"),
        "accident_location":                ("Accident Location",           "text"),
        "narrative":                        ("Accident Description",        "text"),
        "client_vehicle_make_model":        ("Client Vehicle",              "text"),
        "opposing_party_name":              ("Opposing Party Name",         "text"),
        "opposing_party_vehicle":           ("Opposing Party Vehicle",      "text"),
        "police_report_number":             ("Police Report Number",        "text"),
        "sol_date":                         ("Statute of Limitations Date", "date"),
        "client_vehicle_plate":             ("Client Vehicle Plate",        "text"),
        "client_pronoun":                   ("Client Pronoun",              "text"),
        "number_injured":                   ("Number Injured",              "text"),
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
            "custom_field": {"id": field_id},
            "value": value,
        })

    return updates


def _update_matter_custom_fields(headers: dict, field_updates: list, matter_id: int) -> dict:
    """PATCH the matter with new custom field values.
    Must first fetch existing custom_field_value IDs from the matter,
    then use those IDs (not custom_field IDs) in the update payload."""
    if not field_updates:
        logger.warning("No field updates to apply")
        return {}

    # Step 1: Fetch existing custom_field_values to get their IDs
    r = requests.get(
        f"{CLIO_BASE_URL}/matters/{matter_id}",
        headers=headers,
        params={"fields": "id,custom_field_values{id,custom_field}"},
    )
    r.raise_for_status()
    existing = r.json().get("data", {}).get("custom_field_values", [])

    # Build map: custom_field.id -> custom_field_value.id
    cf_id_to_value_id = {}
    for cfv in existing:
        cf = cfv.get("custom_field", {})
        cf_id_to_value_id[cf.get("id")] = cfv.get("id")

    # Step 2: Build update payload using value IDs
    updates = []
    for update in field_updates:
        cf_id = update["custom_field"]["id"]
        value_id = cf_id_to_value_id.get(cf_id)
        if value_id:
            updates.append({
                "id": value_id,
                "value": update["value"],
            })
        else:
            # New field, no existing value — use custom_field format
            updates.append(update)

    payload = {
        "data": {
            "custom_field_values": updates
        }
    }

    r = requests.patch(
        f"{CLIO_BASE_URL}/matters/{matter_id}",
        headers=headers,
        json=payload,
    )
    r.raise_for_status()
    return r.json()


def _update_matter_status(headers: dict, status: str = "Open", matter_id: int = None) -> None:
    """Set matter status to Active once case is accepted."""
    payload = {"data": {"status": status}}
    r = requests.patch(
        f"{CLIO_BASE_URL}/matters/{matter_id}",
        headers = headers,
        json    = payload,
    )
    r.raise_for_status()
    logger.info(f"Matter status → {status}")


def _create_sol_calendar_event(headers: dict, sol_date: str, client_name: str, matter_id: int = None, matter_desc: str = "") -> int | None:
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
            "summary":     f"⚠️ SOL DEADLINE — {client_name} ({matter_desc or 'Personal Injury'})",
            "description": (
                f"STATUTE OF LIMITATIONS DEADLINE\n"
                f"Client: {client_name}\n"
                f"Matter: {matter_desc or 'Personal Injury'}\n"
                f"Matter ID: {matter_id}\n\n"
                f"The statute of limitations expires on {sol_date}.\n"
                f"A lawsuit MUST be filed before this date or the right to sue is permanently lost."
            ),
            "start_at":    start_dt,
            "end_at":      end_dt,
            "all_day":     False,
        }
    }

    # Link to matter if available
    if matter_id:
        payload["data"]["matter"] = {"id": matter_id}

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


# ── Retainer PDF Generation ───────────────────────────────────────────────

def _generate_retainer_pdf(client_name: str, verified_data: dict, sol_date: str | None) -> bytes:
    """Generate a professional retainer agreement PDF with all case data filled in."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            topMargin=0.8*inch, bottomMargin=0.8*inch,
                            leftMargin=1*inch, rightMargin=1*inch)

    navy = HexColor("#1B3A6B")
    gold = HexColor("#C9A84C")
    dark = HexColor("#222222")

    styles = getSampleStyleSheet()
    s_title = ParagraphStyle("FirmTitle", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=20, textColor=navy,
        alignment=TA_CENTER, spaceAfter=4)
    s_subtitle = ParagraphStyle("DocTitle", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=13, textColor=dark,
        alignment=TA_CENTER, spaceBefore=12, spaceAfter=16)
    s_heading = ParagraphStyle("SectionHead", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=11, textColor=navy,
        spaceBefore=16, spaceAfter=8, underline=True, alignment=TA_CENTER)
    s_body = ParagraphStyle("Body", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, textColor=dark,
        leading=15, alignment=TA_JUSTIFY, spaceAfter=8)
    s_bold_body = ParagraphStyle("BoldBody", parent=s_body,
        fontName="Helvetica-Bold")
    s_sig = ParagraphStyle("Sig", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, textColor=dark,
        spaceBefore=4, spaceAfter=4, alignment=TA_LEFT)

    # Extract data
    accident_date    = verified_data.get("accident_date", "___________")
    accident_loc     = verified_data.get("accident_location", "___________")
    accident_desc    = verified_data.get("narrative", "")
    client_vehicle   = verified_data.get("client_vehicle_make_model", "___________")
    opposing_name    = verified_data.get("opposing_party_name", "___________")
    opposing_vehicle = verified_data.get("opposing_party_vehicle", "___________")
    report_no        = verified_data.get("police_report_number", "___________")
    plate            = verified_data.get("client_vehicle_plate", "___________")
    pronoun          = verified_data.get("client_pronoun", "his/her")
    num_injured      = verified_data.get("number_injured", "0")
    sol_display      = sol_date or "To be determined"

    try:
        injured_count = int(num_injured)
    except (ValueError, TypeError):
        injured_count = 0

    story = []

    # Header
    story.append(Paragraph("RICHARDS &amp; LAW", s_title))
    story.append(HRFlowable(width="100%", thickness=2, color=gold, spaceAfter=8))
    story.append(Paragraph("CONTRACT FOR EMPLOYMENT OF ATTORNEYS", s_subtitle))

    # Intro
    story.append(Paragraph(
        f'This Retainer Agreement (&ldquo;Agreement&rdquo;) is entered into between '
        f'<b>{client_name}</b> (&ldquo;Client&rdquo;) and <b>Richards &amp; Law</b> '
        f'(&ldquo;Attorney&rdquo;), for the purpose of providing legal representation '
        f'related to the damages sustained in an incident that occurred on '
        f'<b>{accident_date}</b>. By executing this Agreement, Client employs Attorney '
        f'to investigate, pursue, negotiate, and, if necessary, litigate claims for '
        f'damages against <b>{opposing_name}</b> who may be responsible for such damages '
        f'suffered by Client as a result of {pronoun} accident.', s_body))

    story.append(Paragraph(
        f'Representation under this Agreement is expressly limited to the matter '
        f'described herein (&ldquo;the Claim&rdquo;) and does not extend to any other '
        f'legal issues unless separately agreed to in writing by both Client and Attorney. '
        f'Attorney does not provide tax, accounting, or financial advisory services, and '
        f'any such issues are outside the scope of this representation. Client is encouraged '
        f'to consult separate professionals for such matters, as those responsibilities '
        f'remain {pronoun} own.', s_body))

    # Scope
    story.append(Paragraph("Scope of Representation", s_heading))
    story.append(Paragraph(
        f'Attorney shall undertake all reasonable and necessary legal efforts to diligently '
        f'protect and advance Client&rsquo;s interests in the Claim, extending to both '
        f'settlement negotiations and litigation proceedings where appropriate. Client agrees '
        f'to cooperate fully by providing truthful information, timely responses, and all '
        f'relevant documents or records as requested. Client acknowledges that {pronoun} '
        f'cooperation is essential to the effective handling of the Claim.', s_body))

    # Accident Details
    story.append(Paragraph("Accident Details &amp; Insurance", s_heading))
    story.append(Paragraph(
        f'The incident giving rise to this Claim occurred at <b>{accident_loc}</b>. '
        f'At the time of the accident, Client was operating or occupying a vehicle bearing '
        f'registration plate number <b>{plate}</b>. The circumstances surrounding the '
        f'incident, including the actions of the involved parties and any contributing factors, '
        f'will be further investigated by Attorney as part of the representation under this '
        f'Agreement.', s_body))

    story.append(Paragraph(
        f'Attorney is authorized to investigate the liability aspects of the incident, '
        f'including the collection of police reports, witness statements, and property damage '
        f'appraisals to determine the full extent of recoverable damages. Client understands '
        f'that preserving evidence and providing truthful disclosures regarding the events '
        f'leading to the loss are material obligations under this Agreement. This investigation '
        f'will serve as the basis for identifying all applicable insurance coverage and '
        f'responsible parties.', s_body))

    # Conditional paragraph: injured > 0 or = 0
    if injured_count > 0:
        story.append(Paragraph(
            f'Additionally, since the motor vehicle accident involved an injured person, '
            f'Attorney will also investigate potential bodily injury claims and review relevant '
            f'medical records to substantiate non-economic damages.', s_body))
    else:
        story.append(Paragraph(
            f'However, since the motor vehicle accident involved no reported injured people, '
            f'the scope of this engagement is strictly limited to the recovery of property '
            f'damage and loss of use.', s_body))

    # Litigation Expenses
    story.append(Paragraph("Litigation Expenses", s_heading))
    story.append(Paragraph(
        f'Attorney will advance all reasonable costs and expenses necessary for the proper '
        f'handling of the Claim (&ldquo;Litigation Expenses&rdquo;). Such expenses may include, '
        f'but are not limited to, court filing fees, deposition costs, expert witness fees, '
        f'medical record retrieval, travel expenses, investigative services, and administrative '
        f'charges associated with case management.', s_body))
    story.append(Paragraph(
        f'These Litigation Expenses will be reimbursed to Attorney from Client&rsquo;s share '
        f'of the recovery in addition to the contingency fee. Client understands that these '
        f'expenses are separate from medical bills, liens, or other financial obligations for '
        f'which {pronoun} may remain personally responsible.', s_body))

    # Liens
    story.append(Paragraph("Liens, Subrogation, and Other Obligations", s_heading))
    story.append(Paragraph(
        f'Client understands that certain parties, such as healthcare providers, insurers, or '
        f'government agencies (including Medicare or Medicaid), may have a legal right to '
        f'reimbursement for payments made on Client&rsquo;s behalf. These are commonly referred '
        f'to as liens or subrogation claims, and may affect the final amount received by Client '
        f'from {pronoun} settlement or judgment.', s_body))
    story.append(Paragraph(
        f'Client hereby authorizes Attorney to negotiate, settle, and satisfy such claims from '
        f'the proceeds of any recovery. Attorney may engage specialized lien resolution services '
        f'or other professionals to assist in this process, and the cost of such services shall '
        f'be treated as a Litigation Expense.', s_body))

    # SOL
    story.append(Paragraph("Statute of Limitations", s_heading))
    story.append(Paragraph(
        f'Attorney will monitor and calculate the deadline for filing the Claim in accordance '
        f'with applicable law. Based on current information, the statute of limitations for this '
        f'matter is <b><font color="#C62828">{sol_display}</font></b>. Client acknowledges the '
        f'importance of timely cooperation in providing documents, records, and information '
        f'necessary for Attorney to meet all legal deadlines.', s_body))

    # Termination
    story.append(Paragraph("Termination of Representation", s_heading))
    story.append(Paragraph(
        f'Either party may terminate this Agreement upon reasonable written notice. If Client '
        f'terminates this Agreement after substantial work has been performed, Attorney may '
        f'assert a claim for attorney&rsquo;s fees based on the reasonable value of services '
        f'rendered, payable from any eventual recovery. Client agrees that {pronoun} obligation '
        f'to compensate Attorney in such cases shall be limited to the reasonable value of the '
        f'services rendered up to the point of termination.', s_body))

    # Signature block
    story.append(Spacer(1, 30))
    story.append(Paragraph("<b>ACCEPTED BY:</b>", s_sig))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"CLIENT ___________________________     Date: _____________________", s_sig))
    story.append(Paragraph(f"<b>{client_name}</b>", s_sig))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Richards &amp; Law Attorney _________________________     Date: _____________________", s_sig))
    story.append(Paragraph(f"<b>Andrew Richards</b>", s_sig))

    doc.build(story)
    return buf.getvalue()


def _upload_document_to_clio(headers: dict, pdf_bytes: bytes, filename: str, matter_id: int = None) -> int | None:
    """Upload generated retainer PDF to Clio Matter documents.
    Uses multipart upload: first create the document, then upload the file."""
    try:
        # Step 1: Create document entry in Clio
        create_payload = {
            "data": {
                "name": filename,
            }
        }
        if matter_id:
            create_payload["data"]["matter"] = {"id": matter_id}
        r = requests.post(
            f"{CLIO_BASE_URL}/documents",
            headers=headers,
            json=create_payload,
        )
        r.raise_for_status()
        doc_id = r.json()["data"]["id"]

        # Step 2: Upload the PDF file content
        upload_headers = {
            "Authorization": headers["Authorization"],
        }
        files = {
            "file": (f"{filename}.pdf", pdf_bytes, "application/pdf"),
        }
        # Get the latest_document_version id for upload
        version_id = r.json()["data"].get("latest_document_version", {}).get("id")
        if version_id:
            r2 = requests.put(
                f"{CLIO_BASE_URL}/document_versions/{version_id}",
                headers=upload_headers,
                files=files,
            )
            if r2.status_code < 300:
                logger.info(f"PDF uploaded to Clio document {doc_id}")
            else:
                logger.warning(f"PDF upload returned {r2.status_code}: {r2.text[:200]}")

        return doc_id

    except Exception as e:
        logger.error(f"Clio document upload failed: {e}")
        return None


# ── Email ─────────────────────────────────────────────────────────────────────

def _get_seasonal_booking_link() -> str:
    """Return the right booking link based on current month.
    March-August = in-office, September-February = virtual."""
    month = datetime.now().month
    if 3 <= month <= 8:
        return BOOKING_LINKS["in_office"]
    else:
        return BOOKING_LINKS["virtual"]


def _calculate_sol(incident_date: str, years: int = 8) -> str | None:
    """Calculate SOL date = incident_date + years. Returns YYYY-MM-DD or None.
    Andrew requested 8 years after the accident date."""
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
    retainer_pdf:  bytes | None = None,
) -> None:
    """Send warm personalized email to client with retainer PDF attached."""

    first_name     = client_name.split()[0] if client_name else "Valued Client"
    accident_date  = verified_data.get("accident_date", "")
    accident_loc   = verified_data.get("accident_location", "")
    opposing_party = verified_data.get("opposing_party_name", "the other driver")
    report_no      = verified_data.get("police_report_number", "")
    narrative      = verified_data.get("narrative", "")
    sol_display    = sol_date or "Date to be confirmed"
    month_name     = datetime.now().strftime("%B")

    # Build dynamic matter title from actual client/opposing names
    client_last    = client_name.strip().split()[-1] if client_name.strip() else "Client"
    opposing_last  = opposing_party.strip().split(",")[0].strip().split()[-1] if opposing_party.strip() else "Defendant"
    matter_title   = f"{client_last} v {opposing_last}"

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
        <tr><td>Matter:</td><td><strong>{matter_title}</strong></td></tr>
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
      Your Retainer Agreement has been prepared and is attached to this email
      as a PDF for your review. This agreement formalizes our representation
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
        f"Richards & Law has accepted your case ({matter_title}).\n\n"
        f"Incident: {accident_date} at {accident_loc}\n"
        f"Opposing Party: {opposing_party}\n"
        f"Police Report: {report_no}\n\n"
        f"IMPORTANT: Your Statute of Limitations expires {sol_display}.\n\n"
        f"Your Retainer Agreement is attached to this email as a PDF.\n\n"
        f"Book your consultation: {booking_link}\n\n"
        f"Andrew Richards\nRichards & Law"
    )

    # Build MIME email with optional PDF attachment
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = FROM_EMAIL
    msg["To"]      = client_email

    # Body (HTML + text alternative)
    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(text_body, "plain", "utf-8"))
    body_part.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(body_part)

    # Attach retainer PDF if available
    if retainer_pdf:
        att = MIMEApplication(retainer_pdf, _subtype="pdf")
        safe_name = client_name.replace(" ", "_")
        att.add_header("Content-Disposition", "attachment", filename=f"Retainer_Agreement_{safe_name}.pdf")
        msg.attach(att)

    ses.send_raw_email(
        Source       = FROM_EMAIL,
        Destinations = [client_email],
        RawMessage   = {"Data": msg.as_string()},
    )


# ── DynamoDB ──────────────────────────────────────────────────────────────────

def _mark_synced(intake_id: str, calendar_id: int | None, matter_id: int | None = None) -> None:
    """Mark the DynamoDB intake record as synced to Clio."""
    update_expr = "SET clio_synced = :s, clio_matter_id = :m, clio_calendar_id = :c, updated_at = :u, #st = :st"
    TABLE.update_item(
        Key       = {"intake_id": intake_id},
        UpdateExpression = update_expr,
        ExpressionAttributeNames = {"#st": "status"},
        ExpressionAttributeValues = {
            ":s": True,
            ":m": str(matter_id) if matter_id else "N/A",
            ":c": str(calendar_id) if calendar_id else "N/A",
            ":u": datetime.utcnow().isoformat(),
            ":st": "active",
        },
    )


# ── CORS error helper ─────────────────────────────────────────────────────────

def _error(status: int, message: str) -> dict:
    return {
        "statusCode": status,
        "headers":    CORS,
        "body":       json.dumps({"error": message}),
    }