# Google for Startups Accelerator: AI First (India) — Application Guide

> **DEADLINE: April 19, 2026** (18 days from today)
> **Program:** 3-month equity-free accelerator, bootcamp in Bengaluru (June), Demo Day (October)

---

## Step 1: Open the Application Form

**Direct Application Link:**
https://docs.google.com/forms/d/e/1FAIpQLSe7aNTQze5Rcbkl22Igo2IVtPgRkfS0wXyWH3HXOJsW9ELSwA/viewform?usp=pp_url&entry.877187925=India&entry.1523595543=India&entry.1569650440=India

**Official Program Page:**
https://startup.google.com/programs/accelerator/india/

---

## Step 2: Eligibility Checklist

Before applying, confirm you meet these:

- [ ] **Stage:** Seed to Series A (pre-seed / bootstrapped may also qualify if you have traction)
- [ ] **Location:** Headquartered in India
- [ ] **AI-First:** Core product uses AI/ML (your copilot uses Claude, Whisper, pgvector RAG — this qualifies)
- [ ] **Past idea stage:** Some customer validation or market traction (your 270 tests + pilot playbook show readiness)
- [ ] **Founder commitment:** CEO/CTO available for 1-week Bengaluru bootcamp (June) + monthly sessions until October
- [ ] **Focus area match:** At least one of:
  - [x] **Sovereign AI** — Telugu-first, AP-specific localized model ← YOUR PRIMARY FIT
  - [x] **Agentic AI** — Grievance workflow, task prioritization, SLA enforcement
  - [x] **Multimodal AI** — Voice (Whisper) + text + interactive buttons

---

## Step 3: What the Application Asks

Based on the Google Form and selection criteria, prepare answers for these sections:

### A. Company Information
| Field | Your Answer |
|-------|-------------|
| Company Name | AP Sachivalayam AI Copilot (or your registered entity name) |
| Website | Your deployed URL or GitHub repo link |
| Founded | [Your founding date] |
| Funding Stage | Seed / Pre-seed / Bootstrapped |
| Total Funding Raised | [Amount or "Bootstrapped"] |
| Number of Employees | [Count] |
| Headquarters | [Your city, India] |

### B. Product & Technology
| Question | How to Answer |
|----------|---------------|
| **What does your startup do?** | "AI copilot for Andhra Pradesh's 1.3 lakh village secretariat employees. Telugu-first WhatsApp assistant that handles scheme eligibility queries (100+ schemes), auto-fills government forms, tracks citizen grievances with 72-hour SLA enforcement, and AI-prioritizes daily tasks across 34 departments — reducing employee burnout and citizen wait times." |
| **What AI/ML technologies do you use?** | "Claude API (reasoning + drafting), OpenAI Whisper (Telugu voice-to-text), sentence-transformers with pgvector (RAG for scheme knowledge base), rapidfuzz (Telugu fuzzy matching). Production-ready with 45+ API endpoints and 270 passing tests." |
| **What makes your AI approach unique?** | "Only AI product targeting government EMPLOYEES (not citizens). Zero competition. Telugu-first with 30+ AP scheme knowledge base, GSWS portal integration, and domain-specific prompts. Jugalbandi and Sarvam AI target citizens — we serve the 1.3L officials who process their requests." |
| **Which focus area?** | Select: **Sovereign AI** (primary) + **Agentic AI** (secondary) |

### C. Problem & Market
| Question | How to Answer |
|----------|---------------|
| **What problem are you solving?** | "AP's 1.3 lakh village secretariat employees each manage 34 departments and 100+ schemes. The Jan 2026 Yogandhra survey exposed staff working 48+ hour weeks with mental health crises. They answer scheme queries from memory, manually type forms, have no grievance tracking, and no task management. The AP government itself called for AI tools — but no product exists for the employee side." |
| **What is your target market?** | "11,162 village secretariats across Andhra Pradesh = 1.3 lakh instant users. Expandable to 6 lakh gram panchayat employees in 28 states. TAM: All Indian government frontline workers." |
| **What traction do you have?** | "Production-ready codebase with 45+ endpoints, 270 tests, 30+ scheme data files, 10 form templates. Pilot playbook for 5 secretariats ready. Applying to IndiaAI Innovation Challenge (AP governance track) and direct RTGS pilot." |

### D. Team
| Question | How to Answer |
|----------|---------------|
| **Who is on your team?** | [Founder names, roles, relevant experience] |
| **Who will attend the bootcamp?** | CEO and CTO (or technical co-founder) |
| **Relevant experience** | [Any government, AI, or Telugu language technology background] |

### E. Google Fit
| Question | How to Answer |
|----------|---------------|
| **How can Google help you?** | "1) Google Cloud credits for PostgreSQL + Redis hosting for 11,162 secretariats. 2) Gemini API access as alternative to Claude for cost optimization. 3) Mentorship on scaling WhatsApp-based AI products to 1.3L users. 4) Android team guidance for future GSWS Employee App integration." |
| **What Google products do you use or plan to use?** | "Google Cloud (planned for state-wide deployment), Gemini API (evaluating as LLM alternative), Firebase (push notifications), Google Fonts Noto Sans Telugu (PDF generation)." |

---

## Step 4: What Links to Prepare Before Applying

You need these ready before opening the form:

### Required Links
| Link | What to Prepare | Status |
|------|----------------|--------|
| **Product Website / Landing Page** | Create a simple landing page explaining the product | Needed |
| **GitHub Repository** | Your codebase at github.com (can be private — mention in form) | Push your code |
| **Demo Video (3-5 min)** | Screen recording of WhatsApp conversation flow | Record this |
| **Pitch Deck** | 10-12 slides (see template below) | Create this |

### How to Create Each

#### 1. Product Website (Quick — 2 hours)
Options:
- **Fastest:** Create a GitHub Pages site from your repo's README
- **Better:** Use Carrd.co or Framer to make a 1-page site with:
  - Hero: "AI Copilot for AP's 1.3L Secretariat Employees"
  - Problem stats (34 depts, 100+ schemes, burnout crisis)
  - 4 features with icons
  - Tech stack
  - "Pilot Ready" badge
  - Contact form

#### 2. GitHub Repository
```bash
# Initialize git if not already done
cd /c/Projects/AP-Product/ap-sachivalayam-copilot
git init
git add -A
git commit -m "AP Sachivalayam AI Copilot - Production ready"

# Create GitHub repo and push
gh repo create ap-sachivalayam-copilot --private --source=. --push
```

#### 3. Demo Video (Record with OBS or Loom)
Script (3 minutes):
```
0:00 - "This is AP Sachivalayam AI Copilot" (show WhatsApp chat)
0:15 - Employee sends "నమస్కారం" → Greeting with 5-option menu
0:30 - Employee asks "అమ్మ ఒడి అర్హత?" → Instant scheme response in Telugu
1:00 - Employee sends voice note with citizen details → Transcription + form auto-fill
1:30 - Show PDF generation → "Submit to GSWS" button
2:00 - Employee files grievance → Reference number + SLA deadline shown
2:20 - Employee types "task" → AI daily plan with priorities
2:40 - Show analytics API: time saved, burnout metrics
3:00 - "270 tests passing, 45+ endpoints, production-ready"
```

#### 4. Pitch Deck (10 slides)
```
Slide 1:  AP Sachivalayam AI Copilot
          "AI for the officials who serve 5 crore citizens"

Slide 2:  The Crisis
          - 1.3L employees × 34 departments × 100+ schemes
          - Yogandhra survey: staff under severe pressure
          - Government called for AI tools — none exist for employees

Slide 3:  What We Built (4 Features)
          - Scheme eligibility checker (100+ schemes, Telugu)
          - Form auto-fill (voice → PDF → GSWS submit)
          - Grievance tracker (72-hr SLA, auto-escalation)
          - Daily task AI prioritizer (burnout reduction)

Slide 4:  Demo Screenshots
          - WhatsApp conversations in Telugu
          - PDF output, grievance tracking

Slide 5:  Advanced Features
          - Rate limiting, audit trail, duplicate detection
          - Employee performance dashboards, data export

Slide 6:  Zero Competition
          - Jugalbandi → citizen-side only
          - Sarvam AI → generic platform
          - GSWS App → no AI
          - We are the ONLY employee-side AI

Slide 7:  Tech Stack
          - Claude + Whisper + pgvector + FastAPI
          - 270 tests, 45+ endpoints, 70 source files
          - Docker-ready, WhatsApp Business API

Slide 8:  Go-to-Market
          - RTGS controls all 11,162 secretariats
          - One integration = 1.3L users instantly
          - IndiaAI Challenge = government endorsement

Slide 9:  Impact Metrics (Projected)
          - 87% reduction in scheme query time
          - 83% reduction in form filling time
          - 20% reduction in daily working hours
          - ~5M hours/year saved state-wide

Slide 10: Ask
          - Google Cloud credits for state-wide scale
          - Gemini API access for cost optimization
          - Mentorship on scaling to 1.3L users
```

---

## Step 5: Submit

1. Open the form: https://docs.google.com/forms/d/e/1FAIpQLSe7aNTQze5Rcbkl22Igo2IVtPgRkfS0wXyWH3HXOJsW9ELSwA/viewform?usp=pp_url&entry.877187925=India&entry.1523595543=India&entry.1569650440=India
2. Fill all sections using the answers above
3. Attach links: website, GitHub, demo video, pitch deck
4. Submit before **April 19, 2026**

---

## Selection Process (What Happens After)

| Stage | What Happens | Timeline |
|-------|-------------|----------|
| 1. Eligibility Screening | Google reviews all applications | April-May 2026 |
| 2. Expert Panel Review | Shortlist 40-60 startups | May 2026 |
| 3. Interview/Pitch | Selected startups pitch to panel | May-June 2026 |
| 4. Final Selection | ~15-20 startups chosen for cohort | June 2026 |
| 5. Bootcamp | 1-week intensive in Bengaluru | Late June 2026 |
| 6. Program | Monthly mentorship sessions | July-September 2026 |
| 7. Demo Day | Present to investors & partners | October 2026 |

---

## What You Get If Selected

- **Equity-free** — Google takes no stake
- **Google Cloud credits** — Infrastructure for scaling
- **Gemini, Gemma, Imagen, Veo, Lyria** — Hands-on access to Google AI models
- **TPU access** — For model training/fine-tuning
- **1:1 mentorship** — Google DeepMind, Cloud, Android, Health teams
- **Demo Day** — Present to investors, government partners, media
- **Google for Startups alumni network** — Ongoing support

---

## Preparation Checklist (18 Days)

| Day | Task | Time |
|-----|------|------|
| Day 1-2 | Push code to GitHub (private repo OK) | 1 hour |
| Day 1-2 | Create landing page (Carrd.co or GitHub Pages) | 2 hours |
| Day 3-4 | Record demo video (Loom or OBS) | 3 hours |
| Day 4-5 | Create pitch deck (10 slides in Google Slides/Canva) | 4 hours |
| Day 6-7 | Draft all application answers using templates above | 3 hours |
| Day 8 | Review everything with a friend/mentor | 2 hours |
| Day 9 | **SUBMIT** (don't wait until April 19 — submit early) | 1 hour |
| Day 10-18 | Buffer for revisions if Google allows edits | — |
