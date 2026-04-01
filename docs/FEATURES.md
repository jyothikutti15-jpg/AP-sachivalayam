# AP Sachivalayam AI Copilot — Features Document

> AI assistant for Andhra Pradesh's 1.3 lakh village secretariat employees across 11,162 secretariats.
> Handles paperwork, scheme queries, grievance resolution, and task management in Telugu.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    WhatsApp Business API                      │
│              (Text, Voice, Interactive Buttons)               │
└──────────────┬───────────────────────────────┬───────────────┘
               │                               │
    ┌──────────▼──────────┐         ┌──────────▼──────────┐
    │  FastAPI (REST API)  │         │  Celery Workers      │
    │  8 route modules     │         │  - Voice transcribe  │
    │  30+ endpoints       │         │  - PDF generation    │
    └──────────┬───────────┘         │  - GSWS sync         │
               │                     │  - Grievance SLA     │
    ┌──────────▼──────────┐         │  - Task scheduler    │
    │ Conversation Engine  │         └──────────────────────┘
    │ (Intent → Service)   │
    └──────────┬───────────┘
               │
    ┌──────────▼──────────────────────────────────────────────┐
    │                    Service Layer                          │
    │  SchemeAdvisor │ FormFiller │ GrievanceService │ TaskSvc │
    │  VoicePipeline │ PDFGen   │ Analytics │ GSWSBridge      │
    └──────────┬──────────────────────────────────┬───────────┘
               │                                  │
    ┌──────────▼──────────┐         ┌─────────────▼───────────┐
    │  Claude API          │         │  PostgreSQL + pgvector   │
    │  (Reasoning/Draft)   │         │  Redis (Cache/Sessions)  │
    └──────────────────────┘         └─────────────────────────┘
```

---

## Feature 1: Instant Scheme Eligibility Checker

**Problem:** Employees answer 100+ scheme questions from memory. Citizens face delays.

**Solution:** Employee types or speaks a citizen's situation in Telugu → AI checks all schemes and tells them which ones apply and what documents are needed.

### Capabilities

| Capability | Description | Endpoint |
|-----------|-------------|----------|
| **Semantic Search** | RAG pipeline searches 30+ schemes using pgvector embeddings | `POST /api/v1/schemes/search` |
| **Eligibility Check** | Claude analyzes citizen details against scheme criteria | `POST /api/v1/schemes/eligibility-check` |
| **Scheme Listing** | Browse all schemes with department filters | `GET /api/v1/schemes/` |
| **Scheme Details** | Full scheme info including GO references | `GET /api/v1/schemes/{code}` |

### Search Chain (fast → slow)
1. **Redis FAQ Cache** (0ms) — Top 200 FAQs pre-loaded on startup
2. **DB FAQ Keyword Match** (~5ms) — Bilingual FAQ matching
3. **pgvector Semantic Search** (~500ms) — Cosine similarity on 384D embeddings + Claude
4. **Keyword Fallback** (~2s) — ILIKE search in scheme table + Claude

### Supported Schemes (30+)
YSR Amma Vodi, Rythu Bharosa, Aarogyasri, Cheyutha, Pension Kanuka, Kalyanamasthu, Vahana Mitra, Sunna Vaddi, Bima, Navodayam, Nethanna Nestham, Law Nestham, Matsyakara Bharosa, Sampoorna Poshana, Kanti Velugu, Jala Kala, EHF, Asara, Jagananna Vidya Deevena, Vasathi Deevena, Chedodu, Suraksha, Thodu, Navasakam, Pedalandariki Illu, and more.

---

## Feature 2: Report & Certificate Drafting

**Problem:** Employees spend hours manually typing forms, applications, and field reports.

**Solution:** Employee describes the case via text or voice → AI drafts the official G.O. format document in seconds.

### Capabilities

| Capability | Description | Endpoint |
|-----------|-------------|----------|
| **Auto-Fill Forms** | Claude extracts fields from Telugu text/voice | `POST /api/v1/forms/auto-fill` |
| **PDF Generation** | WeasyPrint renders AP Government format PDFs with Telugu fonts | `GET /api/v1/forms/{id}/pdf` |
| **GSWS Submission** | Submit directly to government portal (with offline queue fallback) | `POST /api/v1/forms/{id}/submit-to-gsws` |
| **Template Library** | 10 form templates covering major schemes | `GET /api/v1/forms/templates` |

### Form Templates Available
1. Amma Vodi Application (18 fields)
2. Rythu Bharosa Registration
3. Pension Application (11 fields)
4. Aarogyasri Card Application
5. Cheyutha Application
6. Kalyanamasthu Application (13 fields)
7. Housing (Pedalandariki Illu)
8. Vidya Deevena Application
9. YSR Bima Claim
10. MGNREGS Employment Guarantee

### Security
- Aadhaar: Only last 4 digits stored, full number hashed (SHA-256)
- PII stripped before LLM calls
- Confidence scoring per field (1.0=explicit, 0.7=inferred, 0.3=guessed)

---

## Feature 3: Grievance Resolution Assistant

**Problem:** Citizens face delays when complaints go untracked. No systematic escalation.

**Solution:** When a citizen complaint comes in, AI suggests the correct department, escalation path, required evidence, and tracks resolution with 72-hour SLA.

### Capabilities

| Capability | Description | Endpoint |
|-----------|-------------|----------|
| **File Grievance** | Create grievance with auto-department routing | `POST /api/v1/grievances/` |
| **Track by Reference** | Track using GRV-YYYY-NNNN reference number | `GET /api/v1/grievances/reference/{ref}` |
| **AI Suggestions** | Claude suggests category, priority, escalation path, evidence needed | `POST /api/v1/grievances/ai-suggest` |
| **Status Updates** | Update status, assign, resolve, close | `PATCH /api/v1/grievances/{id}` |
| **Comments Thread** | Add resolution notes and discussion | `POST /api/v1/grievances/{id}/comments` |
| **Dashboard Stats** | Grievance stats by status, SLA breach count | `GET /api/v1/grievances/stats/summary` |
| **List & Filter** | Filter by status, category, priority, employee, secretariat | `GET /api/v1/grievances/` |

### Grievance Categories (9)
| Category | Telugu | Department | Subcategories |
|----------|--------|-----------|---------------|
| Agriculture | వ్యవసాయం | Agriculture | crop_damage, subsidy_delay, input_supply, insurance |
| Health | ఆరోగ్యం | Health | hospital_service, aarogyasri_issue, medicine_shortage, phc_complaint |
| Education | విద్య | Education | school_issue, scholarship_delay, fee_reimbursement, mid_day_meal |
| Welfare | సంక్షేమం | Welfare | pension_delay, scheme_benefit_delay, ration_card, housing |
| Revenue | రెవెన్యూ | Revenue | land_issue, pattadar_passbook, encroachment, survey |
| Water Supply | నీటి సరఫరా | Panchayat Raj | drinking_water, pipeline_damage, bore_well, water_quality |
| Electricity | విద్యుత్ | Energy | power_cut, new_connection, meter_issue, street_light |
| Roads/Transport | రోడ్లు & రవాణా | Roads & Buildings | road_damage, bridge_issue, bus_service, traffic |
| Other | ఇతరం | General Administration | corruption, staff_behavior, service_delay, other |

### SLA & Escalation
- **Urgent:** 24 hours
- **High:** 48 hours
- **Medium:** 72 hours (default)
- **Low:** 120 hours

Auto-escalation on SLA breach:
```
Level 0: సచివాలయం (Village Secretariat)
    ↓ SLA breach
Level 1: మండల అధికారి (Mandal Officer)
    ↓ SLA breach
Level 2: జిల్లా కలెక్టర్ (District Collector)
    ↓ SLA breach
Level 3: రాష్ట్ర స్థాయి (State Level)
```

### Automated Workers
- **SLA Check:** Every 30 minutes — auto-escalates breached grievances
- **Notifications:** WhatsApp updates on status changes

---

## Feature 4: Daily Task Prioritization

**Problem:** 11 officials manage 34 departments each — decision overload causes burnout. The Jan 2026 People's Pulse survey reported mental health crises and suicides.

**Solution:** AI reads the employee's pending work queue and tells them what to do first — reducing decision overload.

### Capabilities

| Capability | Description | Endpoint |
|-----------|-------------|----------|
| **Daily Plan** | AI-powered prioritized task list for the day | `GET /api/v1/tasks/daily-plan` |
| **Create Tasks** | Manual or auto-generated tasks | `POST /api/v1/tasks/` |
| **Start/Complete** | Track task progress | `POST /api/v1/tasks/{id}/start`, `/complete` |
| **Workload Summary** | Current workload level (light/moderate/heavy/overloaded) | `GET /api/v1/tasks/workload/summary` |
| **List & Filter** | Filter by status, department, due date | `GET /api/v1/tasks/` |

### AI Prioritization Rules
1. Overdue tasks always first
2. Urgent/high priority before medium/low
3. Citizen-facing tasks (scheme_processing, citizen_service) before internal tasks
4. Group by department to reduce context switching
5. Cap at 8 hours (480 minutes) per day to prevent burnout
6. Rule-based fallback when AI is unavailable

### Priority Scoring (0-100)
| Priority | Base Score | Overdue Boost | Due Today | Due in 3 Days |
|----------|-----------|---------------|-----------|---------------|
| Urgent | 90 | +20 (cap 100) | +10 | +5 |
| High | 70 | +20 | +10 | +5 |
| Medium | 50 | +20 | +10 | +5 |
| Low | 30 | +20 | +10 | +5 |

### Workload Levels
| Level | Pending Tasks | Action |
|-------|--------------|--------|
| Light | 0-3 | Normal |
| Moderate | 4-8 | Monitor |
| Heavy | 9-15 | Reduce non-essential |
| Overloaded | 16+ | Escalate to supervisor |

### Task Categories
scheme_processing, field_visit, data_entry, report_writing, grievance_followup, meeting, survey, inspection, citizen_service

### Task Sources
manual, gsws_sync, grievance, scheme_processing, recurring, ai_suggested

### Automated Workers
- **5:30 AM IST:** Create recurring tasks (daily, weekly, monthly, weekdays)
- **6:00 AM IST:** Generate AI daily plans + send via WhatsApp

---

## Supporting Features

### Voice Input (Telugu STT)
- **Whisper large-v3** with Telugu domain vocabulary
- FFmpeg audio conversion (OGG → WAV 16kHz mono)
- Entity extraction: names, age, income, ration card, caste, scheme references
- Telugu number word conversion ("రెండు లక్షలు" → 200000)
- Confidence scoring from Whisper logprobs
- Endpoint: `POST /api/v1/voice/transcribe`

### WhatsApp Integration
- Full Meta Cloud API (text, voice, buttons, lists, documents)
- HMAC-SHA256 signature verification
- Message deduplication (Redis, 5-min window)
- Auto-register employees on first message
- Multi-turn conversation with 30-min session timeout

### Conversation Engine (10 Intents)
| Intent | Telugu Keywords | English Keywords |
|--------|----------------|-----------------|
| scheme_query | పథకం, అర్హత, ప్రయోజనం | scheme, eligibility, benefit |
| eligibility_check | అర్హత ఉందా, వర్తిస్తుందా | eligible, qualify, check |
| form_help | ఫారం, నింపు, సమర్పించు | form, fill, submit, pdf |
| status_check | స్థితి, దరఖాస్తు స్థితి | status, pending, track |
| grievance | ఫిర్యాదు, సమస్య | grievance, complaint, problem |
| task_query | టాస్క్, పని, ఏం చేయాలి | task, daily plan, workload |
| greeting | నమస్కారం, హలో | hi, hello, hey |
| help | సహాయం, ఏం చేయగలవు | help, menu, how to |
| thanks | ధన్యవాదాలు | thanks, great, perfect |
| unclear | (fallback to Claude) | (fallback to Claude) |

### Offline Support
- Offline queue with exponential backoff (5 retries)
- Failed GSWS submissions auto-retried every 5 minutes
- FAQ cache works without connectivity
- Keyword-based intent classification works offline

### Analytics Dashboard
| Metric | Description | Endpoint |
|--------|-------------|----------|
| Secretariat Summary | Queries, forms, time saved per secretariat | `GET /api/v1/analytics/secretariat/{id}/summary` |
| Burnout Report | Weekly hours reduction %, satisfaction scores | `GET /api/v1/analytics/burnout-report` |
| Time Saved | Total hours saved, annual projections, cost savings (INR) | `GET /api/v1/analytics/time-saved` |
| Export | CSV/PDF reports for government review | `GET /api/v1/analytics/export` |

### Knowledge Base (RAG)
- pgvector with 384-dimension embeddings (sentence-transformers)
- Bilingual chunking (Telugu + English, 500 words, 50 overlap)
- Document ingestion: GOs, circulars, scheme guidelines
- Nightly GSWS data sync (2 AM IST)

### Security
- Role-based access (employee, secretariat_admin, district_admin, system_admin)
- Aadhaar hashing (SHA-256, never stored raw)
- PII stripping before all LLM calls
- Phone number masking in logs
- HMAC-SHA256 webhook verification

---

## API Summary (30+ Endpoints)

| Module | Endpoints | Prefix |
|--------|-----------|--------|
| Health | 1 | `/api/v1/health` |
| Schemes | 4 | `/api/v1/schemes` |
| Forms | 4 | `/api/v1/forms` |
| Voice | 1 | `/api/v1/voice` |
| WhatsApp | 2 | `/api/v1/whatsapp` |
| Analytics | 4 | `/api/v1/analytics` |
| Grievances | 8 | `/api/v1/grievances` |
| Tasks | 8 | `/api/v1/tasks` |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Python 3.11+ |
| Database | PostgreSQL 16 + pgvector |
| Cache/Sessions | Redis |
| Task Queue | Celery + Redis |
| AI Reasoning | Claude (Anthropic API) |
| Voice STT | OpenAI Whisper large-v3 |
| Embeddings | sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2) |
| PDF Generation | WeasyPrint + Noto Sans Telugu |
| WhatsApp | Meta Cloud API |
| Government Portal | GSWS AP API |
| Containerization | Docker Compose |
| Monitoring | Prometheus + structlog |

---

## Test Coverage

**159 tests across 11 test files**

| Test File | Tests | Coverage |
|-----------|-------|---------|
| test_scheme_advisor.py | 21 | Scheme matching, search chain, eligibility |
| test_conversation_engine.py | 17 | Intents, multi-turn, greetings, interactive |
| test_form_filler.py | 13 | Templates, extraction, voice entities, PII |
| test_grievance_service.py | 16 | Categories, SLA, AI prompt, model, reference format |
| test_task_service.py | 18 | Priority scoring, rule-based, recurring, workload |
| test_voice_pipeline.py | 11 | Post-processing, entity extraction |
| test_whatsapp.py | 9 | Webhook parsing, intent classification |
| test_analytics.py | 5 | Time saved, burnout, export |
| test_telugu.py | 9 | Digits, language detection, normalization |
| test_security.py | 15 | Aadhaar hashing, PII stripping |
| test_pdf_generator.py | 7 | HTML generation, field rendering |
| test_gsws_bridge.py | 5 | Mock/real modes, status check |
| test_offline_queue.py | 8 | Queue operations, retry logic |

---

## Advanced Features (Production-Grade)

### Rate Limiting
- Redis sliding window counter per user/IP
- Per-endpoint limits (e.g., WhatsApp: 200/min, Grievance filing: 20/min, Exports: 5/hour)
- `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers
- 429 Too Many Requests with Telugu error message
- Fail-open on Redis failure (never blocks legitimate requests)
- Health check endpoints exempt

### Audit Trail (Government Compliance)
- Every create/update/delete/export action logged
- Stores: employee_id, action, resource_type, resource_id, old_values, new_values, IP, timestamp
- Query logs by resource, employee, action, date range
- Employee activity summaries for supervisor review
- Endpoints: `GET /api/v1/audit/logs`, `GET /api/v1/audit/employee/{id}/activity`

### Smart Notifications
- **SLA Warnings**: WhatsApp alert 12 hours before grievance SLA deadline
- **Task Deadline Alerts**: Notify employees about tasks due today
- **Grievance Status Changes**: Real-time status update notifications
- **Daily Summaries**: Morning message with pending tasks, open grievances, deadlines
- Celery beat: SLA warnings (6-hourly), task deadlines (7 AM), summaries (6:30 AM)

### Employee Performance & Supervisor Dashboard
- Per-employee metrics: grievances filed/resolved, tasks completed, response time, satisfaction scores
- Team performance aggregation by secretariat
- Leaderboard ranked by any metric (grievances_resolved, tasks_completed, etc.)
- Period types: daily, weekly, monthly
- Endpoints: `GET /api/v1/performance/employee/{id}`, `/team/{secretariat_id}`, `/leaderboard`

### Duplicate Grievance Detection
- Fuzzy matching using rapidfuzz (token_sort_ratio) on grievance descriptions
- Citizen phone + category matching within 30-day lookback window
- 75% similarity threshold for flagging, 85% for high-confidence duplicates
- Non-blocking: warns but doesn't prevent filing

### Bulk Operations
- `POST /api/v1/grievances/bulk-create` — Up to 50 grievances per batch
- `POST /api/v1/tasks/bulk-create` — Up to 100 tasks per batch
- Returns: created_count, failed_count, detailed error list

### Data Export (Government Reports)
- `GET /api/v1/grievances/export/csv` — Full grievance data with filters
- `GET /api/v1/tasks/export/csv` — Full task data with filters
- Filters: secretariat_id, status, date range, employee_id
- Streaming response for large datasets (up to 5,000 records)
- Columns: Reference Number, Category, Department, Status, Priority, SLA, Resolution, etc.

### Language Switching
- Mid-conversation language switch via keywords
- Telugu: "తెలుగు లో", "telugu please", "భాష మార్చు"
- English: "english lo", "switch to english", "english please"
- Persists preference to employee profile
- All 12 intents support both languages

---

## API Summary (45+ Endpoints)

| Module | Endpoints | Prefix |
|--------|-----------|--------|
| Health | 1 | `/api/v1/health` |
| Schemes | 4 | `/api/v1/schemes` |
| Forms | 4 | `/api/v1/forms` |
| Voice | 1 | `/api/v1/voice` |
| WhatsApp | 2 | `/api/v1/whatsapp` |
| Analytics | 4 | `/api/v1/analytics` |
| Grievances | 11 | `/api/v1/grievances` |
| Tasks | 11 | `/api/v1/tasks` |
| Audit | 2 | `/api/v1/audit` |
| Performance | 3 | `/api/v1/performance` |

---

## Test Coverage

**270 tests across 16 test files — 100% passing**

| Test File | Tests | Coverage |
|-----------|-------|---------|
| test_api_endpoints.py | 32 | FastAPI TestClient for all endpoints |
| test_conversation_handlers.py | 27 | Grievance/task handlers, language switch, edge cases |
| test_service_integration.py | 52 | Service logic, SLA escalation, priority scoring, Celery |
| test_grievance_service.py | 16 | Categories, SLA, AI prompts |
| test_task_service.py | 18 | Priority scoring, rule-based prioritization |
| test_scheme_advisor.py | 21 | RAG pipeline, scheme matching |
| test_conversation_engine.py | 17 | Intent classification, multi-turn |
| test_form_filler.py | 13 | Templates, extraction, voice entities |
| Others (8 files) | 74 | Voice, WhatsApp, PDF, security, Telugu, analytics |

---

## Deployment

```bash
# First-time setup
make setup

# Run all services
make run

# Run tests
make test

# Generate database migrations
make migrate-create msg="initial schema"
make migrate

# Seed scheme data
make seed

# Generate embeddings for RAG
make embed
```
