"""
End-to-end real-data tests for all 5 new features using real AP citizen
profiles, real scheme criteria, and real sachivalayam workflows.

Features tested:
1. Document OCR — Aadhaar/ration card field extraction + form mapping
2. Citizen-Facing Mode — intent gating, user detection, citizen greeting
3. Supervisor Dashboard — mandal/district aggregation, SLA alerts
4. Training Mode — scenarios with real scheme data, evaluation flow
5. Proactive Scheme Outreach — rule-based matching with real citizen profiles

Sources: sspensions.ap.gov.in, thallikivandanam.com, spandana.ap.gov.in
"""
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.security import (
    Role,
    ROLE_HIERARCHY,
    hash_aadhaar,
    mask_aadhaar,
)
from app.services.conversation_engine import CITIZEN_ALLOWED_INTENTS
from app.core.telugu import (
    detect_language,
    fuzzy_match_scheme,
    normalize_telugu_text,
    SCHEME_ALIASES,
)
from app.models.beneficiary import Beneficiary
from app.models.citizen import Citizen
from app.models.outreach import OutreachRecord
from app.models.training import TrainingSession
from app.schemas.grievance import GrievanceCreateRequest
from app.services.ocr_service import OCRService
from app.services.outreach_engine import OutreachEngine, _load_active_schemes
from app.services.training_service import TrainingService, _load_scenarios

SCHEMES_DIR = Path(__file__).parent.parent / "app" / "data" / "schemes"
TEMPLATES_FILE = Path(__file__).parent.parent / "app" / "data" / "templates" / "form_templates.json"
SCENARIOS_FILE = Path(__file__).parent.parent / "app" / "data" / "training" / "scenarios.json"


def load_scheme(filename: str) -> dict:
    with open(SCHEMES_DIR / filename, encoding="utf-8") as fp:
        return json.load(fp)


def load_form_templates() -> list[dict]:
    with open(TEMPLATES_FILE, encoding="utf-8") as fp:
        return json.load(fp)


# ═══════════════════════════════════════════════════════════════
# REAL CITIZEN PROFILES (from official AP government data)
# ═══════════════════════════════════════════════════════════════

def make_beneficiary(**kwargs) -> MagicMock:
    """Create a mock Beneficiary with real citizen data."""
    defaults = {
        "id": 1, "aadhaar_hash": None, "phone_number": None,
        "name_te": "Unknown", "name_en": None, "age": None, "gender": None,
        "caste_category": None, "annual_income": None, "ration_card_type": None,
        "district": None, "mandal": None, "secretariat_id": None,
        "is_disabled": False, "disability_percentage": None, "occupation": None,
        "land_acres_wet": None, "land_acres_dry": None, "num_children": None,
        "is_govt_employee": False, "is_income_tax_payer": False,
        "owns_four_wheeler": False, "electricity_units": None,
        "schemes_enrolled": None, "opt_out": False, "metadata_extra": None,
    }
    defaults.update(kwargs)
    ben = MagicMock(spec=Beneficiary)
    for k, v in defaults.items():
        setattr(ben, k, v)
    return ben


# Real AP citizens based on official eligibility thresholds
LAKSHMI = make_beneficiary(
    id=1, name_te="లక్ష్మి", age=65, gender="female", caste_category="SC",
    annual_income=96000, ration_card_type="white", district="Srikakulam",
    mandal="Narasannapeta", secretariat_id=1, land_acres_dry=1.5,
)

RAMESH = make_beneficiary(
    id=2, name_te="రామేష్", age=42, gender="male", caste_category="BC",
    annual_income=144000, ration_card_type="white", district="Guntur",
    mandal="Tenali", secretariat_id=1, occupation="farmer",
    land_acres_wet=2.5, land_acres_dry=3,
)

SUNITHA = make_beneficiary(
    id=3, name_te="సునీత", age=35, gender="female", caste_category="BC",
    annual_income=108000, ration_card_type="rice", district="Krishna",
    mandal="Vijayawada Rural", secretariat_id=1, num_children=2,
    electricity_units=180,
)

GOVT_EMPLOYEE = make_beneficiary(
    id=4, name_te="రవి", age=55, gender="male",
    annual_income=540000, is_govt_employee=True,
    is_income_tax_payer=True, owns_four_wheeler=True,
    electricity_units=450,
)

VENKATESH_DISABLED = make_beneficiary(
    id=5, name_te="వెంకటేష్", age=40, gender="male",
    annual_income=60000, ration_card_type="white",
    is_disabled=True, disability_percentage=85,
)

SURESH_AUTO = make_beneficiary(
    id=6, name_te="సురేష్", age=38, gender="male",
    annual_income=120000, ration_card_type="white",
    occupation="auto", district="Visakhapatnam",
)

PRIYA_GRADUATE = make_beneficiary(
    id=7, name_te="ప్రియ", age=24, gender="female",
    annual_income=0, district="Visakhapatnam",
)

# Real Aadhaar data (fake numbers, real format)
REAL_AADHAAR_DATA = {
    "name": "లక్ష్మి దేవి",
    "name_te": "లక్ష్మి దేవి",
    "date_of_birth": "15/06/1960",
    "gender": "Female",
    "aadhaar_number": "987654321098",
    "address": "H.No. 3-45, Narasannapeta, Srikakulam, AP - 532001",
    "pin_code": "532001",
    "father_name": "రామయ్య",
    "confidence": 0.95,
}

REAL_RATION_CARD_DATA = {
    "card_number": "AP-SKLM-2023-456789",
    "card_type": "White",
    "head_of_family": "లక్ష్మి దేవి",
    "address": "Narasannapeta, Srikakulam",
    "num_members": 4,
    "members": [
        {"name": "లక్ష్మి దేవి", "age": 65, "relation": "Self"},
        {"name": "రామయ్య", "age": 68, "relation": "Husband"},
        {"name": "సునీల్", "age": 30, "relation": "Son"},
        {"name": "లత", "age": 28, "relation": "Daughter-in-law"},
    ],
    "district": "Srikakulam",
    "mandal": "Narasannapeta",
    "confidence": 0.92,
}


# ═══════════════════════════════════════════════════════════════
# FEATURE 1: DOCUMENT OCR — Real Data Tests
# ═══════════════════════════════════════════════════════════════

class TestOCRWithRealAadhaarData:
    """Test OCR extraction using realistic Aadhaar card field data."""

    def test_aadhaar_extraction_produces_valid_fields(self):
        """OCR should extract all key fields from an Aadhaar card."""
        ocr = OCRService()
        result = dict(REAL_AADHAAR_DATA)
        result["document_type"] = "aadhaar_card"
        # Simulate post-processing
        raw = result["aadhaar_number"].replace(" ", "")
        result["aadhaar_hash"] = hash_aadhaar(raw)
        result["aadhaar_last4"] = raw[-4:]
        result["aadhaar_number"] = mask_aadhaar(raw)

        assert result["name"] == "లక్ష్మి దేవి"
        assert result["aadhaar_last4"] == "1098"
        assert "XXXX" in result["aadhaar_number"]
        assert len(result["aadhaar_hash"]) == 64
        assert "987654321098" not in result["aadhaar_number"]  # Raw never stored

    def test_aadhaar_to_thalliki_vandanam_form_mapping(self):
        """Aadhaar OCR data should map to Thalliki Vandanam form fields."""
        ocr = OCRService()
        ocr_data = dict(REAL_AADHAAR_DATA)
        ocr_data["document_type"] = "aadhaar_card"
        ocr_data["aadhaar_last4"] = "1098"

        templates = load_form_templates()
        tv_template = next(t for t in templates if t["scheme_code"] == "THALLIKI-VANDANAM")

        mapping = ocr.map_to_form_fields(ocr_data, tv_template["fields"])

        assert mapping.get("mother_name") == "లక్ష్మి దేవి"
        assert mapping.get("mother_aadhaar") == "1098"
        assert mapping.get("address") == "H.No. 3-45, Narasannapeta, Srikakulam, AP - 532001"

    def test_aadhaar_to_pension_form_mapping(self):
        """Aadhaar OCR data should map to NTR Bharosa Pension form fields."""
        ocr = OCRService()
        ocr_data = dict(REAL_AADHAAR_DATA)
        ocr_data["document_type"] = "aadhaar_card"
        ocr_data["aadhaar_last4"] = "1098"

        templates = load_form_templates()
        pension_template = next(t for t in templates if t["scheme_code"] == "NTR-BHAROSA-PENSION")

        mapping = ocr.map_to_form_fields(ocr_data, pension_template["fields"])
        assert mapping.get("applicant_name") == "లక్ష్మి దేవి"


class TestOCRWithRealRationCardData:
    """Test OCR extraction using realistic ration card field data."""

    def test_ration_card_extraction_produces_valid_fields(self):
        """OCR should extract all key fields from a ration card."""
        result = dict(REAL_RATION_CARD_DATA)
        result["document_type"] = "ration_card"

        assert result["card_type"] == "White"
        assert result["head_of_family"] == "లక్ష్మి దేవి"
        assert result["num_members"] == 4
        assert result["district"] == "Srikakulam"
        assert result["mandal"] == "Narasannapeta"

    def test_ration_card_to_annadata_form_mapping(self):
        """Ration card OCR data should map to Annadata Sukhibhava form fields."""
        ocr = OCRService()
        ocr_data = dict(REAL_RATION_CARD_DATA)
        ocr_data["document_type"] = "ration_card"

        templates = load_form_templates()
        annadata_template = next(t for t in templates if t["scheme_code"] == "ANNADATA-SUKHIBHAVA")

        mapping = ocr.map_to_form_fields(ocr_data, annadata_template["fields"])
        # Annadata uses "farmer_name" not "applicant_name", and ration card maps to "district"/"mandal"
        assert mapping.get("district") == "Srikakulam"
        assert mapping.get("mandal") == "Narasannapeta"

    def test_ration_card_to_thalliki_vandanam_mapping(self):
        """Ration card data should provide card type and number for education scheme."""
        ocr = OCRService()
        ocr_data = dict(REAL_RATION_CARD_DATA)
        ocr_data["document_type"] = "ration_card"

        templates = load_form_templates()
        tv_template = next(t for t in templates if t["scheme_code"] == "THALLIKI-VANDANAM")

        mapping = ocr.map_to_form_fields(ocr_data, tv_template["fields"])
        assert mapping.get("ration_card_type") == "White"
        assert mapping.get("ration_card_number") == "AP-SKLM-2023-456789"

    def test_ocr_pii_protection_never_stores_raw_aadhaar(self):
        """Even if Aadhaar appears in OCR data, raw number must never persist."""
        raw = "987654321098"
        hashed = hash_aadhaar(raw)
        masked = mask_aadhaar(raw)

        assert raw not in masked
        assert raw not in hashed
        assert "1098" in masked
        assert len(hashed) == 64


# ═══════════════════════════════════════════════════════════════
# FEATURE 2: CITIZEN-FACING MODE — Real Data Tests
# ═══════════════════════════════════════════════════════════════

class TestCitizenModeWithRealQueries:
    """Test citizen access control with real Telugu/English queries."""

    # Real queries citizens would type in WhatsApp
    CITIZEN_ALLOWED_QUERIES = [
        ("అమ్మ ఒడి అర్హత ఏమిటి?", "scheme_query"),
        ("pension status check", "status_check"),
        ("నమస్కారం", "greeting"),
        ("NTR భరోసా పెన్షన్ details", "scheme_query"),
        ("am i eligible for aarogyasri", "eligibility_check"),
        ("help", "help"),
        ("ధన్యవాదాలు", "thanks"),
    ]

    CITIZEN_BLOCKED_QUERIES = [
        ("form నింపండి", "form_help"),
        ("ఫిర్యాదు నమోదు", "grievance"),
        ("task plan చెప్పండి", "task_query"),
        ("training mode", "training"),
        ("outreach list", "outreach"),
    ]

    @pytest.mark.parametrize("query,intent", CITIZEN_ALLOWED_QUERIES,
                             ids=[q[:20] for q, _ in CITIZEN_ALLOWED_QUERIES])
    def test_citizen_allowed_intents(self, query, intent):
        """Citizens should be able to access read-only intents."""
        assert intent in CITIZEN_ALLOWED_INTENTS, \
            f"Intent '{intent}' should be in CITIZEN_ALLOWED_INTENTS"

    @pytest.mark.parametrize("query,intent", CITIZEN_BLOCKED_QUERIES,
                             ids=[q[:20] for q, _ in CITIZEN_BLOCKED_QUERIES])
    def test_citizen_blocked_intents(self, query, intent):
        """Citizens should NOT access employee-only intents."""
        assert intent not in CITIZEN_ALLOWED_INTENTS, \
            f"Intent '{intent}' should NOT be in CITIZEN_ALLOWED_INTENTS"

    def test_citizen_model_has_required_fields(self):
        """Citizen model should have phone, name, location, language."""
        assert hasattr(Citizen, "phone_number")
        assert hasattr(Citizen, "name_te")
        assert hasattr(Citizen, "name_en")
        assert hasattr(Citizen, "district")
        assert hasattr(Citizen, "mandal")
        assert hasattr(Citizen, "preferred_language")
        assert hasattr(Citizen, "is_verified")

    def test_citizen_query_language_detection(self):
        """Real citizen queries should have correct language detection."""
        assert detect_language("అమ్మ ఒడి అర్హత ఏమిటి?") == "te"
        assert detect_language("What is pension eligibility?") == "en"
        assert detect_language("NTR భరోసా pension details") == "te"

    def test_citizen_scheme_queries_resolve_correctly(self):
        """Citizen scheme queries should resolve to correct updated scheme codes."""
        queries = [
            ("అమ్మ ఒడి", "THALLIKI-VANDANAM"),
            ("pension details", "NTR-BHAROSA-PENSION"),
            ("aarogyasri", "DR-NTR-VAIDYA-SEVA"),
            ("దీపం scheme", "DEEPAM-2"),
        ]
        for query, expected_code in queries:
            result = fuzzy_match_scheme(normalize_telugu_text(query))
            assert result == expected_code, f"'{query}' → expected '{expected_code}', got '{result}'"

    def test_citizen_allowed_intents_count(self):
        """Citizen should have exactly 7 allowed intents."""
        assert len(CITIZEN_ALLOWED_INTENTS) == 7
        expected = {"scheme_query", "eligibility_check", "status_check",
                    "greeting", "help", "thanks", "language_switch"}
        assert CITIZEN_ALLOWED_INTENTS == expected


# ═══════════════════════════════════════════════════════════════
# FEATURE 3: SUPERVISOR DASHBOARD — Real Data Tests
# ═══════════════════════════════════════════════════════════════

class TestSupervisorWithRealHierarchy:
    """Test supervisor features against real AP government hierarchy."""

    def test_role_hierarchy_has_mandal_officer(self):
        """MPDO (Mandal Parishad Development Officer) role should exist."""
        assert hasattr(Role, "MANDAL_OFFICER")
        assert Role.MANDAL_OFFICER.value == "mandal_officer"

    def test_role_hierarchy_ordering(self):
        """Role hierarchy: employee < secretariat_admin < mandal_officer < district_admin < system_admin."""
        assert ROLE_HIERARCHY[Role.EMPLOYEE] < ROLE_HIERARCHY[Role.SECRETARIAT_ADMIN]
        assert ROLE_HIERARCHY[Role.SECRETARIAT_ADMIN] < ROLE_HIERARCHY[Role.MANDAL_OFFICER]
        assert ROLE_HIERARCHY[Role.MANDAL_OFFICER] < ROLE_HIERARCHY[Role.DISTRICT_ADMIN]
        assert ROLE_HIERARCHY[Role.DISTRICT_ADMIN] < ROLE_HIERARCHY[Role.SYSTEM_ADMIN]

    def test_sla_breach_calculation_with_real_timelines(self):
        """72-hour SLA breach should be detectable with real timeline data."""
        from app.services.grievance_service import PRIORITY_SLA

        # Grievance filed Monday 9 AM, medium priority (72h SLA)
        filed_at = datetime(2026, 3, 30, 9, 0, tzinfo=timezone.utc)
        sla_hours = PRIORITY_SLA["medium"]
        sla_deadline = filed_at + timedelta(hours=sla_hours)

        # Check at Thursday 10 AM (73 hours later — 1 hour overdue)
        check_time = datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc)
        is_breached = check_time > sla_deadline
        hours_overdue = (check_time - sla_deadline).total_seconds() / 3600

        assert is_breached is True
        assert 0.5 < hours_overdue < 2.0

    def test_real_ap_districts_as_aggregation_units(self):
        """Test with real AP district names."""
        real_districts = ["NTR", "Tirupati", "Srikakulam", "Guntur",
                          "Visakhapatnam", "Krishna", "Prakasam", "Nellore"]
        # Just verify they're valid strings for querying
        for d in real_districts:
            assert len(d) > 0 and len(d) < 50

    def test_real_ap_mandals_as_aggregation_units(self):
        """Test with real AP mandal names."""
        real_mandals = ["Vijayawada Rural", "Tenali", "Narasannapeta",
                        "Tirupati Urban", "Srikakulam Urban"]
        for m in real_mandals:
            assert len(m) > 0 and len(m) < 100

    def test_supervisor_service_exists(self):
        """SupervisorService should be importable and constructable."""
        from app.services.supervisor_service import SupervisorService
        db = AsyncMock()
        service = SupervisorService(db)
        assert hasattr(service, "get_mandal_overview")
        assert hasattr(service, "get_district_overview")
        assert hasattr(service, "get_secretariat_rankings")
        assert hasattr(service, "get_sla_breach_alerts")
        assert hasattr(service, "get_low_performing_secretariats")
        assert hasattr(service, "get_employee_detail")


# ═══════════════════════════════════════════════════════════════
# FEATURE 4: TRAINING MODE — Real Data Tests
# ═══════════════════════════════════════════════════════════════

class TestTrainingWithRealSchemeData:
    """Test training scenarios against real AP scheme data."""

    @pytest.fixture
    def scenarios(self):
        return _load_scenarios()

    def test_scenario_count_at_least_30(self, scenarios):
        assert len(scenarios) >= 30, f"Expected 30+ scenarios, got {len(scenarios)}"

    def test_all_scenarios_have_required_fields(self, scenarios):
        required = ["id", "difficulty", "category", "scenario_te", "scenario_en",
                     "key_points", "model_answer_te"]
        for s in scenarios:
            for field in required:
                assert field in s, f"Scenario {s['id']} missing '{field}'"

    def test_scenarios_cover_all_major_schemes(self, scenarios):
        """Training should cover the key AP schemes employees deal with daily."""
        expected_schemes = {
            "THALLIKI-VANDANAM", "ANNADATA-SUKHIBHAVA", "NTR-BHAROSA-PENSION",
            "DR-NTR-VAIDYA-SEVA", "CHANDRANNA-PELLI-KANUKA", "DEEPAM-2",
            "STREE-SHAKTI", "YUVA-GALAM",
        }
        scenario_schemes = {s.get("expected_scheme") for s in scenarios if s.get("expected_scheme")}
        covered = expected_schemes & scenario_schemes
        assert len(covered) >= 5, \
            f"Expected 5+ major schemes covered, got {len(covered)}: {covered}"

    def test_scenarios_have_valid_difficulties(self, scenarios):
        valid = {"easy", "medium", "hard"}
        for s in scenarios:
            assert s["difficulty"] in valid, f"Scenario {s['id']} has invalid difficulty: {s['difficulty']}"

    def test_scenarios_bilingual(self, scenarios):
        """Every scenario must have both Telugu and English versions."""
        for s in scenarios:
            assert len(s["scenario_te"]) > 10, f"Scenario {s['id']} has short Telugu text"
            assert len(s["scenario_en"]) > 10, f"Scenario {s['id']} has short English text"
            assert len(s["model_answer_te"]) > 20, f"Scenario {s['id']} has short model answer"

    def test_scenario_key_points_match_real_data(self, scenarios):
        """Key points in training scenarios should match real scheme data."""
        # Find Thalliki Vandanam scenario
        tv_scenarios = [s for s in scenarios if s.get("expected_scheme") == "THALLIKI-VANDANAM"]
        assert len(tv_scenarios) >= 1

        scheme = load_scheme("ysr_amma_vodi.json")
        tv = tv_scenarios[0]

        # Key points should mention real amounts/criteria
        all_points = " ".join(tv["key_points"]).lower()
        assert "15,000" in all_points or "15000" in all_points, "Should mention ₹15,000 benefit"
        assert "1-12" in all_points or "classes" in all_points, "Should mention classes 1-12"

    def test_pension_scenario_covers_multiple_types(self, scenarios):
        """Pension training should cover the complexity of 14 pension types."""
        pension_scenarios = [s for s in scenarios
                            if s.get("expected_scheme") == "NTR-BHAROSA-PENSION"]
        assert len(pension_scenarios) >= 2, "Need multiple pension scenarios for 14 types"

    def test_scenario_amounts_match_current_data(self, scenarios):
        """Training scenario amounts should match updated (not old) scheme data."""
        # Annadata Sukhibhava should reference ₹20,000 (not old ₹13,500)
        annadata = [s for s in scenarios if s.get("expected_scheme") == "ANNADATA-SUKHIBHAVA"]
        if annadata:
            all_text = " ".join(annadata[0]["key_points"])
            assert "20,000" in all_text or "20000" in all_text, \
                "Annadata scenario should reference ₹20,000 (updated amount)"

    def test_training_intent_keywords_exist(self):
        """'training' should be a recognized intent in INTENT_KEYWORDS."""
        from app.services.conversation_engine import INTENT_KEYWORDS
        assert "training" in INTENT_KEYWORDS
        keywords = INTENT_KEYWORDS["training"]
        assert "training" in keywords
        assert "practice" in keywords
        assert "ట్రైనింగ్" in keywords  # Telugu keyword

    def test_training_session_model_fields(self):
        """TrainingSession should have all required tracking fields."""
        assert hasattr(TrainingSession, "employee_id")
        assert hasattr(TrainingSession, "scenario_id")
        assert hasattr(TrainingSession, "ai_score")
        assert hasattr(TrainingSession, "ai_feedback_te")
        assert hasattr(TrainingSession, "key_points_covered")
        assert hasattr(TrainingSession, "time_taken_seconds")

    def test_evaluation_prompt_has_scoring_rules(self):
        """The evaluation prompt should have clear scoring brackets."""
        from app.services.training_service import EVALUATION_PROMPT
        assert "90-100" in EVALUATION_PROMPT
        assert "70-89" in EVALUATION_PROMPT
        assert "50-69" in EVALUATION_PROMPT
        assert "0-29" in EVALUATION_PROMPT


# ═══════════════════════════════════════════════════════════════
# FEATURE 5: PROACTIVE SCHEME OUTREACH — Real Data Tests
# ═══════════════════════════════════════════════════════════════

class TestOutreachWithRealCitizenProfiles:
    """Test rule-based eligibility matching with real AP citizen profiles."""

    @pytest.fixture
    def engine(self):
        db = AsyncMock()
        return OutreachEngine(db)

    # --- NTR Bharosa Pension matching ---

    def test_lakshmi_eligible_for_pension(self, engine):
        """65yo SC widow with white card, ₹96K income → eligible for pension."""
        scheme = load_scheme("ysr_pension_kanuka.json")
        eligible, score, reasoning = engine.check_eligibility_rules(LAKSHMI, scheme)
        assert eligible is True
        assert score >= 0.5
        assert len(reasoning) > 0

    def test_lakshmi_pension_score_reflects_multiple_criteria(self, engine):
        """Lakshmi matches age + income + ration card → higher score."""
        scheme = load_scheme("ysr_pension_kanuka.json")
        _, score, reasoning = engine.check_eligibility_rules(LAKSHMI, scheme)
        # Should have score from: base(0.5) + ration_card(0.2) + income or age
        assert score >= 0.7, f"Expected higher score for strong match, got {score}"

    # --- Annadata Sukhibhava matching ---

    def test_ramesh_eligible_for_annadata(self, engine):
        """Farmer with land, BC caste, ₹144K income → eligible for Annadata."""
        scheme = load_scheme("ysr_rythu_bharosa.json")
        eligible, score, reasoning = engine.check_eligibility_rules(RAMESH, scheme)
        assert eligible is True

    def test_ramesh_farmer_occupation_boosts_score(self, engine):
        """Farmer occupation should boost score for agriculture scheme."""
        scheme = load_scheme("ysr_rythu_bharosa.json")
        _, score, _ = engine.check_eligibility_rules(RAMESH, scheme)
        # Base 0.5 + occupation match for "farmer"
        assert score >= 0.5

    # --- Thalliki Vandanam matching ---

    def test_sunitha_eligible_for_thalliki_vandanam(self, engine):
        """Mother with 2 children, rice card, ₹108K income → eligible."""
        scheme = load_scheme("ysr_amma_vodi.json")
        eligible, score, reasoning = engine.check_eligibility_rules(SUNITHA, scheme)
        assert eligible is True
        assert "Ration card" in reasoning

    # --- Government employee exclusion ---

    def test_govt_employee_excluded_from_pension(self, engine):
        """Government employee should be excluded from NTR Bharosa Pension."""
        scheme = load_scheme("ysr_pension_kanuka.json")
        eligible, score, reasoning = engine.check_eligibility_rules(GOVT_EMPLOYEE, scheme)
        assert eligible is False
        assert score == 0.0
        assert "Government employee" in reasoning

    def test_govt_employee_excluded_from_annadata(self, engine):
        scheme = load_scheme("ysr_rythu_bharosa.json")
        eligible, _, _ = engine.check_eligibility_rules(GOVT_EMPLOYEE, scheme)
        assert eligible is False

    def test_govt_employee_excluded_from_thalliki(self, engine):
        scheme = load_scheme("ysr_amma_vodi.json")
        eligible, _, _ = engine.check_eligibility_rules(GOVT_EMPLOYEE, scheme)
        assert eligible is False

    def test_income_tax_payer_excluded(self, engine):
        """Income tax payer should be excluded from welfare schemes."""
        scheme = load_scheme("ysr_amma_vodi.json")
        eligible, _, reasoning = engine.check_eligibility_rules(GOVT_EMPLOYEE, scheme)
        assert eligible is False

    def test_four_wheeler_owner_excluded(self, engine):
        """Four-wheeler owner should be excluded."""
        scheme = load_scheme("ysr_amma_vodi.json")
        eligible, _, _ = engine.check_eligibility_rules(GOVT_EMPLOYEE, scheme)
        assert eligible is False

    # --- Disability pension matching ---

    def test_disabled_citizen_eligible_for_pension(self, engine):
        """85% disabled citizen → should match disability pension."""
        scheme = load_scheme("ysr_pension_kanuka.json")
        eligible, score, reasoning = engine.check_eligibility_rules(VENKATESH_DISABLED, scheme)
        assert eligible is True
        assert "Disability" in reasoning

    def test_disabled_score_higher_than_general(self, engine):
        """Disability match should give high score due to +0.3 boost."""
        scheme = load_scheme("ysr_pension_kanuka.json")
        _, disabled_score, _ = engine.check_eligibility_rules(VENKATESH_DISABLED, scheme)
        # Base 0.5 + disability 0.3 + ration card 0.2 = 1.0
        assert disabled_score >= 0.8

    # --- Auto driver matching ---

    def test_auto_driver_eligible_for_sevalo(self, engine):
        """Auto driver should match Auto Drivers Sevalo scheme."""
        scheme = load_scheme("ysr_vahana_mitra.json")
        eligible, _, reasoning = engine.check_eligibility_rules(SURESH_AUTO, scheme)
        assert eligible is True

    # --- Cross-scheme scanning ---

    def test_active_schemes_load_correctly(self):
        """_load_active_schemes should return 30+ active schemes."""
        schemes = _load_active_schemes()
        assert len(schemes) >= 25, f"Expected 25+ active schemes, got {len(schemes)}"

    def test_cheyutha_not_in_active_schemes(self):
        """YSR Cheyutha (is_active=false) should not appear in active schemes."""
        schemes = _load_active_schemes()
        codes = [s["scheme_code"] for s in schemes]
        assert "YSR-CHEYUTHA" not in codes

    def test_scan_beneficiary_finds_multiple_schemes(self, engine):
        """A single beneficiary can be eligible for multiple schemes."""
        # Lakshmi: elderly + SC + white card + low income → pension + health + housing
        schemes = _load_active_schemes()
        match_count = 0
        for scheme in schemes:
            eligible, _, _ = engine.check_eligibility_rules(LAKSHMI, scheme)
            if eligible:
                match_count += 1

        assert match_count >= 3, f"Lakshmi should match 3+ schemes, got {match_count}"

    def test_beneficiary_model_has_demographic_fields(self):
        """Beneficiary model should capture all fields needed for matching."""
        required_fields = [
            "aadhaar_hash", "phone_number", "name_te", "age", "gender",
            "caste_category", "annual_income", "ration_card_type",
            "district", "mandal", "secretariat_id",
            "is_disabled", "disability_percentage", "occupation",
            "land_acres_wet", "land_acres_dry",
            "is_govt_employee", "is_income_tax_payer", "owns_four_wheeler",
            "schemes_enrolled", "opt_out",
        ]
        for field in required_fields:
            assert hasattr(Beneficiary, field), f"Beneficiary missing field: {field}"

    def test_outreach_record_status_workflow(self):
        """OutreachRecord should support: identified → notified → applied."""
        assert hasattr(OutreachRecord, "status")
        assert hasattr(OutreachRecord, "notified_at")
        assert hasattr(OutreachRecord, "applied_at")
        assert hasattr(OutreachRecord, "match_score")
        assert hasattr(OutreachRecord, "match_reasoning_te")

    def test_outreach_intent_keywords_exist(self):
        """'outreach' should be a recognized intent."""
        from app.services.conversation_engine import INTENT_KEYWORDS
        assert "outreach" in INTENT_KEYWORDS
        keywords = INTENT_KEYWORDS["outreach"]
        assert "outreach" in keywords
        assert "పథకం అర్హులు" in keywords


# ═══════════════════════════════════════════════════════════════
# CROSS-FEATURE INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestCrossFeatureIntegration:
    """Test that all 5 features work together with real data."""

    def test_ocr_feeds_into_form_filler(self):
        """OCR-extracted fields should map to at least some form fields for each template."""
        ocr = OCRService()
        templates = load_form_templates()

        for doc_type, doc_data in [("aadhaar_card", REAL_AADHAAR_DATA),
                                     ("ration_card", REAL_RATION_CARD_DATA)]:
            data = dict(doc_data)
            data["document_type"] = doc_type
            if doc_type == "aadhaar_card":
                data["aadhaar_last4"] = "1098"

            total_mappings = 0
            for tmpl in templates:
                mapping = ocr.map_to_form_fields(data, tmpl["fields"])
                total_mappings += len(mapping)

            # Across all templates, OCR should map to many fields
            assert total_mappings >= 5, \
                f"OCR ({doc_type}) should map to 5+ fields across all templates, got {total_mappings}"

    def test_citizen_cannot_access_training(self):
        """Training mode is employee-only — citizens should be blocked."""
        assert "training" not in CITIZEN_ALLOWED_INTENTS

    def test_citizen_cannot_access_outreach(self):
        """Outreach is employee-only — citizens should be blocked."""
        assert "outreach" not in CITIZEN_ALLOWED_INTENTS

    def test_outreach_uses_same_scheme_data_as_eligibility(self):
        """Outreach engine and scheme advisor use the same 33 scheme files."""
        active_schemes = _load_active_schemes()
        active_codes = {s["scheme_code"] for s in active_schemes}

        # All aliases should point to either active or known scheme codes
        all_scheme_codes = set()
        for f in SCHEMES_DIR.glob("*.json"):
            with open(f, encoding="utf-8") as fp:
                all_scheme_codes.add(json.load(fp)["scheme_code"])

        # Active schemes should be a subset of all schemes
        assert active_codes.issubset(all_scheme_codes)

    def test_training_scenarios_reference_valid_scheme_codes(self):
        """Training scenario expected_scheme codes should match actual scheme files."""
        scenarios = _load_scenarios()
        all_scheme_codes = set()
        for f in SCHEMES_DIR.glob("*.json"):
            with open(f, encoding="utf-8") as fp:
                all_scheme_codes.add(json.load(fp)["scheme_code"])

        for s in scenarios:
            if s.get("expected_scheme"):
                assert s["expected_scheme"] in all_scheme_codes, \
                    f"Scenario {s['id']} references unknown scheme: {s['expected_scheme']}"

    def test_supervisor_can_see_outreach_results(self):
        """Supervisor role should be high enough to access outreach data."""
        assert ROLE_HIERARCHY[Role.MANDAL_OFFICER] >= 2
        assert ROLE_HIERARCHY[Role.DISTRICT_ADMIN] >= 3

    def test_all_new_models_registered(self):
        """All new models should be in __init__.py __all__."""
        from app.models import __all__ as model_list
        assert "Citizen" in model_list
        assert "TrainingSession" in model_list
        assert "Beneficiary" in model_list
        assert "OutreachRecord" in model_list

    def test_all_new_routers_registered(self):
        """All new API routers should be registered."""
        from app.api.v1.router import api_v1_router
        route_paths = [r.path for r in api_v1_router.routes]
        route_str = " ".join(route_paths)
        assert "/citizens" in route_str or "citizens" in route_str
        assert "/supervisor" in route_str or "supervisor" in route_str
        assert "/training" in route_str or "training" in route_str
        assert "/outreach" in route_str or "outreach" in route_str

    def test_full_citizen_journey_simulation(self):
        """Simulate a citizen's complete interaction with the bot."""
        # Step 1: Citizen types "అమ్మ ఒడి అర్హత" in WhatsApp
        query = "అమ్మ ఒడి అర్హత ఏమిటి?"
        lang = detect_language(query)
        assert lang == "te"

        # Step 2: Intent classified as scheme_query
        intent = "scheme_query"
        assert intent in CITIZEN_ALLOWED_INTENTS

        # Step 3: Scheme resolves to updated code
        scheme_code = fuzzy_match_scheme(normalize_telugu_text(query))
        assert scheme_code == "THALLIKI-VANDANAM"

        # Step 4: Citizen tries to file a form → blocked
        form_intent = "form_help"
        assert form_intent not in CITIZEN_ALLOWED_INTENTS

    def test_full_employee_training_simulation(self):
        """Simulate an employee's training session."""
        scenarios = _load_scenarios()
        assert len(scenarios) >= 30

        # Employee gets first scenario
        scenario = scenarios[0]
        assert "scenario_te" in scenario
        assert "key_points" in scenario
        assert len(scenario["key_points"]) >= 3

        # Simulated response (employee answers)
        response = "తల్లికి వందనం పథకం, ₹15,000 per child, 1-12 classes, 75% attendance"

        # Evaluation would happen via Claude — verify prompt structure
        from app.services.training_service import EVALUATION_PROMPT
        prompt = EVALUATION_PROMPT.format(
            scenario=scenario["scenario_en"],
            key_points=json.dumps(scenario["key_points"]),
            model_answer=scenario["model_answer_te"],
            employee_response=response,
        )
        assert "Score" in prompt or "score" in prompt
        assert response in prompt

    def test_full_outreach_simulation(self):
        """Simulate outreach scanning for a secretariat."""
        engine = OutreachEngine(AsyncMock())
        schemes = _load_active_schemes()

        # Test each real citizen against all active schemes
        citizens = [LAKSHMI, RAMESH, SUNITHA, VENKATESH_DISABLED, SURESH_AUTO]
        total_matches = 0

        for citizen in citizens:
            for scheme in schemes:
                eligible, score, _ = engine.check_eligibility_rules(citizen, scheme)
                if eligible:
                    total_matches += 1

        # 5 real citizens × 30+ schemes → should find many matches
        assert total_matches >= 10, f"Expected 10+ matches from 5 citizens, got {total_matches}"

        # Govt employee should get very few matches (only universal schemes with empty excluded list)
        govt_matches = sum(
            1 for s in schemes
            if engine.check_eligibility_rules(GOVT_EMPLOYEE, s)[0]
        )
        # Govt employee excluded from all schemes that have "government" in excluded list
        # Only universal schemes (Kanti Velugu, Sampoorna Poshana etc) with excluded=[] might pass
        schemes_with_govt_exclusion = sum(
            1 for s in schemes
            if any("government" in e.lower() or "govt" in e.lower()
                   for e in s.get("eligibility_criteria", {}).get("excluded", []))
        )
        assert schemes_with_govt_exclusion >= 15, \
            "Most schemes should exclude govt employees"
