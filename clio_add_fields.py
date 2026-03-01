import requests
import json

# ── Load credentials ──────────────────────────────────────────────────────────
with open("credentials.json") as f:
    creds = json.load(f)

ACCESS_TOKEN = creds["access_token"]
BASE_URL     = "https://app.clio.com/api/v4"
HEADERS      = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type":  "application/json"
}

# ── 1. Add 3 missing custom fields ───────────────────────────────────────────
print("\n=== Adding missing custom fields ===")

new_fields = [
    {"name": "Client Vehicle Plate",  "field_type": "text_line", "parent_type": "Matter"},
    {"name": "Client Pronoun",        "field_type": "text_line", "parent_type": "Matter"},
    {"name": "Number Injured",        "field_type": "text_line", "parent_type": "Matter"},
]

for cf in new_fields:
    r = requests.post(f"{BASE_URL}/custom_fields", headers=HEADERS, json={"data": cf})
    result = r.json()
    if "data" in result:
        print(f"  Created: {cf['name']}  (id={result['data']['id']})")
    elif r.status_code == 422:
        print(f"  Already exists: {cf['name']} (skipped)")
    else:
        print(f"  Error: {cf['name']} -> {r.status_code} {r.text[:200]}")

# ── 2. Fetch ALL custom field IDs ────────────────────────────────────────────
print("\n=== All Custom Field IDs ===")

r = requests.get(f"{BASE_URL}/custom_fields", headers=HEADERS, params={"parent_type": "Matter", "limit": 50})
fields = r.json().get("data", [])

field_ids = {}
for f in fields:
    field_ids[f["name"]] = f["id"]
    print(f"  {f['name']:40s} id={f['id']}")

# ── 3. Fetch Matter ID and Contact ID ────────────────────────────────────────
print("\n=== Matter & Contact Info ===")

r = requests.get(f"{BASE_URL}/matters", headers=HEADERS, params={"limit": 10})
matters = r.json().get("data", [])
for m in matters:
    print(f"  Matter: {m.get('display_number')} - {m.get('description')}  id={m['id']}  status={m.get('status')}")

r = requests.get(f"{BASE_URL}/contacts", headers=HEADERS, params={"limit": 10})
contacts = r.json().get("data", [])
for c in contacts:
    print(f"  Contact: {c.get('name')}  id={c['id']}")

r = requests.get(f"{BASE_URL}/users", headers=HEADERS, params={"limit": 10})
users = r.json().get("data", [])
for u in users:
    print(f"  User: {u.get('name')}  id={u['id']}")

# ── 4. Save everything ───────────────────────────────────────────────────────
output = {
    "field_ids": field_ids,
    "matters": [{
        "id": m["id"],
        "description": m.get("description"),
        "display_number": m.get("display_number"),
        "status": m.get("status")
    } for m in matters],
    "contacts": [{"id": c["id"], "name": c.get("name")} for c in contacts],
    "users": [{"id": u["id"], "name": u.get("name")} for u in users],
}

with open("clio_all_ids.json", "w") as f:
    json.dump(output, f, indent=2)

print("\n=== Saved to clio_all_ids.json ===")
print(json.dumps(output, indent=2))