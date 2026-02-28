import json
import logging
import anthropic
from prompt import (
    CLASSIFICATION_SYSTEM_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    build_classification_prompt,
    build_extraction_prompt,
)

logger = logging.getLogger(__name__)

client = anthropic.Anthropic()
MODEL  = "claude-haiku-4-5"


# ── Case Classification ────────────────────────────────────────────────────

def classify_case(client_name: str, description: str, incident_date: str, prior_attorney: bool) -> dict:
    """
    Classify a PI case from the client's text description.
    Returns a dict with case_type, viability_score, urgency, sol_flag,
    key_facts, recommended_action, client_acknowledgment.
    """
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=CLASSIFICATION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": build_classification_prompt(
                        client_name=client_name,
                        description=description,
                        incident_date=incident_date,
                        prior_attorney=prior_attorney,
                    ),
                }
            ],
        )

        raw = response.content[0].text.strip()
        result = json.loads(raw)
        _validate_classification(result)
        logger.info(f"Classification: {result['case_type']} | Score: {result['viability_score']} | Urgency: {result['urgency']}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse classification JSON: {e}")
        return _fallback_classification()
    except Exception as e:
        logger.error(f"Classification error: {e}")
        return _fallback_classification()


def _validate_classification(result: dict) -> None:
    """Ensure all required fields are present and valid."""
    from prompt import VALID_CASE_TYPES

    required = ["case_type", "viability_score", "urgency", "sol_flag",
                "key_facts", "recommended_action", "client_acknowledgment"]

    for field in required:
        if field not in result:
            raise ValueError(f"Missing field: {field}")

    if result["case_type"] not in VALID_CASE_TYPES:
        logger.warning(f"Unknown case type '{result['case_type']}' — defaulting to Out of Scope")
        result["case_type"] = "Out of Scope"

    if not isinstance(result["viability_score"], (int, float)):
        result["viability_score"] = 0

    result["viability_score"] = max(0, min(10, int(result["viability_score"])))

    if result["urgency"] not in ("critical", "high", "medium", "low"):
        result["urgency"] = "medium"

    if not isinstance(result["key_facts"], list):
        result["key_facts"] = []


def _fallback_classification() -> dict:
    """Safe default when Claude fails to respond correctly."""
    return {
        "case_type": "Out of Scope",
        "viability_score": 0,
        "urgency": "low",
        "sol_flag": False,
        "key_facts": [],
        "recommended_action": "Manual review required — AI classification failed.",
        "client_acknowledgment": (
            "Thank you for reaching out to Richards & Law. "
            "We have received your inquiry and a member of our team will be in touch shortly."
        ),
    }


# ── Police Report Extraction ───────────────────────────────────────────────

def extract_police_report(pdf_base64: str, media_type: str = "application/pdf") -> dict:
    """
    Extract structured data from a police report PDF using Claude's vision.
    pdf_base64: base64-encoded PDF content
    Returns a dict with accident details, parties, fault, witnesses, etc.
    """
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": pdf_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": build_extraction_prompt(),
                        },
                    ],
                }
            ],
        )

        raw = response.content[0].text.strip()
        result = json.loads(raw)
        logger.info(f"Police report extracted: report# {result.get('police_report_number', 'unknown')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse extraction JSON: {e}")
        return _fallback_extraction()
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return _fallback_extraction()


def _fallback_extraction() -> dict:
    """Safe default when PDF extraction fails."""
    return {
        "accident_date": None,
        "accident_time": None,
        "accident_location": None,
        "police_report_number": None,
        "reporting_officer": None,
        "client_vehicle": None,
        "client_vehicle_plate": None,
        "client_injuries_noted": None,
        "opposing_party_name": None,
        "opposing_party_vehicle": None,
        "opposing_party_plate": None,
        "opposing_party_insurance": None,
        "fault_determination": None,
        "witnesses": [],
        "charges_filed": None,
        "narrative_summary": "Extraction failed — manual review of PDF required.",
    }