<p align="center">
  <img src="https://img.shields.io/badge/AWS-SAM-FF9900?style=for-the-badge&logo=amazonaws" alt="AWS SAM"/>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Claude_AI-Haiku_4.5-7C3AED?style=for-the-badge" alt="Claude AI"/>
  <img src="https://img.shields.io/badge/Clio-API_v4-1B3A6B?style=for-the-badge" alt="Clio"/>
  <img src="https://img.shields.io/badge/CI/CD-GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" alt="GitHub Actions"/>
</p>

# ⚖️ LexCipher — Intelligent Legal Intake Automation

> AI-powered police report extraction, case classification, and end-to-end case management automation for personal injury law firms.

LexCipher transforms a process that takes **hours of manual paralegal work** into a **2-minute automated pipeline** — from client inquiry to Clio matter creation, SOL tracking, and retainer delivery.

---

## 🎯 What It Does

A client fills out a web form and uploads a police report. From that moment, LexCipher:

1. **Classifies the case** using Claude AI (type, viability 0–10, urgency, SOL risk)
2. **Extracts 40+ fields** from the NY MV-104AN police report using Claude AI
3. **Alerts the attorney** with a viability summary via email
4. **Lets the paralegal verify** AI-extracted data on a dashboard
5. **Syncs everything to Clio** after attorney approval (contact, matter, 11 custom fields, calendar event)
6. **Generates a retainer agreement PDF** with all case data pre-filled
7. **Emails the client** the retainer + Calendly booking link

All serverless. All automated. Zero manual data entry.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT BROWSER                               │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐    │
│  │ Intake Form  │  │ Paralegal/Atty   │  │  Client Portal     │    │
│  │ (CloudFront) │  │ Dashboard        │  │  (read-only)       │    │
│  └──────┬───────┘  └───────┬──────────┘  └────────┬───────────┘    │
└─────────┼──────────────────┼──────────────────────┼────────────────┘
          │ POST /intake     │ GET/PATCH /intakes    │ GET /portal
          ▼                  ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      API GATEWAY (REST)                              │
│         /intake    /intakes    /intakes/{id}    /clio    /portal     │
└────┬──────────────────┬────────────────────────────┬────────────────┘
     ▼                  ▼                            ▼
┌──────────┐    ┌──────────────┐              ┌──────────┐
│ Intake   │    │  Dashboard   │              │  Clio    │
│ Lambda   │    │  Lambda      │              │  Lambda  │
└────┬─────┘    └──────────────┘              └────┬─────┘
     │                                             │
     ├──→ Claude AI (classify + extract)           ├──→ Clio API v4 (contact, matter,
     ├──→ S3 (store PDF)                           │     custom fields, calendar, docs)
     ├──→ DynamoDB (save intake)                   ├──→ ReportLab (generate retainer PDF)
     └──→ SES (client confirm + attorney alert)    └──→ SES (retainer email to client)
```

---

## 🔄 Automation Pipeline

```mermaid
graph TD
    A[Client visits intake form] --> B[Fills name email phone date description uploads PDF]
    B --> C[POST /intake - API Gateway]
    C --> D[lexcipher-intake Lambda]
    D --> E[Upload PDF to S3]
    D --> F[Claude AI classifies case]
    D --> G[Claude AI extracts police report 40+ fields]
    F --> H[Save to DynamoDB]
    G --> H
    H --> I[Email client - confirmation]
    H --> J[Email attorney - alert with viability score]
    H --> K[Paralegal opens Dashboard]
    K --> L[Reviews AI data vs original PDF]
    L --> M[Corrects mistakes and saves verified data]
    M --> N[Attorney reviews verified case on Dashboard]
    N --> O{Attorney Decision}
    O -->|Decline| P[Status declined - Case closed]
    O -->|Approve| Q[Clicks Accept and Sync to Clio]
    Q --> R[POST /clio - API Gateway]
    R --> S[lexcipher-clio Lambda]
    S --> T[Create Contact in Clio]
    T --> U[Create Matter in Clio]
    U --> V[Fill 11 Custom Fields]
    V --> W[Set Matter Status to Open]
    W --> X[Create SOL Calendar Event]
    X --> Y[Generate Retainer PDF]
    Y --> Z[Upload PDF to Clio Documents]
    Z --> AA[SES sends retainer email to client]
    AA --> AB[Client receives Retainer PDF + case details + Calendly booking link]
    Z --> AC[DynamoDB updated - clio_synced true]
```

---

## 📁 Project Structure

```
├── intake-form/
│   └── index.html                  # Client-facing intake form
│
├── lexcipher-intake/                # Lambda: intake processing + AI
│   ├── handler.py                  # Entry point — validates, orchestrates
│   ├── ai_classifier.py           # Claude AI calls (classify + extract)
│   ├── prompt.py                  # Detailed AI prompts for NY MV-104AN form
│   ├── db.py                      # DynamoDB operations
│   ├── emailer.py                 # SES: client confirmation + attorney alert
│   └── requirements.txt
│
├── lexcipher-clio/                  # Lambda: Clio sync + retainer
│   ├── handler.py                  # Clio API, PDF generation, retainer email
│   ├── extractor.py               # Backup AI extraction from S3
│   └── requirements.txt
│
├── dashboard/                       # Lambda: dashboard API + frontend
│   ├── handler.py                  # CRUD for intakes, portal, PDF presign
│   └── index.html                  # Paralegal/attorney dashboard
│
├── portal/
│   └── index.html                  # Client status portal (read-only)
│
├── template.yaml                   # AWS SAM — all infrastructure as code
├── clio_setup.py                   # One-time Clio custom field setup
├── clio_add_fields.py              # Helper for adding Clio fields
└── .github/workflows/
    └── deploy.yml                  # CI/CD: push to main → auto deploy
```

---

## 🤖 How Claude AI Is Used

LexCipher makes **two AI calls** per intake, both using `claude-haiku-4-5`:

### Call 1 — Case Classification

| | |
|---|---|
| **Input** | Client's name, description, incident date |
| **Output** | `case_type`, `viability_score` (0–10), `urgency`, `sol_flag`, `key_facts`, `recommended_action` |
| **Prompt** | `lexcipher-intake/prompt.py` → `CLASSIFICATION_SYSTEM_PROMPT` |

### Call 2 — Police Report Extraction

| | |
|---|---|
| **Input** | Police report PDF (base64) |
| **Output** | 40+ structured fields (dates, names, vehicles, plates, injuries, fault, narrative, SOL) |
| **Prompt** | `lexcipher-intake/prompt.py` → `EXTRACTION_SYSTEM_PROMPT` |
| **Supported Form** | New York MV-104AN Police Accident Report |

The AI handles vehicle-vs-vehicle, vehicle-vs-bicycle, and vehicle-vs-pedestrian cases automatically by detecting which checkbox is marked on the police report header.

---

## ⚙️ AWS Resources (created by `template.yaml`)

| Resource | Service | Purpose |
|----------|---------|---------|
| `lexcipher-intake-prod` | Lambda | Intake processing + AI extraction |
| `lexcipher-clio-prod` | Lambda | Clio sync + retainer generation |
| `lexcipher-dashboard-prod` | Lambda | Dashboard API + client portal |
| `lexcipher-api-prod` | API Gateway | REST API with CORS |
| `lexcipher-intakes` | DynamoDB | Case data storage |
| `lexcipher-police-reports-*` | S3 | Police report PDFs (AES256, 7yr retention) |
| `lexcipher-frontend-*` | S3 | Static frontend hosting |
| CloudFront Distribution | CloudFront | HTTPS frontend delivery |
| `/lexcipher/anthropic/api_key` | SSM | Claude AI API key (encrypted) |
| `/lexcipher/clio/access_token` | SSM | Clio OAuth2 token (encrypted) |
| `lexcipher-deps` | Lambda Layer | Shared Python dependencies |

---

## 🔌 External Integrations

### Anthropic Claude AI
- **Model:** `claude-haiku-4-5`
- **Auth:** API key stored in AWS SSM Parameter Store
- **Used for:** Case classification + police report data extraction

### Clio Manage (API v4)
- **Base URL:** `https://app.clio.com/api/v4`
- **Auth:** OAuth2 Bearer token stored in AWS SSM
- **Resources:** Contacts, Matters, Custom Fields, Calendar Entries, Documents
- **Custom Fields:** 11 fields mapped (Accident Date, Location, Vehicles, Plates, Police Report #, SOL Date, etc.)

### Calendly
- **Purpose:** Client consultation booking
- **Summer/Spring (Mar–Aug):** In-office link
- **Winter/Autumn (Sep–Feb):** Virtual link

### Amazon SES
- **Sender:** `ch.pradhan606@gmail.com`
- **Emails sent:** Client confirmation, attorney alert, retainer delivery with PDF attachment
- **Requirement:** SES production access needed to send to any recipient

---

## 🚀 Deployment

### Prerequisites

- AWS account with IAM credentials
- GitHub repository with Actions enabled
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Clio API access token ([app.clio.com/settings/developer_apps](https://app.clio.com/settings/developer_apps))
- SES verified sender email (and production access for unrestricted sending)

### GitHub Secrets Required

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM access key |
| `AWS_SECRET_ACCESS_KEY` | IAM secret key |
| `AWS_ACCOUNT_ID` | AWS account number |
| `ANTHROPIC_API_KEY` | Claude AI API key |
| `CLIO_ACCESS_TOKEN` | Clio OAuth2 access token |

### Deploy

Push to `main` and GitHub Actions handles everything:

```bash
git add .
git commit -m "deploy"
git push origin main
```

The CI/CD pipeline will:
1. Build Lambda layer with dependencies
2. Package and deploy all Lambdas via SAM
3. Inject API URL into frontend files
4. Upload frontend to S3
5. Invalidate CloudFront cache

### Manual Deploy (SAM CLI)

```bash
# Install dependencies for Lambda layer
mkdir -p layer/python
pip install anthropic==0.40.0 boto3==1.35.0 requests==2.31.0 \
    python-dateutil==2.9.0 reportlab==4.1.0 -t layer/python

# Build and deploy
sam build --use-container
sam deploy \
  --stack-name lexcipher \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    Stage=prod \
    AnthropicApiKey=YOUR_KEY \
    ClioAccessToken=YOUR_TOKEN \
    SesFromEmail=your@email.com \
    AttorneyEmail=attorney@email.com
```

---

## 🔗 API Endpoints

| Method | Path | Lambda | Description |
|--------|------|--------|-------------|
| `POST` | `/intake` | Intake | Submit new client inquiry |
| `POST` | `/clio` | Clio | Sync approved case to Clio |
| `GET` | `/intakes` | Dashboard | List all intakes |
| `GET` | `/intakes/{id}` | Dashboard | Get single intake details |
| `PATCH` | `/intakes/{id}/status` | Dashboard | Update status + save verified data |
| `GET` | `/intakes/{id}/pdf` | Dashboard | Get presigned S3 URL for police report |
| `DELETE` | `/intakes/{id}` | Dashboard | Delete single intake |
| `DELETE` | `/intakes/reset` | Dashboard | Clear all intakes |
| `GET` | `/portal?token=xxx` | Dashboard | Client portal (read-only) |

---

## 📊 Clio Custom Fields

11 custom fields are automatically populated in the Clio matter when a case is approved, including accident date, location, vehicles, plates, opposing party, police report number, SOL date, and more.

> Run `clio_setup.py` once to create these fields in your Clio account. Field IDs are configured in `lexcipher-clio/handler.py`.

---

## 📧 Email Flow

| Trigger | Recipient | Content |
|---------|-----------|---------|
| Client submits form | Client email | Confirmation + acknowledgment |
| Client submits form | Attorney email | Alert with viability score, urgency, key facts |
| Attorney approves case | Client email | Retainer PDF + case details + Calendly booking link |

The retainer email includes firm-branded HTML with seasonal booking links (in-office for summer, virtual for winter).

---

## 🛡️ Security

- **Secrets:** All API keys stored in AWS SSM Parameter Store (encrypted)
- **PDFs:** Stored in S3 with AES-256 server-side encryption
- **Public Access:** S3 police report bucket has all public access blocked
- **Client Portal:** Read-only, limited to safe fields (no viability scores or internal notes)
- **CORS:** Configured on API Gateway for frontend access
- **PDF Retention:** 7-year lifecycle policy (legal compliance)

---

## ⚡ NY Statute of Limitations Rules

Built into the AI classification prompt:

| Case Type | SOL Period |
|-----------|-----------|
| Vehicle Accident | 8 years from incident |
| Slip and Fall | 3 years from incident |
| Medical Malpractice | 2.5 years from incident/discovery |
| Workplace Injury | 3 years (2 years workers comp) |
| Employment Law | 3 years for most claims |
| Against Government | 90 days to file notice of claim |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML/CSS/JS (single-file, no framework) |
| Hosting | S3 + CloudFront (HTTPS) |
| API | API Gateway (REST) |
| Compute | AWS Lambda (Python 3.12) |
| Database | DynamoDB (PAY_PER_REQUEST) |
| File Storage | S3 (AES-256) |
| Email | Amazon SES |
| AI | Anthropic Claude Haiku 4.5 |
| Case Management | Clio Manage API v4 |
| Scheduling | Calendly |
| Secrets | AWS SSM Parameter Store |
| IaC | AWS SAM (CloudFormation) |
| CI/CD | GitHub Actions |
| PDF Generation | ReportLab 4.1.0 |

---

## 📝 License

Proprietary — Richards & Law. All rights reserved.
