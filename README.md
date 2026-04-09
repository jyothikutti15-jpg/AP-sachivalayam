# AP Sachivalayam AI Copilot

[![Tests](https://github.com/ap-sachivalayam/copilot/actions/workflows/ci.yml/badge.svg)](https://github.com/ap-sachivalayam/copilot/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

**Telugu-first AI assistant for Andhra Pradesh's 1.3 lakh village secretariat employees across 11,162 secretariats.**

Delivered over WhatsApp. Powered by Claude AI. Handles scheme eligibility, form automation, grievance tracking, task management, voice input, GO/circular search, document checklists, and citizen follow-up reminders.

> Built for the IndiaAI Challenge 2026.

---

## The Problem

Each AP Sachivalayam employee manages **34 government departments**, answers **100+ daily scheme queries from memory**, and processes applications for **33 welfare schemes** — all while tracking grievances, generating reports, and meeting SLA deadlines.

Wrong answers cause citizens to lose benefits. Missed deadlines go unreported. The People's Pulse survey (Jan 2026) found this workload is causing a **mental health crisis** among secretariat staff.

They need AI help — **in Telugu, on WhatsApp, that works offline**.

## The Solution

```
  Citizen visits secretariat
         |
  Employee opens WhatsApp
         |
  Sends voice note in Telugu: "ఈ అమ్మకు 2 పిల్లలు, BC, ₹9,000 ఆదాయం, ఏ పథకాలు వర్తిస్తాయి?"
         |
  AI Copilot responds:
    - 5 eligible schemes identified
    - 8 documents needed (consolidated checklist)
    - Auto-fills Thalliki Vandanam application form
    - Schedules follow-up reminder for missing income certificate
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      WhatsApp Business API                       │
│                (Text · Voice · Interactive Buttons)               │
└──────────────┬─────────────────────────────────┬────────────────┘
               |                                 |
    ┌──────────v───────────┐          ┌──────────v───────────────┐
    │   FastAPI (REST API)  │          │    Celery Workers         │
    │   73 endpoints        │          │    Voice · PDF · SLA      │
    │   Correlation IDs     │          │    Tasks · Reminders      │
    │   Rate Limiting       │          │    Outreach · GSWS Sync   │
    └──────────┬────────────┘          └──────────────────────────┘
               |
    ┌──────────v──────────────────────────────────────────────────┐
    │                       Service Layer                          │
    │  SchemeAdvisor    FormFiller      GrievanceService            │
    │  TaskService      VoicePipeline   ChecklistService            │
    │  CircularService  ReminderService OutreachEngine              │
    └──────────┬───────────────────────────────────┬──────────────┘
               |                                   |
    ┌──────────v───────────┐        ┌──────────────v──────────────┐
    │  Claude AI            │        │  PostgreSQL 16 + pgvector   │
    │  Circuit Breaker      │        │  Redis 7 (Cache/Sessions)   │
    └───────────────────────┘        └─────────────────────────────┘
```

## 10 Features

| # | Feature | What It Does |
|---|---------|-------------|
| 1 | **Scheme Eligibility Checker** | RAG search over 33 schemes — checks eligibility, lists documents, batch mode (50 concurrent) |
| 2 | **Form Auto-Fill & PDF** | Voice/text → AI extracts fields → government-format PDF → submits to GSWS portal |
| 3 | **Grievance Tracker** | AI routes to department, enforces SLA (24-120h), auto-escalates through 4 levels |
| 4 | **Task Prioritizer** | AI daily plan capped at 8 hours, sent via WhatsApp at 6 AM, prevents burnout |
| 5 | **Voice Input (Telugu STT)** | Whisper large-v3 transcribes Telugu, extracts entities (name, age, income, caste) |
| 6 | **Outreach Scanner** | Weekly scan identifies eligible citizens who haven't applied — no one left behind |
| 7 | **Training Quizzes** | AI-generated scenarios from real citizen situations, tracks employee progress |
| 8 | **Document Checklist** | Citizen profile → eligibility across all schemes → consolidated document list |
| 9 | **GO/Circular Knowledge Base** | "What changed in Amma Vodi?" → AI answer citing GO numbers, tracks key changes |
| 10 | **Citizen Reminders** | Auto-scheduled WhatsApp reminders for pending documents, renewals, disbursements |

## Supported Schemes (33)

**Super Six:** Thalliki Vandanam (తల్లికి వందనం) · Annadata Sukhibhava (అన్నదాత సుఖీభవ) · NTR Bharosa Pension · Deepam 2.0 · Stree Shakti · Yuva Galam

**Plus:** Cheyutha · Asara · Bima · Aarogyasri · Kanti Velugu · Kalyanamasthu · Vahana Mitra · Vidya Deevena · Vasathi Deevena · Sampoorna Poshana · Pedalandariki Illu · MGNREGS and 15 more.

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Anthropic API key ([get one here](https://console.anthropic.com))

### Setup

```bash
# Clone the repo
git clone https://github.com/ap-sachivalayam/copilot.git
cd copilot

# Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Start everything (PostgreSQL + pgvector, Redis, FastAPI, Celery worker, Celery beat)
make setup

# Visit the API docs
open http://localhost:8000/docs
```

### Verify

```bash
# Health check
make health

# Run tests (924 tests)
make test

# View logs
make logs
```

### Try It

```bash
# Search schemes
curl -X POST http://localhost:8000/api/v1/schemes/search \
  -H "Content-Type: application/json" \
  -d '{"query": "అమ్మ ఒడి అర్హత ఏమిటి?", "language": "te"}'

# Check eligibility
curl -X POST http://localhost:8000/api/v1/schemes/eligibility-check \
  -H "Content-Type: application/json" \
  -d '{"scheme_code": "THALLIKI-VANDANAM", "citizen_details": {"age": 35, "income": 108000, "children_in_school": 2, "ration_card": "rice"}}'

# Generate document checklist
curl -X POST http://localhost:8000/api/v1/checklist/generate \
  -H "Content-Type: application/json" \
  -d '{"name": "సునీత", "age": 35, "gender": "female", "income": 108000, "caste": "BC", "ration_card": "rice", "has_school_children": true}'

# Run the interactive demo (no Docker needed)
python scripts/demo.py
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | FastAPI 0.115+ · Python 3.11+ · async/await |
| AI | Claude (claude-sonnet-4-6) via Anthropic API |
| Voice | OpenAI Whisper large-v3 + FFmpeg |
| Search | pgvector (384-D embeddings) + sentence-transformers |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| Task Queue | Celery 5.4 + Redis |
| PDF | WeasyPrint + Noto Sans Telugu |
| WhatsApp | Meta Cloud API v21 |
| Govt Portal | GSWS AP API |
| Monitoring | Prometheus + structlog |
| Deploy | Docker Compose |

## Project Structure

```
ap-sachivalayam-copilot/
|-- app/
|   |-- api/v1/           # 17 route modules, 73 endpoints
|   |-- core/             # Circuit breaker, security, Telugu utils
|   |-- data/
|   |   |-- schemes/      # 33 scheme JSONs with real criteria
|   |   |-- templates/    # 10 government form templates
|   |   +-- scheme_faqs.json
|   |-- models/           # 20+ SQLAlchemy ORM models
|   |-- schemas/          # Pydantic request/response schemas
|   |-- services/         # 15 service modules (AI, forms, grievance, etc.)
|   +-- workers/          # 7 Celery workers + beat schedule
|-- scripts/              # Seed data, embeddings, onboarding, demo
|-- tests/                # 30 test files, 924 tests
|-- docs/                 # Features, competitions, impact, testing guides
|-- Dockerfile
|-- docker-compose.yml
|-- Makefile
+-- pyproject.toml
```

## Test Coverage

**924 tests across 30 files — all passing**

```bash
make test          # Full suite
make test-fast     # Skip slow integration tests
```

Tests use **real AP government data** — actual scheme criteria from official portals (thallikivandanam.com, sspensions.ap.gov.in, spandana.ap.gov.in), real citizen profiles, real grievance categories.

| Test Area | Tests |
|---|---|
| End-to-end (all 10 features) | 65 |
| API endpoints | 32 |
| Service integration | 52 |
| Real-world scenarios | 75+ |
| Scheme advisor / RAG | 21 |
| Grievance + Task services | 34 |
| Document checklist | 14 |
| GO/Circulars | 14 |
| Citizen reminders | 16 |
| Voice + Telugu + Security | 30+ |

## Security

- **Aadhaar:** bcrypt hashed (rounds=12, random salt) — never stored raw, only last 4 digits in responses
- **PII:** Stripped from all LLM calls (Aadhaar + phone numbers)
- **Auth:** JWT + bcrypt passwords + 5-level RBAC
- **WhatsApp:** HMAC-SHA256 webhook signature verification
- **Audit:** Every action logged with old/new values, IP, timestamp

## Key Makefile Commands

```bash
make setup          # First-time: Docker + seed + migrations
make run            # Start all services (background)
make run-dev        # Start with live reload
make test           # Run 924 tests
make lint           # Ruff linter
make seed           # Reload scheme data
make embed          # Generate RAG embeddings
make health         # API health check
make logs           # Application logs
make logs-celery    # Worker logs
make clean          # Remove containers + volumes
```

## Impact

| Metric | Scale |
|---|---|
| Secretariats | 11,162 across 26 districts |
| Employees | 1,30,000 |
| Citizens served | 4.9 crore |
| Schemes | 33 with real eligibility criteria |
| Time saved | ~2 hours/employee/day (projected) |
| Annual savings | ~Rs 450 crore (projected) |

See [docs/IMPACT.md](docs/IMPACT.md) for detailed methodology.

## Documentation

- [Features (all 10)](docs/FEATURES.md) — complete feature specs with endpoints
- [Impact Projections](docs/IMPACT.md) — time saved, cost analysis, methodology
- [Competition Guide](docs/COMPETITIONS.md) — 20 competitions with application strategy
- [Testing Guide](docs/TESTING_WITH_REAL_DATA.md) — how tests use real AP data
- [Live Test Results](docs/LIVE_TEST_RESULTS.md) — actual test run output

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-scheme`)
3. Run tests (`make test`)
4. Run linter (`make lint`)
5. Submit a pull request

## License

[MIT](LICENSE)

---

Built with care for the 1.3 lakh secretariat employees who serve 4.9 crore citizens of Andhra Pradesh.
