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

## ⭐ Key Highlights

- Fully serverless AWS architecture (Lambda, API Gateway, DynamoDB, S3, CloudFront)
- AI-powered document extraction using **Claude Haiku 4.5**
- Automated legal workflow from intake → verification → Clio sync
- Infrastructure deployed with **AWS SAM + GitHub Actions CI/CD**
- Real-world integrations: **Clio CRM, Calendly, Email automation**

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

## 🏗️ Architecture Diagram
<img width="7656" height="2628" alt="LexCipher drawio" src="https://github.com/user-attachments/assets/4b4e53b0-a1fb-49ee-9177-a87e457b954f" />

---
## 🖥️ Application Walkthrough
### Client Intake Form
<img width="1881" height="1080" alt="image" src="https://github.com/user-attachments/assets/66b5caca-e067-4329-a147-25b16bea953a" />
<img width="1873" height="1002" alt="Screenshot 2026-03-08 190141" src="https://github.com/user-attachments/assets/0f1630ce-562c-477a-a83e-ec55fe6d7b74" />

### Client Portal — Case Status Tracking
<img width="889" height="860" alt="Screenshot 2026-03-08 190953" src="https://github.com/user-attachments/assets/865f3ff1-2f18-4584-bbb7-0b44dd5ba95b" />
<img width="1752" height="1074" alt="Screenshot 2026-03-08 191059" src="https://github.com/user-attachments/assets/0160ceca-3424-493a-a78a-821410fd54a3" />

---
### Attorney Receives New Intake Alert
<img width="1414" height="878" alt="image" src="https://github.com/user-attachments/assets/63cd1331-7aff-41ac-9b4c-f581f7335215" />

---
### Law Firm Dashboard — Paralegal & Attorney
<img width="1902" height="1026" alt="image" src="https://github.com/user-attachments/assets/2c10b3c3-d56b-4fe7-b317-a3bf0d1febd1" />

#### LawFirm Dashboard showing : Police Report Extraction showing 40+ fields** from NY MV-104AN
<img width="1897" height="1016" alt="image" src="https://github.com/user-attachments/assets/b8b81c1d-e0e4-49f6-b3f9-e987059bc389" />

#### LawFirm Dashboard showing : Vehicle Damage Analysis
The dashboard visualizes **AI-extracted vehicle impact zones** from the police report to help the attorney quickly understand the accident scenario.
The system supports multiple accident types automatically detected by the AI extraction pipeline.
**Supported scenarios**

| Accident Type | Visualization |
|---|---|
| Vehicle vs Vehicle | Impact zones mapped on both vehicles |
| Vehicle vs Bicycle | Bicycle rider with impact points |
| Vehicle vs Pedestrian | Pedestrian impact visualization |

<img width="1896" height="1017" alt="image" src="https://github.com/user-attachments/assets/318e0f70-968d-4bc6-a1e5-7919af9a2c0e" />
<img width="1548" height="318" alt="image" src="https://github.com/user-attachments/assets/bf1aad79-c5ce-43d5-a0e9-e01a6c809128" />
<img width="1547" height="316" alt="image" src="https://github.com/user-attachments/assets/65c54acb-32c1-4571-b047-d02db2cd4327" />




#### LawFirm Dashboard showing : Workflow Status
<img width="1902" height="1023" alt="Screenshot 2026-03-08 192517" src="https://github.com/user-attachments/assets/bdbc84a0-da66-4a9d-bd54-a8ef2011751d" />

---
### Retainer Agreement & Consultation Scheduling Sent to Client Email-ID
After attorney approval, LexCipher automatically generates a **retainer agreement PDF** and sends it to the client via email.  
The email explains the **contingency fee agreement** and provides a **Calendly booking link** so the client can schedule their initial consultation.
<img width="730" height="833" alt="image" src="https://github.com/user-attachments/assets/a02313b1-5175-4f77-946a-d0ff384586a3" />
<img width="1529" height="791" alt="Screenshot 2026-03-08 191258" src="https://github.com/user-attachments/assets/fcf50a57-e19a-432b-9373-5b0e45ca2e0c" />

#### The system automatically selects the **consultation format based on the season**.

#### Seasonal Consultation Logic
| Season | Months | Consultation Type | Booking Method |
|------|------|------|------|
| **Spring & Summer** | March – August | In-Office Meeting | Client books a physical office consultation via Calendly |
| **Autumn & Winter** | September – February | Virtual Meeting | Client books a remote consultation (video call) via Calendly |

This ensures consultations remain convenient for clients while accommodating seasonal conditions.
<img width="1064" height="706" alt="image" src="https://github.com/user-attachments/assets/322c20b2-29a2-4907-aade-28ff92bdf72b" />


---
### Clio CRM Sync
<img width="1915" height="677" alt="image" src="https://github.com/user-attachments/assets/bc1fea83-dcc4-4b4d-bd8e-7a50375d3f60" />














## 🔄 Automation Pipeline

```mermaid
graph TD
    subgraph "STAGE 1 — Client Intake"
        A["🧑 Client visits intake form<br/>(CloudFront)"] --> B["Fills in: name, email, phone,<br/>incident date, description,<br/>uploads police report PDF"]
        B --> C["POST /intake<br/>(API Gateway)"]
    end

    subgraph "STAGE 2 — AI Processing (automatic, ~10 sec)"
        C --> D["lexcipher-intake Lambda"]
        D --> E["📄 Upload PDF → S3"]
        D --> F["🤖 Claude AI — Classify Case<br/>type, viability 0-10, urgency"]
        D --> G["🤖 Claude AI — Extract Report<br/>40+ fields from MV-104AN"]
        F --> H["💾 Save to DynamoDB"]
        G --> H
        H --> I["📧 Client gets confirmation email"]
        H --> J["📧 Attorney gets alert email<br/>with viability score,<br/>key facts, urgency level"]
    end

    subgraph "STAGE 3 — Paralegal Verification"
        H --> K["👩‍💼 Paralegal opens Dashboard"]
        K --> L["Reviews AI-extracted data<br/>Views original police report PDF"]
        L --> M["Edits/corrects any<br/>fields AI got wrong"]
        M --> N["Saves verified_data<br/>→ DynamoDB"]
        N --> O["Sets status → 'verified'<br/>PATCH /intakes/id/status"]
    end

    subgraph "STAGE 4 — Attorney Review & Approval"
        O --> P["⚖️ Attorney reviews<br/>verified case on Dashboard"]
        P --> Q["Reviews: case type, viability,<br/>SOL deadline, police report,<br/>paralegal-verified data"]
        Q --> R{"Attorney Decision"}
        R -->|"Decline"| S["Status → declined<br/>Case closed"]
        R -->|"Approve"| T["Clicks 'Accept & Sync to Clio'<br/>POST /clio with verified_data<br/>+ client_email"]
    end

    subgraph "STAGE 5 — Clio Sync + Retainer (auto after approval)"
        T --> U["lexcipher-clio Lambda"]
        U --> V["1. Create Contact in Clio<br/>(client name + email)"]
        V --> W["2. Create Matter<br/>'LastName v OpposingName - PI'"]
        W --> X["3. Fill 11 Custom Fields<br/>(accident data, vehicles, etc.)"]
        X --> Y["4. Set Matter → Open"]
        Y --> Z["5. Create SOL Calendar Event<br/>⚠️ Deadline on Clio calendar"]
        Z --> AA["6. Generate Retainer PDF<br/>(ReportLab — firm branded)"]
        AA --> AB["7. Upload Retainer → Clio Docs"]
        AB --> AC["✅ Mark DynamoDB:<br/>clio_synced = true,<br/>status = active"]
    end

    subgraph "STAGE 6 — Client Receives Retainer"
        AB --> AD["📧 SES sends email to<br/>CLIENT EMAIL from intake form"]
        AD --> AE["🧑 Client receives:<br/>• Retainer agreement PDF<br/>• Case details & SOL warning<br/>• Calendly booking link<br/>• Contingency fee explanation"]
        AE --> AF["Client books consultation<br/>via Calendly link"]
    end

    subgraph "BONUS — Client Portal"
        AC --> AG["🔗 Client can check status<br/>/portal?token=xxx<br/>(read-only, safe fields only)"]
    end

    style A fill:#1B3A6B,color:#fff
    style F fill:#7c3aed,color:#fff
    style G fill:#7c3aed,color:#fff
    style J fill:#dc2626,color:#fff
    style K fill:#2563eb,color:#fff
    style O fill:#2563eb,color:#fff
    style P fill:#C9A84C,color:#000
    style Q fill:#C9A84C,color:#000
    style T fill:#C9A84C,color:#000
    style AD fill:#16a34a,color:#fff
    style AE fill:#16a34a,color:#fff
    style S fill:#dc2626,color:#fff
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


## ⚠️Challenges & Lessons Learned 💡

| Problem | Obstacle | Solution | Impact |
|--------|----------|----------|--------|
| **Lambda deployment failure** | Intake Lambda stopped working after deployment due to handler misconfiguration in the CloudFormation/SAM template, causing the API endpoint to fail. | Rolled back to a stable deployment version and introduced stricter deployment controls, avoiding function signature changes and isolating improvements to prompt logic. | Restored the intake pipeline and improved reliability of serverless deployments. |
| **AI extraction inaccuracies** | AI model produced inconsistent outputs when extracting structured fields from police report PDFs (date swaps, incorrect DOB parsing, field misinterpretation). | Designed a structured multi-step prompt with validation rules tailored to the NY MV-104AN form and iteratively tested across multiple cases. | Improved extraction reliability and reduced incorrect field mappings during automated intake processing. |
| **Frontend dashboard crash** | Dashboard occasionally crashed due to inline script execution inside a template literal, causing improper rendering and JavaScript errors. | Refactored rendering logic to remove inline script injection and separated DOM updates from execution logic. | Stabilized dashboard rendering and improved reliability of the client-side interface. |
| **AWS SES sandbox blocking client emails** | SES sandbox mode only allows sending to verified email addresses, so real client emails entered in the intake form were rejected. | Requested SES production access with a detailed transactional email use case description. | Identified the root cause of blocked emails and attempted proper AWS escalation. |
| **SES production access denied** | AWS denied production access (common for newer accounts with limited history), preventing the system from emailing real clients. | Replaced SES with Gmail SMTP (`smtplib`) and stored the Gmail App Password securely in AWS SSM Parameter Store. | Email system now works immediately without sandbox restrictions, allowing the system to communicate with real users. |

---
##  🚀 Future Roadmap 🛣️

- Replace Gmail SMTP with Amazon SES production access once approved

- Add OCR support for handwritten police reports using Amazon Textract

- Implement authentication for the dashboard (AWS Cognito / JWT)

- Add CloudWatch monitoring and alerting for Lambda failures

- Support additional police report formats beyond NY MV-104AN

- Add rate limiting and AWS WAF protection on API Gateway

- Introduce Multi-tenancy support so multiple Law Firms can use the platform with isolated data, configurations, and dashboards

---
## 👩‍💻 Author
#### Chinmayee Pradhan
#### Network Engineer | DevOps & AI Engineer
#### LinkedIn: https://www.linkedin.com/in/chinmayee-pradhan-devops/


