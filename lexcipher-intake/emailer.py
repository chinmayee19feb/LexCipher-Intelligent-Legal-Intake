import os
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ── SES setup ─────────────────────────────────────────────────────────────
ses            = boto3.client("ses", region_name=os.environ.get("AWS_REGION", "us-east-1"))
FROM_EMAIL     = os.environ.get("FROM_EMAIL",     "ch.pradhan606@gmail.com")
ATTORNEY_EMAIL = os.environ.get("ATTORNEY_EMAIL", "lexcipher.submission@gmail.com")
PORTAL_BASE_URL = os.environ.get("PORTAL_BASE_URL", "https://d1kxxuu61azwve.cloudfront.net/dashboard/index.html")

# Urgency badge colors for attorney alert email
URGENCY_COLORS = {
    "critical": "#DC2626",   # red
    "high":     "#EA580C",   # orange
    "medium":   "#CA8A04",   # yellow
    "low":      "#16A34A",   # green
}


# ── Client Confirmation Email ──────────────────────────────────────────────

def send_client_confirmation(
    client_name:    str,
    client_email:   str,
    intake_id:      str,
    portal_token:   str,
    acknowledgment: str,
    case_type:      str,
    has_police_report: bool = False,
) -> bool:
    """Send a confirmation email to the client with their portal link."""

    first_name   = client_name.split()[0]
    portal_link  = f"{PORTAL_BASE_URL}?token={portal_token}"
    pdf_note     = (
        "<p style='color:#059669;font-size:14px;'>✅ <strong>Police report received.</strong> "
        "Our team will review the uploaded document as part of your case evaluation.</p>"
        if has_police_report else ""
    )

    subject = f"Richards & Law — We've Received Your Inquiry ({intake_id[:8].upper()})"

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F8F5F0;font-family:'DM Sans',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F8F5F0;padding:40px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

        <!-- Header -->
        <tr>
          <td style="background:#0B1B2B;padding:32px 40px;">
            <p style="margin:0;font-family:Georgia,serif;font-size:22px;font-weight:600;color:#ffffff;letter-spacing:0.02em;">
              Richards <span style="color:#C9A84C;">&</span> Law
            </p>
            <p style="margin:4px 0 0;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:rgba(255,255,255,0.4);">
              Personal Injury Attorneys · New York
            </p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:40px;">
            <h1 style="font-family:Georgia,serif;font-size:26px;color:#0B1B2B;margin:0 0 8px;">
              We've Received Your Inquiry
            </h1>
            <div style="width:48px;height:3px;background:#C9A84C;border-radius:2px;margin:0 0 24px;"></div>

            <p style="font-size:15px;color:#374151;line-height:1.7;margin:0 0 16px;">
              Dear {first_name},
            </p>
            <p style="font-size:15px;color:#374151;line-height:1.7;margin:0 0 16px;">
              {acknowledgment}
            </p>

            {pdf_note}

            <p style="font-size:14px;color:#6B7E8F;margin:16px 0 8px;">Case Type Identified:</p>
            <p style="font-size:15px;font-weight:600;color:#0B1B2B;margin:0 0 24px;">{case_type}</p>

            <!-- Portal Button -->
            <table cellpadding="0" cellspacing="0" style="margin:24px 0;">
              <tr>
                <td style="background:#0B1B2B;border-radius:8px;padding:14px 28px;">
                  <a href="{portal_link}" style="color:#ffffff;font-size:15px;font-weight:500;text-decoration:none;">
                    Track Your Case Status →
                  </a>
                </td>
              </tr>
            </table>

            <p style="font-size:13px;color:#9CA3AF;line-height:1.6;margin:0 0 8px;">
              Your reference ID: <strong style="font-family:monospace;color:#0B1B2B;">{intake_id[:8].upper()}</strong>
            </p>
            <p style="font-size:13px;color:#9CA3AF;line-height:1.6;margin:0;">
              If you have any questions, reply to this email or call us directly.
            </p>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#F8F5F0;padding:24px 40px;border-top:1px solid #EDE9E2;">
            <p style="font-size:12px;color:#9CA3AF;margin:0;line-height:1.6;">
              🔒 This communication is protected by attorney-client privilege.
              Richards & Law · New York, NY · <a href="mailto:{FROM_EMAIL}" style="color:#C9A84C;">{FROM_EMAIL}</a>
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    text_body = f"""Richards & Law — Inquiry Received

Dear {first_name},

{acknowledgment}

Case Type: {case_type}
Reference ID: {intake_id[:8].upper()}

Track your case: {portal_link}

Richards & Law | Personal Injury Attorneys | New York
"""

    return _send_email(
        to=client_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )


# ── Attorney Alert Email ───────────────────────────────────────────────────

def send_attorney_alert(
    intake_id:      str,
    client_name:    str,
    client_email:   str,
    client_phone:   str,
    incident_date:  str,
    case_type:      str,
    viability_score: int,
    urgency:        str,
    sol_flag:       bool,
    key_facts:      list,
    recommended_action: str,
    has_police_report:  bool = False,
    prior_attorney:     bool = False,
) -> bool:
    """Send an alert to the attorney with full case details."""

    urgency_color  = URGENCY_COLORS.get(urgency, "#6B7E8F")
    sol_banner     = """
    <tr>
      <td style="background:#FEF2F2;border:1px solid #FECACA;border-radius:8px;padding:12px 16px;margin-bottom:16px;">
        <p style="margin:0;font-size:14px;color:#DC2626;font-weight:600;">
          ⚠️ STATUTE OF LIMITATIONS WARNING — Action required within 90 days
        </p>
      </td>
    </tr>""" if sol_flag else ""

    prior_atty_note = (
        "<p style='font-size:13px;color:#EA580C;margin:4px 0 0;'>⚠️ Client has spoken to another attorney</p>"
        if prior_attorney else ""
    )

    pdf_badge = (
        "<span style='background:#DCFCE7;color:#16A34A;font-size:11px;font-weight:600;"
        "padding:3px 10px;border-radius:20px;margin-left:8px;'>📄 Police Report Uploaded</span>"
        if has_police_report else ""
    )

    facts_html = "".join(
        f"<li style='margin:4px 0;font-size:14px;color:#374151;'>{fact}</li>"
        for fact in key_facts
    )

    subject = f"[{urgency.upper()}] New Intake: {client_name} — {case_type} ({intake_id[:8].upper()})"

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#F8F5F0;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F8F5F0;padding:40px 0;">
    <tr><td align="center">
      <table width="640" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

        <!-- Header with urgency color -->
        <tr>
          <td style="background:#0B1B2B;padding:28px 40px;border-top:4px solid {urgency_color};">
            <p style="margin:0;font-family:Georgia,serif;font-size:20px;font-weight:600;color:#ffffff;">
              Richards <span style="color:#C9A84C;">&</span> Law — New Intake Alert
            </p>
            <span style="display:inline-block;margin-top:8px;background:{urgency_color};color:white;
              font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;
              padding:4px 14px;border-radius:20px;">
              {urgency} urgency
            </span>
          </td>
        </tr>

        <tr><td style="padding:32px 40px;">
          <table width="100%" cellpadding="0" cellspacing="0">

            {sol_banner}

            <!-- Client Info -->
            <tr><td style="padding-bottom:24px;">
              <h2 style="font-family:Georgia,serif;font-size:22px;color:#0B1B2B;margin:0 0 4px;">
                {client_name} {pdf_badge}
              </h2>
              {prior_atty_note}
              <p style="margin:8px 0 0;font-size:14px;color:#6B7E8F;">
                📧 {client_email} &nbsp;|&nbsp; 📞 {client_phone} &nbsp;|&nbsp; 📅 Incident: {incident_date}
              </p>
            </td></tr>

            <!-- Case Type & Score -->
            <tr><td style="padding-bottom:24px;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td width="60%" style="background:#F8F5F0;border-radius:8px;padding:16px;">
                    <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:#9CA3AF;">Case Type</p>
                    <p style="margin:0;font-size:16px;font-weight:600;color:#0B1B2B;">{case_type}</p>
                  </td>
                  <td width="8px"></td>
                  <td width="40%" style="background:#F8F5F0;border-radius:8px;padding:16px;text-align:center;">
                    <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:0.1em;color:#9CA3AF;">Viability Score</p>
                    <p style="margin:0;font-size:28px;font-weight:700;color:#0B1B2B;">{viability_score}<span style="font-size:14px;color:#9CA3AF;">/10</span></p>
                  </td>
                </tr>
              </table>
            </td></tr>

            <!-- Key Facts -->
            <tr><td style="padding-bottom:24px;">
              <p style="margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.1em;color:#9CA3AF;">Key Facts</p>
              <ul style="margin:0;padding-left:20px;">{facts_html}</ul>
            </td></tr>

            <!-- Recommended Action -->
            <tr><td style="padding-bottom:24px;">
              <p style="margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.1em;color:#9CA3AF;">Recommended Action</p>
              <p style="margin:0;font-size:14px;color:#374151;line-height:1.6;background:#FFF9EC;
                border-left:3px solid #C9A84C;padding:12px 16px;border-radius:0 8px 8px 0;">
                {recommended_action}
              </p>
            </td></tr>

            <!-- Reference -->
            <tr><td>
              <p style="margin:0;font-size:12px;color:#9CA3AF;">
                Reference ID: <strong style="font-family:monospace;color:#0B1B2B;">{intake_id}</strong>
              </p>
            </td></tr>

          </table>
        </td></tr>

        <!-- Footer -->
        <tr>
          <td style="background:#F8F5F0;padding:20px 40px;border-top:1px solid #EDE9E2;">
            <p style="font-size:12px;color:#9CA3AF;margin:0;">
              Richards & Law Internal System · LexCipher Intake Pipeline
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    text_body = f"""NEW INTAKE — {urgency.upper()} URGENCY
{'⚠️  SOL WARNING — Action required within 90 days' if sol_flag else ''}

Client:       {client_name}
Email:        {client_email}
Phone:        {client_phone}
Incident:     {incident_date}
Case Type:    {case_type}
Viability:    {viability_score}/10
Prior Atty:   {'Yes' if prior_attorney else 'No'}
Police Report:{'Yes' if has_police_report else 'No'}

Key Facts:
{chr(10).join(f'- {f}' for f in key_facts)}

Recommended Action:
{recommended_action}

Reference ID: {intake_id}
"""

    return _send_email(
        to=ATTORNEY_EMAIL,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )


# ── Internal send helper ───────────────────────────────────────────────────

def _send_email(to: str, subject: str, html_body: str, text_body: str) -> bool:
    try:
        ses.send_email(
            Source=FROM_EMAIL,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                },
            },
        )
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except ClientError as e:
        logger.error(f"SES send failed to {to}: {e}")
        return False