# AP Sachivalayam AI Copilot — Components Documentation

> Complete reference of every component in the system — API routes, services, models, workers, core utilities, data, and infrastructure.

## Table of Contents

1. [System Overview](#system-overview)
2. [API Layer (19 modules, 73 endpoints)](#api-layer)
3. [Service Layer (26 services)](#service-layer)
4. [Data Models (19 models)](#data-models)
5. [Pydantic Schemas](#pydantic-schemas)
6. [Core Utilities](#core-utilities)
7. [Celery Workers (9 modules, 8 scheduled tasks)](#celery-workers)
8. [Data Files](#data-files)
9. [Infrastructure](#infrastructure)
10. [Dependency Graph](#dependency-graph)

---

## System Overview

```
┌────────────────────────────────────────────────────────────────┐
│                     FastAPI Application                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Middleware: Correlation ID → Rate Limit → CORS         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              |                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  API Layer (19 route modules, 73 endpoints)             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              |                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Service Layer (26 services)                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              |                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Core Utilities (security, circuit breaker, language)  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              |                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Data Layer (SQLAlchemy models + Pydantic schemas)      │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬───────────────────────────────┘
                                 |
   ┌────────────────────┬────────┼─────────┬─────────────────┐
   |                    |        |         |                 |
┌──v───────┐  ┌─────────v─┐  ┌───v──────┐  ┌v──────────┐  ┌──v─────────┐
│ Claude   │  │PostgreSQL │  │  Redis   │  │ Celery    │  │  WhatsApp  │
│ Sonnet   │  │ pgvector  │  │          │  │ Workers   │  │  Business  │
└──────────┘  └───────────┘  └──────────┘  └───────────┘  └────────────┘
```

---

## API Layer

**Location:** `app/api/v1/`

Registration: `app/api/v1/router.py`

### Route Modules (19 files)

| # | Module | File | Prefix | Endpoints | Purpose |
|---|--------|------|--------|-----------|---------|
| 1 | Health | `health.py` | `/health` | 1 | Health check (DB, Redis, circuit breaker status) |
| 2 | WhatsApp | `whatsapp.py` | `/whatsapp` | 2 | Webhook verification + message receiving |
| 3 | Schemes | `schemes.py` | `/schemes` | 5 | List, get, search, eligibility check, batch check |
| 4 | Forms | `forms.py` | `/forms` | 4 | Auto-fill, PDF, GSWS submit, templates |
| 5 | Voice | `voice.py` | `/voice` | 1 | Telugu STT transcription |
| 6 | Dashboard | `dashboard.py` | `/analytics` | 4 | Secretariat summary, burnout, time saved, export |
| 7 | Grievances | `grievances.py` | `/grievances` | 11 | File, track, update, comment, stats, bulk, export |
| 8 | Tasks | `tasks.py` | `/tasks` | 11 | Create, daily plan, start/complete, workload, bulk |
| 9 | Audit | `audit.py` | `/audit` | 2 | Audit logs, employee activity |
| 10 | Performance | `performance.py` | `/performance` | 3 | Employee, team, leaderboard |
| 11 | Citizens | `citizens.py` | `/citizens` | 2 | Citizen lookup + beneficiary registration |
| 12 | Supervisor | `supervisor.py` | `/supervisor` | 6 | Mandal, district, SLA alerts, low performing |
| 13 | Training | `training.py` | `/training` | 4 | Scenario, submit, progress, leaderboard |
| 14 | Outreach | `outreach.py` | `/outreach` | 7 | Scan, notify, apply, eligible schemes |
| 15 | **Checklist** | `checklist.py` | `/checklist` | 1 | Document checklist generator |
| 16 | **Circulars** | `circulars.py` | `/circulars` | 5 | GO/circular RAG search + auto-summarize |
| 17 | **Reminders** | `reminders.py` | `/reminders` | 6 | Citizen follow-up reminders |
| 18 | **Languages** | `languages.py` | `/languages` | 4 | Language + state discovery |
| 19 | **Citizen Self-Service** | `citizen_selfservice.py` | `/citizen` | varies | Citizen-facing endpoints |

**Total: 73+ endpoints across 17 prefixes**

---

## Service Layer

**Location:** `app/services/`

26 service modules implementing business logic, separated from API routing.

### Core AI Services

| Service | File | Responsibility |
|---------|------|---------------|
| `LLMRouter` | `llm_service.py` | Claude API wrapper with circuit breaker, PII stripping, multi-language error messages. Methods: `call_claude()`, `call_claude_structured()`, `call_claude_vision()`, `call_claude_with_history()` |
| `SchemeAdvisor` | `scheme_advisor.py` | RAG pipeline over 33 schemes. 4-level search chain: Redis cache → DB FAQs → pgvector → keyword fallback. Batch eligibility checking with concurrent LLM calls |
| `ConversationEngine` | `conversation_engine.py` | WhatsApp message router. Intent detection, session management, multi-turn context |
| `VoicePipeline` | `voice_pipeline.py` | Whisper STT with per-language vocabulary. FFmpeg audio conversion, entity extraction, PII detection |
| `FormFiller` | `form_filler.py` | Claude-based form field extraction from text/voice. Confidence scoring per field |
| `OCRService` | `ocr_service.py` | Claude Vision document analysis. Aadhaar card, ration card field extraction |

### Feature Services

| Service | File | Responsibility |
|---------|------|---------------|
| `GrievanceService` | `grievance_service.py` | Grievance CRUD, auto-routing, SLA tracking, 4-level escalation, AI suggestions |
| `TaskService` | `task_service.py` | Task CRUD, AI daily planning, priority scoring, workload classification, recurring tasks |
| `ChecklistService` | `checklist_service.py` | Document checklist generator across all eligible schemes with localized document names |
| `CircularService` | `circular_service.py` | GO/circular RAG search, auto-summarization, key changes tracking |
| `ReminderService` | `reminder_service.py` | Citizen follow-up reminder scheduling with multi-language templates |
| `OutreachEngine` | `outreach_engine.py` | Rule-based beneficiary-to-scheme matching, confidence scoring |
| `TrainingService` | `training_service.py` | AI-generated training scenarios, response evaluation |

### Infrastructure Services

| Service | File | Responsibility |
|---------|------|---------------|
| `PDFGenerator` | `pdf_generator.py` | WeasyPrint-based PDF generation with Noto Sans Telugu font |
| `WhatsAppService` | `whatsapp_service.py` | Meta Cloud API client (send text, buttons, lists, media, HMAC verification) |
| `GSWSBridge` | `gsws_bridge.py` | GSWS portal API client with mock fallback when credentials missing |
| `NotificationService` | `notification_service.py` | Multi-channel notifications (WhatsApp, SMS, email) |
| `OfflineQueue` | `offline_queue.py` | Offline message queuing with exponential backoff retry |

### Analytics & Management

| Service | File | Responsibility |
|---------|------|---------------|
| `AnalyticsService` | `analytics_service.py` | Burnout reports, time saved, secretariat summaries |
| `SupervisorService` | `supervisor_service.py` | Mandal/district rollups, SLA breach alerts, low-performing alerts |
| `PerformanceService` | `performance_service.py` | Individual/team metrics, leaderboards |
| `AuditService` | `audit_service.py` | Compliance audit trail logging |
| `ExportService` | `export_service.py` | CSV/PDF exports with filters |
| `DuplicateDetector` | `duplicate_detector.py` | Fuzzy matching with rapidfuzz for grievance deduplication |
| `KnowledgeIndexer` | `knowledge_indexer.py` | Embedding generation for RAG (sentence-transformers) |

---

## Data Models

**Location:** `app/models/`

SQLAlchemy 2.0 async ORM. 19 model files, 22 tables total.

### User & Identity

| Model | File | Table | Purpose |
|-------|------|-------|---------|
| `Secretariat` | `user.py` | `secretariats` | Village/ward secretariat registry (11,162 in AP) |
| `Employee` | `user.py` | `employees` | Secretariat staff — phone, designation, role, language |
| `Citizen` | `citizen.py` | `citizens` | Citizen records — phone, demographics, Aadhaar hash |
| `Beneficiary` | `beneficiary.py` | `beneficiaries` | Scheme beneficiary profile for outreach matching |

### Schemes & Knowledge

| Model | File | Table | Purpose |
|-------|------|-------|---------|
| `Scheme` | `scheme.py` | `schemes` | 33 schemes with eligibility JSONB, required documents, GO reference. Has `state_code` for multi-state support |
| `SchemeFAQ` | `scheme.py` | `scheme_faqs` | Bilingual Q&A with frequency counter |
| `KBDocument` | `knowledge.py` | `kb_documents` | Source documents (scraped, manually added) |
| `KBChunk` | `knowledge.py` | `kb_chunks` | pgvector embeddings (384-D) for semantic search |
| `Circular` | `circular.py` | `circulars` | GOs/circulars with impact level, key changes, scheme linkage |

### Conversations

| Model | File | Table | Purpose |
|-------|------|-------|---------|
| `ChatSession` | `interaction.py` | `chat_sessions` | WhatsApp conversation session |
| `Message` | `interaction.py` | `messages` | Individual messages with intent + confidence |

### Forms

| Model | File | Table | Purpose |
|-------|------|-------|---------|
| `FormTemplate` | `form.py` | `form_templates` | 10 AP govt form templates with bilingual field labels |
| `FormSubmission` | `form.py` | `form_submissions` | Auto-filled form submissions with confidence scores, GSWS ID |

### Grievances & Tasks

| Model | File | Table | Purpose |
|-------|------|-------|---------|
| `Grievance` | `grievance.py` | `grievances` | Citizen grievances with SLA tracking, escalation level |
| `GrievanceComment` | `grievance.py` | `grievance_comments` | Comment thread on grievances |
| `Task` | `task.py` | `tasks` | Employee tasks with AI priority reasoning |
| `DailyPlan` | `task.py` | `daily_plans` | AI-generated daily plans sent via WhatsApp |

### Outreach & Reminders

| Model | File | Table | Purpose |
|-------|------|-------|---------|
| `OutreachRecord` | `outreach.py` | `outreach_records` | Identified citizen-scheme matches with status workflow |
| `CitizenReminder` | `reminder.py` | `citizen_reminders` | Scheduled WhatsApp follow-up reminders |

### Analytics & Compliance

| Model | File | Table | Purpose |
|-------|------|-------|---------|
| `DailyMetric` | `analytics.py` | `daily_metrics` | Per-employee daily counters |
| `BurnoutIndicator` | `analytics.py` | `burnout_indicators` | Weekly hours before/after comparison |
| `EmployeePerformance` | `employee_performance.py` | `employee_performance` | Period-based performance aggregates |
| `AuditLog` | `audit.py` | `audit_logs` | Action-level audit trail with old/new values |
| `TrainingSession` | `training.py` | `training_sessions` | Training scenario responses and scores |
| `OfflineQueueItem` | `offline.py` | `offline_queue_items` | Offline message retry queue |

### Base

| Component | File | Purpose |
|-----------|------|---------|
| `Base` | `base.py` | Declarative base for all models |
| `TimestampMixin` | `base.py` | Auto `created_at` + `updated_at` columns |

---

## Pydantic Schemas

**Location:** `app/schemas/`

Request/response validation layer.

| File | Key Schemas |
|------|-------------|
| `scheme.py` | `SchemeResponse`, `SchemeSearchRequest/Response`, `EligibilityCheckRequest/Response`, `BatchEligibilityItem/Response` |
| `grievance.py` | `GrievanceCreateRequest`, `GrievanceResponse`, `GrievanceUpdateRequest`, `GrievanceAISuggestResponse` |
| `task.py` | `TaskCreateRequest`, `TaskResponse`, `DailyPlanResponse`, `PrioritizedTask`, `WorkloadSummaryResponse` |
| `checklist.py` | `CitizenProfile`, `DocumentChecklistResponse`, `SchemeDocumentGroup`, `DocumentItem` |
| `circular.py` | `CircularCreate`, `CircularResponse`, `CircularSearchRequest/Response`, `CircularSummaryRequest` |
| `reminder.py` | `ReminderCreate`, `ReminderResponse`, `ReminderUpdate`, `AutoReminderRequest`, `ReminderStatsResponse` |
| `voice.py` | `TranscriptionResponse` |
| `citizen.py` | Citizen-related request/response schemas |
| `outreach.py` | `OutreachRecord` schemas |
| `ocr.py` | OCR document extraction schemas |
| `supervisor.py` | Supervisor dashboard response schemas |
| `training.py` | Training scenario and response schemas |

---

## Core Utilities

**Location:** `app/core/`

| File | Component | Purpose |
|------|-----------|---------|
| `security.py` | `hash_aadhaar()`, `mask_aadhaar()`, `strip_pii()` | bcrypt (rounds=12) Aadhaar hashing, last-4 masking, PII stripping before LLM calls |
| `language_config.py` | `SUPPORTED_LANGUAGES`, `SUPPORTED_STATES`, `REMINDER_TEMPLATES_I18N`, `COMMON_DOCUMENTS_I18N` | Multi-language (7 langs) and multi-state (8 states) configuration registry |
| `telugu.py` | `normalize_telugu_text()`, `fuzzy_match_scheme()`, `detect_language()`, `split_sentences()` | Telugu utilities + backward-compat wrapper for generic language processor |
| `circuit_breaker.py` | `get_circuit_breaker()`, `CircuitOpenError` | Claude API circuit breaker (CLOSED/OPEN/HALF-OPEN) with 5-failure threshold, 60s recovery |
| `rate_limiter.py` | `RateLimitMiddleware` | Redis sliding window rate limiter (fail-open on Redis errors) |
| `correlation.py` | `CorrelationIdMiddleware` | UUID4 correlation ID injected into every log line |

---

## Celery Workers

**Location:** `app/workers/`

### Configuration

| File | Purpose |
|------|---------|
| `celery_app.py` | Celery app config, retry policy, beat schedule |

### Worker Modules (9 files)

| File | Tasks | Retry Policy |
|------|-------|--------------|
| `voice_transcription.py` | `transcribe_voice_note()`, `process_offline_queue()` | 30s base, 5min max, 3 retries |
| `form_generation.py` | `generate_form_pdf()` | 30s base, 5min max, 3 retries |
| `grievance_escalation.py` | `check_grievance_sla()`, `send_grievance_notification()` | 60s base, 60min max, 3 retries |
| `task_scheduler.py` | `create_recurring_tasks()`, `generate_daily_plans()` | 60s base, 60min max, 3 retries |
| `knowledge_sync.py` | `sync_gsws_data()`, `aggregate_daily_metrics()` | 60s base, 60min max, 3 retries |
| `outreach_scanner.py` | `scan_outreach()` | 60s base, 60min max, 2 retries |
| `reminder_sender.py` | `send_due_reminders()` | 30s base, 5min max, 3 retries |

### Beat Schedule (8 scheduled tasks)

| Schedule | Task | Description |
|----------|------|-------------|
| Every 5 min | `process-offline-queue` | Retry failed GSWS submissions |
| Every 30 min | `check-grievance-sla` | Auto-escalate SLA breaches |
| 2:00 AM IST | `nightly-gsws-sync` | Pull latest GSWS data |
| 5:30 AM IST | `create-recurring-tasks` | Spawn daily/weekly/monthly tasks |
| 6:00 AM IST | `generate-daily-plans` | AI daily plans → WhatsApp |
| **8:30 AM IST** | `send-citizen-reminders` | **Send due follow-up reminders** |
| 11:30 PM IST | `daily-metrics-aggregation` | Compute performance metrics |
| Sunday 3 AM | `scan-outreach-weekly` | Beneficiary-to-scheme matching |

---

## Data Files

**Location:** `app/data/`

### Scheme Data

| File/Folder | Contents | Count |
|-------------|----------|-------|
| `schemes/*.json` | Individual scheme JSON files with real AP govt eligibility criteria | 33 files |
| `scheme_faqs.json` | Bilingual FAQs keyed by scheme code | 10+ schemes |
| `templates/form_templates.json` | 10 form templates with bilingual field labels | 10 templates |
| `telugu_prompts/*.txt` | Claude system prompts for Telugu responses | 9 files |
| `training/scenarios.json` | Training scenarios for employee learning | Scenarios |

### Super Six Schemes (TDP Government Flagship)

| Code | Name | Benefit |
|------|------|---------|
| `THALLIKI-VANDANAM` | తల్లికి వందనం | Rs 15,000/year per school child |
| `ANNADATA-SUKHIBHAVA` | అన్నదాత సుఖీభవ | Rs 20,000/year for farmers |
| `NTR-BHAROSA-PENSION` | NTR భరోసా పెన్షన్ | Rs 4,000-15,000/month (12 categories) |
| `DEEPAM-2` | దీపం 2.0 | 3 free LPG cylinders/year |
| `STREE-SHAKTI` | స్త్రీ శక్తి | Free bus travel for women |
| `YUVA-GALAM` | యువ గళం | Rs 3,000/month unemployment allowance |

---

## Infrastructure

### Dependency Injection

**Location:** `app/dependencies.py`

| Component | Purpose |
|-----------|---------|
| `engine` | SQLAlchemy async engine (auto-converts postgresql:// to postgresql+asyncpg://, sets ssl=True for Neon/Supabase/Render) |
| `async_session_factory` | AsyncSession factory for FastAPI `get_db()` dependency |
| `AsyncSessionLocal` | Alias used by Celery workers |
| `redis_client` | aioredis client (decode_responses=True) |
| `get_db()` | FastAPI dependency with auto commit/rollback |
| `get_redis()` | FastAPI dependency for Redis access |

### Configuration

**Location:** `app/config.py`

Uses `pydantic-settings` with `.env` file support.

| Setting | Default | Env Var |
|---------|---------|---------|
| `app_env` | `development` | `APP_ENV` |
| `secret_key` | `change-me` | `SECRET_KEY` |
| `database_url` | localhost PostgreSQL | `DATABASE_URL` |
| `redis_url` | localhost Redis | `REDIS_URL` |
| `anthropic_api_key` | empty | `ANTHROPIC_API_KEY` |
| `claude_model` | `claude-sonnet-4-6` | `CLAUDE_MODEL` |
| `state_code` | `AP` | `STATE_CODE` |
| `default_language` | `te` | `DEFAULT_LANGUAGE` |
| `whisper_model_size` | `large-v3` | `WHISPER_MODEL_SIZE` |
| `voice_max_file_size_mb` | 25 | `VOICE_MAX_FILE_SIZE_MB` |
| `claude_circuit_failure_threshold` | 5 | `CLAUDE_CIRCUIT_FAILURE_THRESHOLD` |
| `claude_circuit_recovery_timeout` | 60 | `CLAUDE_CIRCUIT_RECOVERY_TIMEOUT` |
| `celery_broker_url` | localhost Redis | `CELERY_BROKER_URL` |
| `celery_result_backend` | localhost Redis | `CELERY_RESULT_BACKEND` |

**Property:** `async_database_url` — auto-strips `sslmode`, `channel_binding` params that asyncpg rejects.

### FastAPI App

**Location:** `app/main.py`

| Component | Purpose |
|-----------|---------|
| `lifespan()` | Startup: init database, seed schemes (idempotent), warm FAQ cache, verify DB/Redis connections. Shutdown: dispose engine, close Redis |
| `_init_database()` | Auto-creates tables via `Base.metadata.create_all()`, enables pgvector extension, seeds 33 schemes + FAQs + 10 templates on first startup |
| `_warm_faq_cache()` | Pre-loads top 200 FAQs into Redis cache |
| `REQUEST_COUNT`, `RESPONSE_TIME` | Prometheus counters and histograms |
| Middleware stack | Correlation ID → Rate Limit → CORS |

### Deployment

| File | Purpose |
|------|---------|
| `Dockerfile` | Python 3.11-slim base with WeasyPrint dependencies, FFmpeg |
| `docker-compose.yml` | Local dev: app, PostgreSQL (ankane/pgvector), Redis 7, Celery worker, Celery beat |
| `render.yaml` | Render Blueprint with web service, Celery worker/beat, Redis |
| `scripts/render_start.sh` | Render startup script (optional, main.py handles auto-init) |
| `Makefile` | 15 commands (setup, run, test, lint, seed, embed, migrate, logs) |
| `alembic/versions/001_initial_schema.py` | Initial database migration (22 tables) |
| `.github/workflows/ci.yml` | GitHub Actions: lint (ruff) + test (pytest) + security scan |

---

## Dependency Graph

### Request Flow (Scheme Search Example)

```
HTTP POST /api/v1/schemes/search
    |
    v
app/api/v1/router.py            (route registration)
    |
    v
app/api/v1/schemes.py           (endpoint handler)
    |
    v
app/services/scheme_advisor.py  (RAG pipeline)
    |
    +--> app/core/telugu.py     (normalize Telugu text)
    |
    +--> dependencies.redis     (Redis FAQ cache lookup)
    |
    +--> app/models/scheme.py   (DB query for FAQs)
    |
    +--> app/models/knowledge.py (pgvector semantic search)
    |
    +--> app/services/llm_service.py
             |
             +--> app/core/security.py  (PII stripping)
             |
             +--> app/core/circuit_breaker.py
             |
             +--> Claude API
             |
             +--> app/core/language_config.py (error messages)
    |
    v
Response → Rate Limiter → Correlation ID → CORS → Client
```

### Background Task Flow (Daily Plan Example)

```
Celery Beat (6:00 AM IST)
    |
    v
app/workers/task_scheduler.py::generate_daily_plans
    |
    +--> Fetch all active employees (app/models/user.py)
    |
    +--> For each employee:
         |
         +--> app/services/task_service.py::get_daily_plan
         |       |
         |       +--> Fetch pending tasks
         |       |
         |       +--> app/services/llm_service.py (Claude prioritization)
         |       |
         |       +--> Save DailyPlan (app/models/task.py)
         |
         +--> app/services/whatsapp_service.py (send via Meta API)
```

### Data Seeding Flow (Startup)

```
FastAPI startup (lifespan)
    |
    v
_init_database()
    |
    +--> CREATE EXTENSION IF NOT EXISTS vector
    |
    +--> Base.metadata.create_all() → 22 tables
    |
    +--> Check if Scheme table has data
    |    (if yes, skip seeding)
    |
    +--> Load app/data/schemes/*.json → 33 Scheme rows
    |
    +--> Load app/data/scheme_faqs.json → FAQ rows
    |
    +--> Load app/data/templates/form_templates.json → 10 FormTemplate rows
    |
    v
_warm_faq_cache()
    |
    +--> Load top 200 FAQs into Redis
```

---

## File Count Summary

| Layer | File Count | Lines (approx) |
|-------|-----------|----------------|
| API routes | 19 | ~2,500 |
| Services | 26 | ~6,000 |
| Models | 19 | ~1,500 |
| Schemas | 12 | ~1,000 |
| Core utilities | 6 | ~1,200 |
| Workers | 9 | ~1,500 |
| Data (JSON/TXT) | 50+ | ~5,000 |
| Tests | 28 | ~10,000 |
| **Total source** | **~170 files** | **~28,000 lines** |

---

## Related Documentation

- [FEATURES.md](FEATURES.md) — Complete feature specs with endpoints
- [IMPACT.md](IMPACT.md) — Impact projections and ROI methodology
- [COMPETITIONS.md](COMPETITIONS.md) — Competition application guide
- [README.md](../README.md) — Quick start and overview
