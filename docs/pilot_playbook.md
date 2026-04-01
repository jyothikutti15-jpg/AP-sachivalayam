# AP Sachivalayam AI Copilot — Pilot Playbook

## Pilot Overview
- **Target**: 5 secretariats across 3 districts (NTR, Tirupati, Srikakulam)
- **Employees**: ~55 (11 per secretariat)
- **Duration**: 6 weeks (2 weeks baseline + 4 weeks with copilot)
- **Goal**: Demonstrate measurable burnout reduction and faster citizen service

## Pilot Secretariats

| # | Secretariat | District | Type | Connectivity |
|---|------------|----------|------|-------------|
| 1 | Vijayawada Secretariat 1 | NTR | Urban | Good |
| 2 | Vijayawada Secretariat 2 | NTR | Semi-urban | Normal |
| 3 | Tirupati Secretariat 1 | Tirupati | Urban | Good |
| 4 | Srikakulam Secretariat 1 | Srikakulam | Rural | Low |
| 5 | Narasannapeta Secretariat | Srikakulam | Rural | Low |

## Setup Guide

### 1. Infrastructure (Day 1)

```bash
# Clone and configure
git clone <repo-url>
cd ap-sachivalayam-copilot
cp .env.example .env

# Edit .env with real credentials:
# - ANTHROPIC_API_KEY (required)
# - WHATSAPP_PHONE_NUMBER_ID (from Meta Business)
# - WHATSAPP_ACCESS_TOKEN (from Meta Business)
# - WHATSAPP_VERIFY_TOKEN (your custom token)

# Start all services
docker-compose up -d

# Verify all services running
docker-compose ps
curl http://localhost:8000/api/v1/health
```

### 2. Database Setup (Day 1)

```bash
# Run migrations
docker-compose exec app alembic upgrade head

# Seed data: 30 schemes + FAQs + 5 pilot secretariats + 10 form templates
docker-compose exec app python scripts/seed_db.py

# Generate embeddings for RAG (takes ~5 min)
docker-compose exec app python scripts/generate_embeddings.py

# Verify
docker-compose exec app python scripts/generate_embeddings.py --stats
```

### 3. WhatsApp Business Setup (Day 1-2)

1. Create Meta Business account at business.facebook.com
2. Set up WhatsApp Business API (Cloud API)
3. Register phone number for the copilot
4. Configure webhook URL: `https://your-domain.com/api/v1/whatsapp/webhook`
5. Set verify token (same as WHATSAPP_VERIFY_TOKEN in .env)
6. Subscribe to "messages" webhook field

### 4. Employee Onboarding (Day 3-5)

For each secretariat:
1. Collect employee phone numbers (WhatsApp-registered)
2. Add to the system:
```bash
# Bulk onboard via script (or employees self-register on first message)
docker-compose exec app python scripts/onboard_employees.py --csv employees.csv
```
3. Send welcome message to each employee:
   - Employee sends "Hi" to the copilot WhatsApp number
   - Copilot responds with greeting + menu
   - Employee is auto-registered

### 5. Training (Day 3-5)

No formal training needed — but share this quick guide via WhatsApp group:

```
🤖 AP సచివాలయం AI Copilot — Quick Start

1. పథకం గురించి తెలుసుకోవాలంటే:
   → పథకం పేరు టైప్ చేయండి (ఉదా: "అమ్మ ఒడి అర్హత?")

2. ఫారం నింపాలంటే:
   → "ఫారం" అని టైప్ చేయండి → citizen details voice note పంపండి

3. Status check:
   → "స్థితి" + Application ID టైప్ చేయండి

4. Voice notes:
   → Telugu లో voice note పంపండి — AI transcribe చేసి answer ఇస్తుంది

5. Help:
   → "help" అని టైప్ చేయండి
```

## Baseline Data Collection (Weeks 1-2)

Before enabling the copilot, collect baseline metrics:

| Metric | How to Measure | Target |
|--------|---------------|--------|
| Avg queries/day per employee | Manual log sheet | Baseline |
| Avg time per scheme query | Time observation (10 samples) | ~15 min |
| Avg time per form fill | Time observation (10 samples) | ~30 min |
| Daily working hours | Self-report survey | ~9-10 hrs |
| Employee satisfaction | 1-5 scale survey | Baseline |
| Citizen wait time | Observation at secretariat | ~20-30 min |

## Copilot Phase (Weeks 3-6)

### Monitoring Dashboard

Access at: `http://your-server:8000/docs` → Analytics endpoints

Key API calls:
```bash
# Secretariat summary
curl "http://localhost:8000/api/v1/analytics/secretariat/1/summary?start_date=2026-04-01&end_date=2026-04-30"

# Burnout report
curl "http://localhost:8000/api/v1/analytics/burnout-report?week_start=2026-04-07"

# Time saved (district-level)
curl "http://localhost:8000/api/v1/analytics/time-saved?start_date=2026-04-01&end_date=2026-04-30&district=NTR"

# Export CSV
curl "http://localhost:8000/api/v1/analytics/export?start_date=2026-04-01&end_date=2026-04-30&format=csv" -o report.csv
```

### Weekly Check-ins

Every Friday:
1. Pull analytics from dashboard
2. Check offline queue stats
3. Note any scheme data that needs updating
4. Collect employee feedback (1-5 rating via WhatsApp)
5. Report to pilot coordinator

## Success Metrics

| Metric | Before | Target After | How We Prove It |
|--------|--------|-------------|----------------|
| Time per scheme query | 15 min | 2 min | Copilot response time logs |
| Time per form fill | 30 min | 5 min | Form auto-fill timestamps |
| Daily working hours | 10 hrs | 8 hrs | After-6pm message drop |
| Employee satisfaction | 2.1/5 | 4.0/5 | Weekly WhatsApp survey |
| Citizen wait time | 25 min | 10 min | Observation study |
| Scheme awareness | 30% | 85% | Unique schemes queried |

## Scaling Plan

If pilot succeeds (4+ weeks of positive metrics):

| Phase | Scope | Timeline |
|-------|-------|----------|
| Pilot | 5 secretariats, 55 employees | 6 weeks |
| District rollout | 3 districts, ~500 secretariats | 3 months |
| State rollout | All 13 districts, 11,162 secretariats | 6 months |
| Full scale | 1.3 lakh employees | 12 months |

Infrastructure scaling:
- Pilot: 1 VM (t3.xlarge) + 1 GPU (g4dn.xlarge for Whisper)
- District: ECS cluster, RDS PostgreSQL, ElastiCache
- State: Full Kubernetes deployment on NIC cloud

## Troubleshooting

| Issue | Solution |
|-------|---------|
| Bot not responding | Check `docker-compose logs app` |
| GSWS submission failing | Auto-queued for retry. Check `/api/v1/health` |
| Voice not working | Verify ffmpeg installed: `docker-compose exec app ffmpeg -version` |
| Telugu garbled | Check UTF-8 encoding in database |
| Rate limited by Claude | Reduce concurrency in .env, enable FAQ cache |
| Low connectivity area | Copilot auto-falls back to cached FAQs + keyword search |

## Contacts

- Technical Lead: [Your Name]
- RTGS Coordinator: [RTGS Contact]
- District Collector Office: [DC Contact]
- IndiaAI Challenge Submission: [Portal Link]
