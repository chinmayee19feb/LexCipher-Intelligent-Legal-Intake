import requests
import json

# ══════════════════════════════════════════════════════════════════════════════
# EMAIL CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
#
# 📧 EMAIL #1 — You → Andrew (fictional client)
#    PURPOSE : You manually write this email delivering the solution to Andrew
#    TESTING : lexcipher.client@gmail.com
#    FINAL   : talent.legal-engineer.hackathon.client-email@swans.co
CLIENT_EMAIL = "lexcipher.client@gmail.com"

# 📧 EMAIL #2 — You → Swans Judges
#    PURPOSE : You manually write this with video walkthrough + JSON blueprint
#    TESTING : lexcipher.submission@gmail.com
#    FINAL   : talent.legal-engineer.hackathon.submission-email@swans.co
SUBMISSION_EMAIL = "lexcipher.submission@gmail.com"

# 📧 EMAIL #3 — Your Automation → Client (Guillermo Reyes)
#    PURPOSE : Your automation sends this personalized email to the client
#              with retainer PDF + seasonal booking link
#    TESTING : chinmayee.ohmaws@gmail.com
#    FINAL   : talent.legal-engineer.hackathon.automation-email@swans.co
AUTOMATION_EMAIL = "chinmayee.ohmaws@gmail.com"

# ══════════════════════════════════════════════════════════════════════════════
# ⚠️  BEFORE FINAL SUBMISSION — change all 3 emails above to:
#    CLIENT_EMAIL     = "talent.legal-engineer.hackathon.client-email@swans.co"
#    SUBMISSION_EMAIL = "talent.legal-engineer.hackathon.submission-email@swans.co"
#    AUTOMATION_EMAIL = "talent.legal-engineer.hackathon.automation-email@swans.co"
# ══════════════════════════════════════════════════════════════════════════════

# ── Load credentials ──────────────────────────────────────────────────────────
with open("credentials.json") as f:
    creds = json.load(f)

ACCESS_TOKEN = creds["access_token"]
BASE_URL     = "https://app.clio.com/api/v4"
HEADERS      = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type":  "application/json"
}

# ── Helper functions ──────────────────────────────────────────────────────────
def post(endpoint, payload):
    r = requests.post(f"{BASE_URL}{endpoint}", headers=HEADERS, json=payload)
    print(f"\n{'='*50}")
    print(f"POST {endpoint}  →  {r.status_code}")
    print(json.dumps(r.json(), indent=2))
    return r.json()

def get(endpoint, params=None):
    r = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=params)
    return r.json()

# ── 1. Create Custom Fields on Matters ───────────────────────────────────────
print("\n🔧 STEP 1 — Creating custom fields on Matters...")

custom_fields = [
    {"name": "Accident Date",               "field_type": "date",      "parent_type": "Matter"},
    {"name": "Accident Location",           "field_type": "text_line", "parent_type": "Matter"},
    {"name": "Accident Description",        "field_type": "text_area", "parent_type": "Matter"},
    {"name": "Client Vehicle",              "field_type": "text_line", "parent_type": "Matter"},
    {"name": "Opposing Party Name",         "field_type": "text_line", "parent_type": "Matter"},
    {"name": "Opposing Party Vehicle",      "field_type": "text_line", "parent_type": "Matter"},
    {"name": "Police Report Number",        "field_type": "text_line", "parent_type": "Matter"},
    {"name": "Statute of Limitations Date", "field_type": "date",      "parent_type": "Matter"},
]

field_ids = {}
for cf in custom_fields:
    result = post("/custom_fields", {"data": cf})
    if "data" in result:
        field_ids[cf["name"]] = result["data"]["id"]
        print(f"  ✅ Created: {cf['name']}  (id={result['data']['id']})")
    else:
        print(f"  ❌ Failed: {cf['name']}")

# ── 2. Create Contact (Guillermo Reyes) ───────────────────────────────────────
print(f"\n👤 STEP 2 — Creating Contact (Guillermo Reyes) with email: {AUTOMATION_EMAIL}")

contact_payload = {
    "data": {
        "type":       "Person",
        "first_name": "Guillermo",
        "last_name":  "Reyes",
        "emails": [
            {
                "address":       AUTOMATION_EMAIL,
                "name":          "Work",
                "default_email": True
            }
        ]
    }
}
contact_result = post("/contacts", contact_payload)
contact_id = contact_result.get("data", {}).get("id")
print(f"  ✅ Contact ID: {contact_id}")

# ── 3. Get Responsible Attorney (Andrew Richards) user ID ─────────────────────
print("\n👨‍⚖️  STEP 3 — Getting Andrew Richards user ID...")

users = get("/users")
user_id = None
for u in users.get("data", []):
    print(f"  Found user: {u['name']}  id={u['id']}")
    user_id = u["id"]

print(f"  ✅ Responsible Attorney ID: {user_id}")

# ── 4. Create Matter ──────────────────────────────────────────────────────────
print("\n📁 STEP 4 — Creating Matter (Reyes v Francois)...")

matter_payload = {
    "data": {
        "description":          "Reyes v Francois - Personal Injury",
        "status":               "Pending",
        "responsible_attorney": {"id": user_id},
        "client":               {"id": contact_id}
    }
}
matter_result = post("/matters", matter_payload)
matter_id = matter_result.get("data", {}).get("id")
print(f"  ✅ Matter ID: {matter_id}")

# ── 5. Save all IDs + emails for later use ────────────────────────────────────
output = {
    "access_token":    ACCESS_TOKEN,
    "contact_id":      contact_id,
    "matter_id":       matter_id,
    "user_id":         user_id,
    "field_ids":       field_ids,
    "emails": {
        "client_email":     CLIENT_EMAIL,
        "submission_email": SUBMISSION_EMAIL,
        "automation_email": AUTOMATION_EMAIL
    }
}

with open("clio_ids.json", "w") as f:
    json.dump(output, f, indent=2)

print("\n\n✅ ALL DONE! IDs saved to clio_ids.json")
print(json.dumps(output, indent=2))