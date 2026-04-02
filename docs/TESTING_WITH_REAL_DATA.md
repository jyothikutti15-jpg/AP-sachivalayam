# Testing AP Sachivalayam AI Copilot with Real Government Data

> Yes — there is real, free, publicly available government data you can use to test every feature.

---

## Real Data Sources (All Free, No Login Required)

### 1. Scheme Data — 723 Schemes with Eligibility (JSON/CSV)

**HuggingFace Dataset (BEST SOURCE — ready to use)**
- **URL:** https://huggingface.co/datasets/shrijayan/gov_myscheme
- **Format:** JSON, CSV, Parquet
- **Contains:** 723 government schemes with name, description, eligibility criteria, benefits, application process, official links
- **License:** Apache 2.0 (free to use)
- **How to use:**
```bash
# Download with Python
pip install datasets
python -c "
from datasets import load_dataset
ds = load_dataset('shrijayan/gov_myscheme')
print(ds)
# Filter for AP schemes
for row in ds['train']:
    if 'andhra' in row['description'].lower():
        print(row['scheme_name'], row['eligibility'])
"
```

### 2. AP-Specific Scheme Data — 36+ Schemes with Full Details

**Vikaspedia (Government of India)**
- **URL:** https://en.vikaspedia.in/viewcontent/schemesall//state-specific-schemes/welfare-schemes-of-andhra-pradesh
- **Contains:** 36 AP welfare schemes with descriptions
- **Schemes include:** YSR Rythu Bharosa, Amma Vodi, Aarogyasri, Cheyutha, Pension Kanuka, Vidya Deevena, Kalyana Kanuka, Vahana Mitra, and 28 more

**myScheme.gov.in (Government of India)**
- **URL:** https://www.myscheme.gov.in/search/state/Andhra%20Pradesh
- **Contains:** AP schemes with eligibility criteria, application process, benefits
- **Use for:** Validating and enriching your scheme knowledge base

**AP Govt Schemes Blog (Telugu + English)**
- **URL:** https://apgovtschemes.com/
- **Contains:** Latest AP scheme updates, eligibility, benefits in Telugu
- **Use for:** Telugu language test data

**Sarkari Yojana — AP Schemes PDF**
- **URL:** https://sarkariyojana.com/andhra-pradesh/
- **Contains:** Complete AP schemes list with eligibility PDFs

### 3. GSWS Application Forms — Real Government PDF Forms

**GSWS Helper (Community Resource)**
- **URL:** https://www.gswshelper.com/p/gsws-application-forms.html
- **Contains:** All GSWS application form PDFs for pensions, housing, education, certificates
- **Use for:** Testing form auto-fill feature with real form structures

**Sachivalayam Updates**
- **URL:** https://www.sachivalayamupdates.com/p/gsws-all-application-forms.html
- **Contains:** All sachivalayam application forms PDF download

**Venky Academy**
- **URL:** https://www.venkyacademy.in/2021/11/gsws-pdf-applications.html
- **Contains:** Compiled GSWS PDF application forms

### 4. Open Government Data — AP Statistics & Datasets

**AP Open Data Portal**
- **URL:** https://ap.data.gov.in/
- **Format:** CSV, XLS, JSON, XML, API
- **Contains:** AP government datasets across departments
- **API Access:** Free registration for API key at https://www.data.gov.in/apis

**National Open Data Portal — AP Section**
- **URL:** https://www.data.gov.in/statedepartment/Andhra%20Pradesh
- **Contains:** Welfare, agriculture, health, education datasets
- **Python tool:** `pip install datagovindia` — download datasets programmatically

**Open Budgets India — AP Scheme Budgets**
- **URL:** https://openbudgetsindia.org/dataset/andhra-pradesh-state-scheme
- **Contains:** AP scheme budget allocations, spending data

### 5. Beneficiary Portals — Real Status Check Data

**GSWS Portal (Official)**
- **URL:** https://vswsonline.ap.gov.in/
- **Use for:** Testing application status check feature

**NBM Portal (Beneficiary Management)**
- **URL:** https://gsws-nbm.ap.gov.in/
- **Contains:** Scheme-wise beneficiary lists (Rythu Bharosa, Pensions, Health Cards)

**Amma Vodi Portal**
- **URL:** https://jaganannaammavodi.ap.gov.in/
- **Contains:** Beneficiary list, eligibility check, payment status

### 6. Government Orders (GOs) — Legal References

**GSWS Helper — GOs & Circulars**
- **URL:** https://www.gswshelper.com/p/latest-user-manuals.html
- **Contains:** Latest government orders, circulars, user manuals
- **Use for:** Enriching knowledge base with official GO references

---

## How to Test Each Feature with Real Data

### Feature 1: Scheme Eligibility Checker

**Test Data Source:** HuggingFace dataset + myScheme.gov.in

```bash
# Step 1: Download real scheme data
pip install datasets
python -c "
from datasets import load_dataset
import json

ds = load_dataset('shrijayan/gov_myscheme')
ap_schemes = []
for row in ds['train']:
    desc = (row.get('description') or '').lower()
    name = (row.get('scheme_name') or '').lower()
    if 'andhra' in desc or 'andhra' in name or 'ap ' in name:
        ap_schemes.append(row)
        
print(f'Found {len(ap_schemes)} AP schemes')
with open('real_ap_schemes.json', 'w') as f:
    json.dump(ap_schemes, f, indent=2, ensure_ascii=False)
"
```

**Test Queries (Real Telugu):**
```
1. "అమ్మ ఒడి పథకంలో అర్హత ఏమిటి?" (What is Amma Vodi eligibility?)
2. "రైతు భరోసా కోసం ఏ documents కావాలి?" (What documents for Rythu Bharosa?)
3. "పెన్షన్ ఎంత వస్తుంది?" (How much pension?)
4. "White card ఉంటే ఏ schemes వర్తిస్తాయి?" (Which schemes for White card holders?)
5. "వయస్సు 50, income 1.5 లక్షలు, ఏ schemes?" (Age 50, income 1.5L, which schemes?)
```

### Feature 2: Form Auto-Fill

**Test Data Source:** GSWS application forms from gswshelper.com

**Test Input (Real citizen scenario in Telugu):**
```
"రాము, వయస్సు 42, agricultural worker, White ration card, 
income 80,000, Kurnool district, Aadhaar 1234 5678 9012, 
2 children, wife name సీత, bank account SBI Kurnool branch"
```

**Expected:** Auto-fill Amma Vodi / Rythu Bharosa form fields with confidence scores.

### Feature 3: Grievance Resolution

**Test Data (Real grievance scenarios from AP):**
```
1. "రాము గారి పెన్షన్ 3 నెలల నుండి రావడం లేదు. Welfare department." 
   (Ram's pension not received for 3 months)
   → Should categorize: welfare, subcategory: pension_delay, priority: high

2. "PHC లో మందులు లేవు. Health department."
   (No medicines in PHC)
   → Should categorize: health, subcategory: medicine_shortage, priority: high

3. "రోడ్ damage అయింది, accident risk ఉంది"
   (Road damaged, accident risk)
   → Should categorize: road_transport, priority: urgent

4. "Aarogyasri card reject అయింది, re-apply ఎలా?"
   (Aarogyasri card rejected, how to re-apply?)
   → Should categorize: health, subcategory: aarogyasri_issue
```

### Feature 4: Task Prioritization

**Test Data (Real secretariat employee workday):**
```python
test_tasks = [
    {"title_te": "రైతు భరోసా దరఖాస్తులు process చేయాలి", "department": "Agriculture", "priority": "high", "due_date": "today", "category": "scheme_processing"},
    {"title_te": "Amma Vodi beneficiary verification", "department": "Education", "priority": "medium", "due_date": "today", "category": "field_visit"},
    {"title_te": "Monthly attendance report submit", "department": "General Administration", "priority": "low", "due_date": "tomorrow", "category": "report_writing"},
    {"title_te": "Pension grievance follow-up — 3 citizens", "department": "Welfare", "priority": "urgent", "due_date": "overdue", "category": "grievance_followup"},
    {"title_te": "GSWS portal data entry — 20 records", "department": "Revenue", "priority": "medium", "due_date": "today", "category": "data_entry"},
]
# Expected AI output: Pension grievance first (overdue + urgent), then Rythu Bharosa (high + due today), etc.
```

---

## Quick Start: Test the Whole Product in 30 Minutes

### Step 1: Enrich Scheme Data (10 min)
```bash
# Download real AP scheme data from HuggingFace
pip install datasets
python scripts/scrape_schemes.py  # Uses your existing scraper

# Or manually download from:
# https://huggingface.co/datasets/shrijayan/gov_myscheme
# Filter for Andhra Pradesh schemes
```

### Step 2: Run the Product Locally (5 min)
```bash
docker-compose up -d
# Wait for all services to start
curl http://localhost:8000/api/v1/health
```

### Step 3: Test Scheme Search (5 min)
```bash
# Telugu scheme query
curl -X POST http://localhost:8000/api/v1/schemes/search \
  -H "Content-Type: application/json" \
  -d '{"query": "అమ్మ ఒడి అర్హత ఏమిటి?", "language": "te"}'

# Eligibility check
curl -X POST http://localhost:8000/api/v1/schemes/eligibility-check \
  -H "Content-Type: application/json" \
  -d '{"scheme_code": "YSR-AMMA-VODI", "citizen_details": {"age": 35, "income": 150000, "ration_card": "White", "children": 2}}'
```

### Step 4: Test Form Auto-Fill (5 min)
```bash
curl -X POST http://localhost:8000/api/v1/forms/auto-fill \
  -H "Content-Type: application/json" \
  -d '{"template_id": 1, "employee_id": 1, "input_text": "రాము, వయస్సు 35, income 2 లక్షలు, White card, SBI bank account"}'
```

### Step 5: Test Grievance Filing (5 min)
```bash
curl -X POST "http://localhost:8000/api/v1/grievances/?employee_id=1" \
  -H "Content-Type: application/json" \
  -d '{"citizen_name": "రాము", "category": "welfare", "subject_te": "పెన్షన్ 3 నెలల నుండి రాలేదు", "description_te": "రాము గారికి YSR Pension 3 నెలల నుండి credit కాలేదు. Bank: SBI Kurnool. Pension ID: AP-PEN-12345", "priority": "high"}'

# Check grievance status
curl http://localhost:8000/api/v1/grievances/reference/GRV-2026-0001
```

---

## Data Sources Summary Table

| Source | URL | What You Get | Format | Free? |
|--------|-----|-------------|--------|-------|
| **HuggingFace MyScheme** | huggingface.co/datasets/shrijayan/gov_myscheme | 723 schemes + eligibility | JSON/CSV | Yes |
| **myScheme.gov.in** | myscheme.gov.in/search/state/Andhra%20Pradesh | AP schemes with details | Web | Yes |
| **Vikaspedia** | vikaspedia.in (AP welfare) | 36 AP schemes | Web | Yes |
| **AP Open Data** | ap.data.gov.in | AP government datasets | CSV/JSON/API | Yes |
| **data.gov.in** | data.gov.in/statedepartment/Andhra%20Pradesh | National datasets | CSV/API | Yes |
| **GSWS Helper** | gswshelper.com | Application forms, GOs | PDF | Yes |
| **GSWS Portal** | vswsonline.ap.gov.in | Status check, services | Web | Yes |
| **NBM Portal** | gsws-nbm.ap.gov.in | Beneficiary lists | Web | Yes |
| **Amma Vodi Portal** | jaganannaammavodi.ap.gov.in | Beneficiary data | Web | Yes |
| **Open Budgets India** | openbudgetsindia.org/dataset/andhra-pradesh-state-scheme | Budget data | CSV | Yes |
| **AP Govt Schemes** | apgovtschemes.com | Telugu scheme info | Web | Yes |
| **Sarkari Yojana** | sarkariyojana.com/andhra-pradesh | Scheme PDFs | PDF | Yes |

All data is publicly available from Government of India portals. No authentication required for downloads.
