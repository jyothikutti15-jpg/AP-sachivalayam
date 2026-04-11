# AP Sachivalayam AI Copilot — Product Features

> **Mission:** Telugu-first AI assistant for Andhra Pradesh's 1.3 lakh village secretariat employees across 11,162 secretariats.
> Delivered over WhatsApp. Powered by Claude AI. 10 features, 73 endpoints, 33 schemes, 928 tests.
> Built for the IndiaAI Challenge 2026.

---

## At a Glance

| Metric | Value |
|---|---|
| Features | 10 integrated AI features |
| API Endpoints | 73 REST endpoints |
| Schemes Covered | 33 (including Super Six) |
| Test Coverage | 928 tests across 28 files |
| Services | 26 service modules |
| Data Models | 19 SQLAlchemy ORM models |
| Celery Workers | 9 worker modules, 8 scheduled tasks |
| Languages | Telugu (primary) + English |
| Delivery | WhatsApp Business API |
| Offline | Yes — FAQ cache + rule-based fallback |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        WhatsApp Business API                         │
│                  (Text · Voice · Interactive Buttons)                 │
└──────────────┬───────────────────────────────────┬──────────────────┘
               |                                   |
    ┌──────────v────────────┐           ┌──────────v────────────────┐
    │   FastAPI (REST API)   │           │    Celery Workers          │
    │   73 endpoints         │           │    - Voice transcribe      │
    │   Correlation ID MW    │           │    - PDF generation        │
    │   Rate Limit MW        │           │    - GSWS sync             │
    │   Prometheus Metrics   │           │    - Grievance SLA check   │
    └──────────┬─────────────┘           │    - Task scheduler        │
               |                          │    - Outreach scan         │
    ┌──────────v────────────┐           │    - Citizen reminders     │
    │  Conversation Engine   │           │    - Metrics aggregation   │
    │  (Intent -> Service)   │           └────────────────────────────┘
    └──────────┬─────────────┘
               |
    ┌──────────v────────────────────────────────────────────────────────┐
    │                          Service Layer (26 modules)                │
    │                                                                    │
    │  SchemeAdvisor     FormFiller       GrievanceService               │
    │  TaskService       VoicePipeline    ChecklistService               │
    │  CircularService   ReminderService  OutreachEngine                 │
    │  ConversationEng   OCRService       TrainingService                │
    │  AnalyticsService  SupervisorSvc    PerformanceService             │
    │  PDFGenerator      ExportService    NotificationService            │
    │  WhatsAppService   GSWSBridge       KnowledgeIndexer               │
    │  AuditService      OfflineQueue     DuplicateDetector              │
    │  LLMRouter (Claude + Circuit Breaker + PII Stripping)             │
    └──────────┬────────────────────────────────────┬──────────────────┘
               |                                    |
    ┌──────────v────────────┐         ┌─────────────v─────────────────┐
    │  Claude AI             │         │  PostgreSQL 16 + pgvector     │
    │  claude-sonnet-4-6     │         │  Redis 7 (Cache / Sessions)   │
    │  Circuit Breaker       │         │  Alembic Migrations           │
    └────────────────────────┘         └───────────────────────────────┘
```

---

## Feature 1: Instant Scheme Eligibility Checker

**Problem:** Employees answer 100+ scheme questions daily from memory. Wrong answers cause citizens to lose benefits they're entitled to.

**Solution:** Employee types or speaks a citizen's situation in Telugu -> AI checks eligibility for all applicable schemes and lists required documents.

### Capabilities

| Capability | Description | Endpoint |
|---|---|---|
| Semantic Search | RAG pipeline over 33 schemes using pgvector embeddings | `POST /api/v1/schemes/search` |
| Single Eligibility Check | Claude analyses citizen profile against scheme criteria | `POST /api/v1/schemes/eligibility-check` |
| Batch Eligibility Check | Up to 50 citizen-scheme pairs in one call -- concurrent LLM execution | `POST /api/v1/schemes/eligibility-check/batch` |
| Scheme Listing | Browse all schemes with department filters | `GET /api/v1/schemes/` |
| Scheme Details | Full scheme info including GO references | `GET /api/v1/schemes/{code}` |

### Search Chain (fast -> slow)

```
Query arrives
  |
  v
[1] Redis FAQ Cache .............. 0 ms   (top 200 queries, 24h TTL)
  |
  v (miss)
[2] DB FAQ Keyword Match ......... ~5 ms  (bilingual matching)
  |
  v (miss)
[3] pgvector Semantic Search ..... ~500 ms (384-D cosine similarity + Claude)
  |
  v (miss)
[4] Keyword Fallback ............. ~2 s   (ILIKE on scheme table + Claude)
```

### Batch Eligibility

- Single DB query fetches all unique schemes (no N+1)
- All LLM calls run concurrently via `asyncio.gather` (~50x faster than sequential)
- Per-item error isolation -- one bad scheme code doesn't fail the whole batch
- Response: `total`, `eligible_count`, per-item `is_eligible`, `reasoning_te`, `missing_documents`, `next_steps_te`

### Supported Schemes (33)

**Super Six (TDP Government):**

| Scheme | Telugu Name | Benefit |
|---|---|---|
| Thalliki Vandanam | తల్లికి వందనం | Rs 15,000/year per school child |
| Annadata Sukhibhava | అన్నదాత సుఖీభవ | Rs 20,000/year for farmers |
| NTR Bharosa Pension | NTR భరోసా పెన్షన్ | Rs 4,000-15,000/month (12 categories) |
| Deepam 2.0 | దీపం 2.0 | 3 free LPG cylinders/year |
| Stree Shakti | స్త్రీ శక్తి | Free bus travel for women |
| Yuva Galam | యువ గళం | Rs 3,000/month unemployment allowance |

**Plus 27 more:** Cheyutha, Asara, Bima, Dr. NTR Vaidya Seva (Aarogyasri), Kanti Velugu, Kalyanamasthu, Vahana Mitra, Vidya Deevena, Vasathi Deevena, Sampoorna Poshana, Pedalandariki Illu, Nethanna Nestham, Matsyakara Bharosa, Jala Kala, Law Nestham, Navodayam, Sunna Vaddi, EHF, Jagananna Suraksha, Thodu, Chedodu, Navasakam, Ammavodi Plus, Yantra Seva, Sampoorna Poshana Plus, MGNREGS.

Each scheme JSON includes: eligibility criteria, required documents, benefit amount, application process (Telugu), GO reference, effective dates, active/inactive status.

---

## Feature 2: Report & Certificate Drafting

**Problem:** Employees spend hours manually typing forms, applications, and field reports.

**Solution:** Employee describes the case via text or voice -> AI drafts the official G.O. format document in seconds.

### Capabilities

| Capability | Description | Endpoint |
|---|---|---|
| Auto-Fill Forms | Claude extracts fields from Telugu text/voice | `POST /api/v1/forms/auto-fill` |
| PDF Generation | WeasyPrint renders AP Government format PDFs with Telugu fonts | `GET /api/v1/forms/{id}/pdf` |
| GSWS Submission | Submit directly to government portal (offline queue fallback) | `POST /api/v1/forms/{id}/submit-to-gsws` |
| Template Library | 10 form templates covering major schemes | `GET /api/v1/forms/templates` |
| OCR Scanning | Extract fields from scanned document images via Claude Vision | `POST /api/v1/forms/ocr` |

### Form Templates (10)

| # | Template | Fields | Department |
|---|---|---|---|
| 1 | Thalliki Vandanam (Amma Vodi) | 18 | School Education |
| 2 | Annadata Sukhibhava (Rythu Bharosa) | -- | Agriculture |
| 3 | NTR Bharosa Pension | 11 | Panchayat Raj |
| 4 | Dr. NTR Vaidya Seva (Aarogyasri) | -- | Health |
| 5 | YSR Cheyutha | -- | Women & Child Welfare |
| 6 | Chandranna Pelli Kanuka (Kalyanamasthu) | 13 | Welfare |
| 7 | Navaratnalu Pedalandariki Illu | -- | Housing |
| 8 | Post-Matric Scholarship (Vidya Deevena) | -- | Education |
| 9 | YSR Bima Claim | -- | Insurance |
| 10 | MGNREGS Employment Guarantee | -- | Rural Development |

### Confidence Scoring

| Score | Meaning | Example |
|---|---|---|
| 1.0 | Explicit -- directly stated by citizen | "నా పేరు లక్ష్మి" -> name = లక్ష్మి |
| 0.7 | Inferred -- derived from context | "వైట్ కార్డు" -> ration_card = white (BPL) |
| 0.3 | Guessed -- low confidence, needs confirmation | Age inferred from "retirement" mention |

### Security

- **Aadhaar:** Only last 4 digits visible in responses; full number hashed with bcrypt (rounds=12, random salt) -- never stored raw
- **PII:** Stripped before every LLM call (Aadhaar + phone numbers)
- **GSWS:** Real API integration with mock fallback when credentials unavailable

---

## Feature 3: Grievance Resolution Assistant

**Problem:** Citizens face delays when complaints go untracked. No systematic escalation.

**Solution:** AI suggests the correct department and escalation path, then tracks resolution with automated SLA enforcement.

### Capabilities

| Capability | Description | Endpoint |
|---|---|---|
| File Grievance | Create with auto-department routing | `POST /api/v1/grievances/` |
| Track by Reference | Track using GRV-YYYY-NNNN reference | `GET /api/v1/grievances/reference/{ref}` |
| AI Suggestions | Claude suggests category, priority, escalation path, evidence | `POST /api/v1/grievances/ai-suggest` |
| Status Updates | Update status, assign, resolve, close | `PATCH /api/v1/grievances/{id}` |
| Comments Thread | Add resolution notes and discussion | `POST /api/v1/grievances/{id}/comments` |
| Dashboard Stats | Stats by status, SLA breach count | `GET /api/v1/grievances/stats/summary` |
| Bulk Create | Up to 50 grievances per batch | `POST /api/v1/grievances/bulk-create` |
| Export CSV | Full data with date/status filters (up to 5,000 rows) | `GET /api/v1/grievances/export/csv` |

### Grievance Categories (9)

| Category | Telugu | Department | SLA |
|---|---|---|---|
| Electricity | విద్యుత్ | Energy (APSPDCL) | **24 h** |
| Health | ఆరోగ్యం | Health | **48 h** |
| Water Supply | నీటి సరఫరా | Panchayat Raj | **48 h** |
| Agriculture | వ్యవసాయం | Agriculture | 72 h |
| Education | విద్య | Education | 72 h |
| Welfare | సంక్షేమం | Welfare | 72 h |
| Other | ఇతరం | General Administration | 72 h |
| Revenue | రెవెన్యూ | Revenue | 120 h |
| Roads/Transport | రోడ్లు & రవాణా | Roads & Buildings | 120 h |

### Escalation Path (auto-triggered on SLA breach)

```
Level 0: సచివాలయం (Village Secretariat)
    | SLA breach -> auto-escalate
Level 1: మండల అధికారి (Mandal Officer / MPDO)
    | SLA breach -> auto-escalate
Level 2: జిల్లా కలెక్టర్ (District Collector)
    | SLA breach -> auto-escalate
Level 3: రాష్ట్ర స్థాయి (State Level)
```

Auto-escalation check runs every **30 minutes** via Celery beat.

### Duplicate Detection

- Fuzzy matching (rapidfuzz `token_sort_ratio`) on descriptions
- 75% similarity -> flagged, 85% -> high-confidence duplicate
- Non-blocking -- warns but never prevents filing

---

## Feature 4: Daily Task Prioritization

**Problem:** Each employee manages 34 departments -- decision overload causes burnout. People's Pulse survey (Jan 2026) reported mental health crises.

**Solution:** AI reads the employee's pending queue and outputs a prioritised daily plan, capped at 8 hours to prevent overload.

### Capabilities

| Capability | Description | Endpoint |
|---|---|---|
| Daily Plan | AI-powered prioritised task list | `GET /api/v1/tasks/daily-plan` |
| Create Tasks | Manual or auto-generated | `POST /api/v1/tasks/` |
| Start / Complete | Track task progress | `POST /api/v1/tasks/{id}/start` / `/complete` |
| Workload Summary | Load level: light/moderate/heavy/overloaded | `GET /api/v1/tasks/workload/summary` |
| Bulk Create | Up to 100 tasks per batch | `POST /api/v1/tasks/bulk-create` |
| Export CSV | Full task data with filters | `GET /api/v1/tasks/export/csv` |

### Priority Scoring (0-100)

| Priority | Base Score | +Overdue | +Due Today | +Due in 3 Days | +Citizen-Facing |
|---|---|---|---|---|---|
| Urgent | 90 | +20 (cap 100) | +10 | +5 | +5 |
| High | 70 | +20 | +10 | +5 | +5 |
| Medium | 50 | +20 | +10 | +5 | +5 |
| Low | 30 | +20 | +10 | +5 | +5 |

### Task Categories

`scheme_processing` . `citizen_service` . `field_visit` . `data_entry` . `report_writing` . `grievance_followup` . `meeting` . `survey` . `inspection` . `general`

### Workload Levels

| Level | Tasks | Action |
|---|---|---|
| Light | 0-3 | Normal |
| Moderate | 4-8 | Normal |
| Heavy | 9-15 | Warning to supervisor |
| Overloaded | 16+ | Redistribute tasks |

### Burnout Prevention

- **8-hour daily cap** (480 minutes) -- AI defers non-critical tasks
- **Department grouping** -- reduces context switching
- **Overdue alerts** -- prevents pile-up
- Rule-based fallback when Claude is unavailable

### Automated Workers

- **5:30 AM IST:** Create recurring tasks (daily / weekly / monthly / weekdays)
- **6:00 AM IST:** Generate AI daily plans -> send via WhatsApp to every active employee

---

## Feature 5: Voice Input (Telugu STT)

**Problem:** Typing long citizen details in Telugu on mobile is slow and error-prone.

**Solution:** Employee sends a voice note -> AI transcribes it and extracts structured data.

### Pipeline

```
WhatsApp Voice Note (OGG/MP3/WAV)
    |  FFmpeg: convert to WAV 16kHz mono
    v
Whisper large-v3 (Telugu domain vocabulary)
    |  Raw transcription
    v
Post-Processing
    |  Normalize Telugu text, fix errors, remove repetition
    v
Entity Extraction (regex + rules)
    |  Name, age, income, caste, ration card, scheme references
    v
PII Detection
    |  Flag Aadhaar / phone numbers for stripping
    v
Structured Output with confidence scores
```

**Endpoint:** `POST /api/v1/voice/transcribe`

### Telugu Number Conversion

| Telugu Word | Value |
|---|---|
| ఒకటి | 1 |
| రెండు | 2 |
| పది | 10 |
| వంద | 100 |
| వెయ్యి | 1,000 |
| లక్ష | 1,00,000 |

"రెండు లక్షలు" -> 2,00,000

### File Validation

| Check | Rule |
|---|---|
| Max file size | 25 MB (configurable via `VOICE_MAX_FILE_SIZE_MB`) |
| Accepted types | `audio/ogg`, `audio/mpeg`, `audio/mp4`, `audio/wav`, `audio/aac`, `audio/webm`, `audio/flac`, `audio/x-m4a` |
| Oversized | `413 Request Entity Too Large` |
| Wrong type | `415 Unsupported Media Type` |

Files read in 1 MB chunks -- oversized uploads rejected before fully loading.

---

## Feature 6: Outreach Scanner

**Problem:** Eligible citizens who haven't applied for schemes they qualify for are missed -- no proactive identification.

**Solution:** Weekly automated scan identifies eligible beneficiaries per secretariat and notifies employees via WhatsApp.

### Capabilities

| Capability | Description | Endpoint |
|---|---|---|
| Trigger Scan | Scan a secretariat for eligible citizens | `POST /api/v1/outreach/scan/{secretariat_id}` |
| View Results | Outreach list with status filters | `GET /api/v1/outreach/{secretariat_id}` |
| Eligible Schemes | Find schemes for a beneficiary | `GET /api/v1/outreach/beneficiary/{id}/eligible` |
| Mark Notified | Track notification status | `PATCH /api/v1/outreach/{id}/notify` |
| Mark Applied | Track application status | `PATCH /api/v1/outreach/{id}/applied` |
| Register Beneficiary | Add new beneficiary | `POST /api/v1/beneficiaries` |
| List Beneficiaries | View per secretariat | `GET /api/v1/beneficiaries/{secretariat_id}` |

### How It Works

- Scans all 11,162 secretariats every **Sunday at 3:00 AM IST** via Celery beat
- Rule-based matching: citizen profiles vs 33 active scheme eligibility criteria
- Confidence scoring (0.0-1.0) per match
- Status workflow: identified -> notified -> applied -> enrolled
- Prevents duplicate outreach entries
- Results surfaced to employees via WhatsApp notifications

---

## Feature 7: Training & Quizzes

**Problem:** New employees need to learn 33 schemes and government procedures. No structured training for sachivalayam staff.

**Solution:** AI-generated quizzes and practice scenarios from real citizen situations.

### Capabilities

| Capability | Description | Endpoint |
|---|---|---|
| Get Scenario | AI-generated training scenario | `GET /api/v1/training/scenario` |
| Submit Response | Submit and get AI evaluation | `POST /api/v1/training/submit` |
| Progress | Employee learning progress | `GET /api/v1/training/progress/{employee_id}` |
| Leaderboard | Rank by training performance | `GET /api/v1/training/leaderboard` |

### Features

- Practice scenarios based on real AP citizen situations
- Difficulty scaling based on employee performance
- Claude-based response evaluation with rubric scoring
- Covers all 33 active schemes
- Bilingual (Telugu/English) scenarios

---

## Feature 8: Document Checklist Generator

**Problem:** Citizens eligible for multiple schemes make 2-3 repeat visits because they don't know all the documents needed upfront.

**Solution:** Employee enters a citizen's profile -> AI checks eligibility across all 33 schemes -> generates a consolidated document checklist with common documents highlighted.

### Capabilities

| Capability | Description | Endpoint |
|---|---|---|
| Generate Checklist | AI eligibility + consolidated document list | `POST /api/v1/checklist/generate` |

### Flow

```
Citizen Profile (age, income, caste, ration card, etc.)
    |
    v
AI Eligibility Check (Claude + rule-based fallback)
    |
    v
Eligible Schemes identified (e.g., 5 out of 33)
    |
    v
Required Documents extracted per scheme
    |
    v
Common Documents highlighted ("Aadhaar needed for 5 schemes")
    |
    v
Telugu Summary + Consolidated Checklist returned
```

### Input: Citizen Profile

| Field | Type | Example |
|---|---|---|
| `name` | string | సునీత |
| `age` | int | 35 |
| `gender` | string | female |
| `income` | int | 108000 (annual) |
| `caste` | string | BC / SC / ST / OC / EBC |
| `ration_card` | string | white / pink / rice / antyodaya |
| `occupation` | string | farmer / auto_driver / weaver |
| `is_disabled` | bool | + disability_percentage |
| `land_acres` | float | 2.5 |
| `has_school_children` | bool | + num_children |
| `is_widow` / `is_pregnant` | bool | Special eligibility |

### Document Database (15 Common AP Government Documents)

| English | Telugu |
|---|---|
| Aadhaar Card | ఆధార్ కార్డు |
| Ration Card | రేషన్ కార్డు |
| Income Certificate | ఆదాయ ధృవీకరణ పత్రం |
| Caste Certificate | కులధృవీకరణ పత్రం |
| Residence Certificate | నివాస ధృవీకరణ పత్రం |
| Bank Passbook | బ్యాంకు పాస్‌బుక్ |
| Passport Photo | పాస్‌పోర్ట్ సైజు ఫోటో |
| Voter ID | ఓటరు గుర్తింపు కార్డు |
| Birth Certificate | జనన ధృవీకరణ పత్రం |
| Disability Certificate | వికలాంగ ధృవీకరణ పత్రం |
| Land Document / Pattadar | భూమి పత్రాలు / పట్టాదారు పాస్‌బుక్ |
| School Certificate | పాఠశాల ధృవీకరణ పత్రం |
| Death Certificate | మరణ ధృవీకరణ పత్రం |
| Marriage Certificate | వివాహ ధృవీకరణ పత్రం |
| Medical Certificate | వైద్య ధృవీకరణ పత్రం |

### Fallback

Rule-based eligibility matching (age, income, ration card) activates when Claude is unavailable -- no LLM dependency for basic checks.

---

## Feature 9: GO/Circular Knowledge Base

**Problem:** Employees receive hundreds of government orders -- hard to track what changed, when, and for which schemes.

**Solution:** Employee asks "What changed in Amma Vodi eligibility?" -> AI answers citing specific GO numbers with old/new values.

### Capabilities

| Capability | Description | Endpoint |
|---|---|---|
| Search GOs | AI-powered search with GO citations | `POST /api/v1/circulars/search` |
| List Recent | Browse by department | `GET /api/v1/circulars/` |
| Get by Reference | Fetch by GO number | `GET /api/v1/circulars/reference/{ref}` |
| Create Circular | Add new GO/circular | `POST /api/v1/circulars/` |
| Auto-Summarize | AI structured summary | `POST /api/v1/circulars/summarize` |

### Circular Categories

| Category | Description | Example |
|---|---|---|
| `go` | Government Order | G.O.Ms.No.47, G.O.Rt.No.215 |
| `circular` | Department circular | Policy updates |
| `amendment` | Amendment to existing GO | Eligibility changes |
| `notification` | Official notification | Scheme launch |
| `memo` | Office memorandum | Internal policy |
| `proceedings` | Committee proceedings | Review decisions |

### Key Changes Tracking

```json
{
  "field": "income_limit_rural",
  "old": "Rs 10,000",
  "new": "Rs 12,000",
  "description_te": "గ్రామీణ ఆదాయ పరిమితి పెంపు"
}
```

### Data Model Highlights

- **Impact levels:** critical / high / normal / low
- **Scheme linkage:** which GO affects which scheme
- **District filtering:** affects all districts or specific ones
- **Tags:** `eligibility_change`, `benefit_increase`, `new_scheme`, `payment_schedule`
- **View count:** popularity tracking for analytics
- **AI Summarization:** extracts purpose, key changes, affected parties, deadlines from raw GO text

---

## Feature 10: Citizen Follow-up Reminders

**Problem:** Citizens miss deadlines for pending documents, renewals, and disbursements because there's no systematic follow-up.

**Solution:** Employees schedule WhatsApp reminders that auto-send to citizens at the right time. System also auto-generates reminders from missing documents.

### Capabilities

| Capability | Description | Endpoint |
|---|---|---|
| Create Reminder | Schedule a follow-up | `POST /api/v1/reminders/` |
| Auto-Generate | Create from missing documents | `POST /api/v1/reminders/auto-generate` |
| List Reminders | View with filters | `GET /api/v1/reminders/` |
| Update Reminder | Cancel, acknowledge, reschedule | `PATCH /api/v1/reminders/{id}` |
| Due Today | All reminders due today | `GET /api/v1/reminders/due-today` |
| Stats | Statistics by status and type | `GET /api/v1/reminders/stats` |

### Reminder Types

| Type | Use Case |
|---|---|
| `pending_documents` | Missing documents for scheme application |
| `renewal_deadline` | Benefit renewal approaching |
| `disbursement_date` | Payment disbursement notification |
| `application_followup` | Application status update |
| `scheme_deadline` | Application deadline approaching |
| `general` | Custom follow-up |

### Auto-Generation

When a scheme application has missing documents:

```
Scheme application with missing docs detected
    |
    +-- Reminder 1: 3 days from now (high priority)
    |
    +-- Reminder 2: 3 days before deadline (urgent priority)
    |
    v
WhatsApp messages sent automatically at 8:30 AM IST
```

### Telugu Message Templates

**Pending Documents:**
> నమస్కారం {name} గారు, {scheme} పథకం కోసం మీ దరఖాస్తులో కింది పత్రాలు పెండింగ్‌లో ఉన్నాయి: {documents}. దయచేసి {deadline} లోపు మీ సచివాలయానికి తీసుకురండి.

**Renewal Deadline:**
> నమస్కారం {name} గారు, {scheme} పథకం రెన్యూవల్ గడువు {deadline} న ముగుస్తుంది. దయచేసి సమయానికి మీ సచివాలయంలో రెన్యూవల్ చేయించుకోండి.

**Disbursement Date:**
> నమస్కారం {name} గారు, {scheme} పథకం ద్వారా మీ ఖాతాలో {date} న నగదు జమ అవుతుంది. మీ బ్యాంక్ ఖాతా వివరాలు సరిగ్గా ఉన్నాయో ధృవీకరించుకోండి.

**Application Followup:**
> నమస్కారం {name} గారు, {scheme} పథకం దరఖాస్తు స్థితి: ప్రాసెస్‌లో ఉంది. ఏదైనా అదనపు సమాచారం అవసరమైతే మీ సచివాలయాన్ని సంప్రదించండి.

### Scheduling & Delivery

- Celery beat sends due reminders daily at **8:30 AM IST**
- Priority ordering: urgent -> high -> medium -> low
- Recurring: daily, weekly, monthly with auto-scheduling of next occurrence
- Max 3 sends per reminder to avoid spam
- Status tracking: scheduled -> sent -> acknowledged -> completed
- Phone number auto-formatting (91 prefix for India)

---

## Infrastructure & Reliability

### Request Correlation IDs

Every request gets a unique `X-Correlation-ID` (UUID4). Present in every log line, echoed in response headers.

```json
{"event": "Scheme query received", "correlation_id": "a3f2-...", "path": "/api/v1/schemes/search"}
{"event": "LLM call complete",     "correlation_id": "a3f2-...", "tokens": 312}
```

### Circuit Breaker (Claude API)

| State | Behaviour |
|---|---|
| **CLOSED** | Normal -- all requests pass through |
| **OPEN** | Fail fast -- Telugu fallback returned immediately |
| **HALF-OPEN** | One probe request; success -> CLOSED, failure -> OPEN |

| Setting | Default | Env Var |
|---|---|---|
| Failure threshold | 5 consecutive | `CLAUDE_CIRCUIT_FAILURE_THRESHOLD` |
| Recovery timeout | 60 seconds | `CLAUDE_CIRCUIT_RECOVERY_TIMEOUT` |

**Trips on:** `APIConnectionError`, `APITimeoutError`, `InternalServerError`, `RateLimitError`
**Does NOT trip on:** `BadRequestError` (4xx)

Circuit state exposed in `GET /api/v1/health`.

### Celery Workers -- Scheduled Tasks

| Schedule | Task | Description |
|---|---|---|
| Every 5 min | `process-offline-queue` | Retry failed GSWS submissions |
| Every 30 min | `check-grievance-sla` | Auto-escalate SLA breaches |
| 2:00 AM IST | `nightly-gsws-sync` | Sync data from GSWS portal |
| 5:30 AM IST | `create-recurring-tasks` | Spawn daily/weekly/monthly tasks |
| 6:00 AM IST | `generate-daily-plans` | AI daily plans -> WhatsApp |
| 8:30 AM IST | `send-citizen-reminders` | Send due follow-up reminders |
| 11:30 PM IST | `daily-metrics-aggregation` | Compute performance metrics |
| Sunday 3 AM | `scan-outreach-weekly` | Beneficiary-to-scheme matching |

### Retry Policy

| Task Group | Base Delay | Max Delay | Retries |
|---|---|---|---|
| User-facing (transcribe, PDF, reminders) | 30 s | 5 min | 3 |
| Background (SLA, GSWS sync, plans) | 60 s | 60 min | 3 |
| Weekly outreach scan | 60 s | 60 min | 2 |

+-25% jitter on every retry. `task_acks_late=True` -- tasks not acked until complete.

### Rate Limiting

- Redis sliding window counter per user/IP
- Per-endpoint: WhatsApp 200/min, Grievance 20/min, Exports 5/hour
- Response headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- 429 with Telugu error message
- Fail-open on Redis failure

### Offline Support

- Offline queue with exponential backoff (5 retries, 5 min via Celery)
- Failed GSWS submissions auto-retried
- FAQ cache (200 entries) works without internet
- Keyword-based intent classification works offline
- Rule-based eligibility fallback works without LLM

---

## Security

| Control | Implementation |
|---|---|
| Aadhaar hashing | bcrypt (rounds=12, random salt) via passlib -- never stored raw |
| PII in LLM calls | Aadhaar + phone numbers stripped before every API call |
| Aadhaar in responses | Only last 4 digits visible (`XXXX XXXX 1234`) |
| WhatsApp webhooks | HMAC-SHA256 signature verification |
| Voice uploads | Content-type validation + 25 MB size cap |
| Auth | JWT (python-jose) + bcrypt password hashing |
| Role-based access | 5 roles: employee -> secretariat_admin -> mandal_officer -> district_admin -> system_admin |
| Audit trail | Every action logged with old/new values, IP, timestamp |
| CI security scan | GitHub Actions checks for leaked keys and raw Aadhaar storage |

---

## Monitoring & Observability

| Signal | Tool | Details |
|---|---|---|
| Structured logs | structlog (JSON in prod) | Correlation ID in every line |
| Metrics | Prometheus | REQUEST_COUNT, RESPONSE_TIME, WHATSAPP_MESSAGES, LLM_CALLS |
| Health check | `GET /api/v1/health` | DB, Redis, Claude circuit state |
| Audit trail | `GET /api/v1/audit/logs` | Per-resource, per-employee, date-range |
| Performance | `GET /api/v1/performance/employee/{id}` | Queries, forms, response time |

---

## Analytics & Dashboards

### Analytics

| Metric | Endpoint |
|---|---|
| Secretariat summary | `GET /api/v1/analytics/secretariat/{id}/summary` |
| Burnout report | `GET /api/v1/analytics/burnout-report` |
| Time saved | `GET /api/v1/analytics/time-saved` |
| CSV/PDF export | `GET /api/v1/analytics/export` |

### Supervisor Dashboard

| Capability | Endpoint |
|---|---|
| Mandal overview | `GET /api/v1/supervisor/mandal/{name}/overview` |
| Secretariat rankings | `GET /api/v1/supervisor/mandal/{name}/secretariats` |
| District overview | `GET /api/v1/supervisor/district/{name}/overview` |
| SLA breach alerts | `GET /api/v1/supervisor/alerts/sla-breaches` |
| Low-performing secretariats | `GET /api/v1/supervisor/alerts/low-performing` |
| Employee detail | `GET /api/v1/supervisor/employee/{id}/detail` |

---

## API Summary (73 Endpoints)

| Module | Endpoints | Prefix |
|---|---|---|
| Health | 1 | `/api/v1/health` |
| Schemes | 5 | `/api/v1/schemes` |
| Forms | 4 | `/api/v1/forms` |
| Voice | 1 | `/api/v1/voice` |
| WhatsApp | 2 | `/api/v1/whatsapp` |
| Analytics | 4 | `/api/v1/analytics` |
| Grievances | 11 | `/api/v1/grievances` |
| Tasks | 11 | `/api/v1/tasks` |
| Audit | 2 | `/api/v1/audit` |
| Performance | 3 | `/api/v1/performance` |
| Citizens | 2 | `/api/v1/citizens` |
| Supervisor | 6 | `/api/v1/supervisor` |
| Training | 4 | `/api/v1/training` |
| Outreach | 7 | `/api/v1/outreach` |
| Checklist | 1 | `/api/v1/checklist` |
| Circulars | 5 | `/api/v1/circulars` |
| Reminders | 6 | `/api/v1/reminders` |

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI 0.115+ . Python 3.11+ . async/await |
| Database | PostgreSQL 16 + pgvector . Alembic migrations |
| Cache / Sessions | Redis 7 |
| Task Queue | Celery 5.4 + Redis |
| AI Reasoning | Claude (`claude-sonnet-4-6`) via Anthropic API |
| Voice STT | OpenAI Whisper large-v3 |
| Embeddings | sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2` (384-D) |
| PDF Generation | WeasyPrint 62.0 + Noto Sans Telugu |
| WhatsApp | Meta Cloud API v21 |
| Government Portal | GSWS AP API (real + mock fallback) |
| Containerisation | Docker Compose (app, PostgreSQL, Redis, Celery worker, Celery beat) |
| CI/CD | GitHub Actions (lint + test + security scan) |
| Monitoring | Prometheus + structlog |
| Linting | Ruff |

---

## Project Structure

```
ap-sachivalayam-copilot/
|-- app/
|   |-- api/v1/              # 19 route modules, 73 endpoints
|   |-- core/                # Circuit breaker, security, Telugu utils
|   |-- data/
|   |   |-- schemes/         # 33 scheme JSONs with real criteria
|   |   |-- templates/       # 10 government form templates
|   |   |-- telugu_prompts/  # System prompts for Claude
|   |   +-- scheme_faqs.json # Bilingual FAQs
|   |-- models/              # 19 SQLAlchemy ORM model files
|   |-- schemas/             # Pydantic request/response schemas
|   |-- services/            # 26 service modules
|   +-- workers/             # 9 Celery worker modules
|-- alembic/
|   +-- versions/            # Database migration history
|-- scripts/
|   |-- demo.py              # Interactive demo (all 10 features)
|   |-- seed_db.py           # Load schemes, FAQs, templates
|   |-- generate_embeddings.py
|   +-- onboard_employees.py
|-- tests/                   # 28 test files, 928 tests
|-- docs/
|   |-- FEATURES.md          # This file
|   |-- IMPACT.md            # Time saved, cost analysis, ROI
|   |-- COMPONENTS.md        # Component reference
|   +-- ...
|-- .github/workflows/ci.yml # GitHub Actions CI/CD
|-- Dockerfile
|-- docker-compose.yml
|-- Makefile                  # 15 commands
|-- pyproject.toml
|-- LICENSE                   # MIT
+-- README.md
```

---

## Test Coverage

**928 tests across 28 files**

```bash
make test          # Full suite (~45 seconds)
make test-fast     # Skip slow integration tests
python scripts/demo.py  # Interactive demo (no Docker needed)
```

| Area | Key Test Files | Tests |
|---|---|---|
| End-to-end (all 10 features) | `test_end_to_end_all_features.py` | 65 |
| API endpoints | `test_api_endpoints.py` | 32 |
| Service integration | `test_service_integration.py` | 52 |
| Real-world scenarios | `test_real_world_scenarios.py` | 45+ |
| New features real data | `test_new_features_real_data.py` | 30+ |
| Scheme advisor / RAG | `test_scheme_advisor.py` | 21 |
| Conversation engine | `test_conversation_engine.py` | 17 |
| Grievance service | `test_grievance_service.py` | 16 |
| Task service | `test_task_service.py` | 18 |
| Document checklist | `test_checklist.py` | 14 |
| GO/Circulars | `test_circulars.py` | 14 |
| Citizen reminders | `test_reminders.py` | 16 |
| Voice + Telugu + Security | various | 50+ |
| Outreach + Supervisor + OCR | various | 30+ |

### Real Data Sources

Tests use **real AP government data**, not synthetic:

| Data | Source |
|---|---|
| 33 scheme criteria | thallikivandanam.com, sspensions.ap.gov.in, annadathasukhibhava.ap.gov.in |
| 8 citizen profiles | Real demographics from Srikakulam, Guntur, Krishna, Visakhapatnam |
| 5 grievance scenarios | AP Spandana portal categories |
| 7 daily tasks | Real sachivalayam workload across 6 departments |
| 3 GO/circulars | Real GO references with key changes |
| 4 reminder templates | Telugu messages for each reminder type |

---

## Deployment

### Docker (Recommended)

```bash
# First-time setup
make setup      # Docker build + seed + migrations

# Start all services
make run        # Background
make run-dev    # With live reload

# Verify
make health     # API health check
make test       # 928 tests
```

### Makefile Commands

| Command | Description |
|---|---|
| `make setup` | First-time: Docker + seed + migrations |
| `make run` | Start all services (background) |
| `make run-dev` | Start with hot reload |
| `make test` | Run 928 tests |
| `make test-fast` | Skip slow tests |
| `make lint` | Ruff linter |
| `make lint-fix` | Auto-fix lint issues |
| `make seed` | Reload scheme data |
| `make embed` | Generate RAG embeddings |
| `make health` | API health check |
| `make logs` | Application logs |
| `make logs-celery` | Worker logs |
| `make migrate` | Run Alembic migrations |
| `make migrate-create` | Create new migration |
| `make clean` | Remove containers + volumes |

### Environment Variables

See `.env.example` for all options:

| Variable | Description | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API key | Yes |
| `DATABASE_URL` | PostgreSQL connection | Yes (Docker default provided) |
| `REDIS_URL` | Redis connection | Yes (Docker default provided) |
| `CLAUDE_MODEL` | Model name | No (default: claude-sonnet-4-6) |
| `WHATSAPP_ACCESS_TOKEN` | Meta Cloud API token | For WhatsApp features |
| `GSWS_API_KEY` | GSWS portal key | For govt portal (mock fallback) |
| `VOICE_MAX_FILE_SIZE_MB` | Voice upload limit | No (default: 25) |

---

## Impact Projections

| Metric | Value |
|---|---|
| Employees impacted | 1,30,000 |
| Citizens served | 4.9 crore |
| Time saved per employee | ~2 hours/day |
| Annual savings (employee time) | Rs 447 crore |
| Annual savings (citizen visits) | Rs 440 crore |
| Scheme leakage reduction | Rs 236 crore |
| Deployment cost | Rs 2-5 crore/year |
| **ROI** | **98x** |

See [IMPACT.md](IMPACT.md) for detailed methodology and calculations.

---

## Related Documentation

- [Impact Projections](IMPACT.md) -- time saved, cost analysis, ROI methodology
- [Components Reference](COMPONENTS.md) -- complete component documentation
- [Live Test Results](LIVE_TEST_RESULTS.md) -- actual test output with real data
- [Testing Guide](TESTING_WITH_REAL_DATA.md) -- how tests use real AP government data
