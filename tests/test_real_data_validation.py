"""
Tests validating scheme data, FAQs, form templates, and Telugu aliases
against real AP government data collected from official portals.

Sources:
- https://sspensions.ap.gov.in/ssp/home/about (NTR Bharosa Pensions)
- https://thallikivandanam.com/ (Thalliki Vandanam)
- https://annadathasukhibhava.ap.gov.in/ (Annadata Sukhibhava)
- https://drntrvaidyaseva.ap.gov.in/ (Dr. NTR Vaidya Seva)
- https://spandana.ap.gov.in/ (Grievance portal)
- https://schemes.vikaspedia.in (AP welfare schemes)
"""
import json
from pathlib import Path

import pytest

from app.core.telugu import (
    SCHEME_ALIASES,
    detect_language,
    fuzzy_match_scheme,
    normalize_telugu_text,
)

SCHEMES_DIR = Path(__file__).parent.parent / "app" / "data" / "schemes"
FAQS_FILE = Path(__file__).parent.parent / "app" / "data" / "scheme_faqs.json"
TEMPLATES_FILE = Path(__file__).parent.parent / "app" / "data" / "templates" / "form_templates.json"


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def load_all_schemes() -> list[dict]:
    """Load all scheme JSON files."""
    schemes = []
    for f in SCHEMES_DIR.glob("*.json"):
        with open(f, encoding="utf-8") as fp:
            schemes.append(json.load(fp))
    return schemes


def load_scheme(filename: str) -> dict:
    """Load a specific scheme file."""
    with open(SCHEMES_DIR / filename, encoding="utf-8") as fp:
        return json.load(fp)


def load_faqs() -> dict:
    with open(FAQS_FILE, encoding="utf-8") as fp:
        return json.load(fp)


def load_form_templates() -> list[dict]:
    with open(TEMPLATES_FILE, encoding="utf-8") as fp:
        return json.load(fp)


# ══════════════════════════════════════════════
# 1. SCHEME DATA INTEGRITY
# ══════════════════════════════════════════════

class TestSchemeDataIntegrity:
    """Verify all 33 scheme JSON files have valid structure."""

    def test_scheme_count(self):
        schemes = list(SCHEMES_DIR.glob("*.json"))
        assert len(schemes) >= 33, f"Expected at least 33 schemes, got {len(schemes)}"

    @pytest.mark.parametrize("scheme", load_all_schemes(), ids=lambda s: s.get("scheme_code", "unknown"))
    def test_required_fields_present(self, scheme):
        required = ["scheme_code", "name_te", "name_en", "department",
                     "description_te", "description_en", "eligibility_criteria",
                     "required_documents", "benefit_amount", "application_process_te",
                     "is_active"]
        for field in required:
            assert field in scheme, f"{scheme['scheme_code']}: missing field '{field}'"

    @pytest.mark.parametrize("scheme", load_all_schemes(), ids=lambda s: s.get("scheme_code", "unknown"))
    def test_eligibility_has_excluded(self, scheme):
        ec = scheme["eligibility_criteria"]
        assert "excluded" in ec, f"{scheme['scheme_code']}: eligibility_criteria missing 'excluded' list"

    @pytest.mark.parametrize("scheme", load_all_schemes(), ids=lambda s: s.get("scheme_code", "unknown"))
    def test_documents_has_mandatory(self, scheme):
        docs = scheme["required_documents"]
        assert "mandatory" in docs, f"{scheme['scheme_code']}: missing mandatory documents"
        assert len(docs["mandatory"]) > 0, f"{scheme['scheme_code']}: empty mandatory documents"

    @pytest.mark.parametrize("scheme", load_all_schemes(), ids=lambda s: s.get("scheme_code", "unknown"))
    def test_telugu_text_present(self, scheme):
        assert len(scheme["name_te"]) > 0, f"{scheme['scheme_code']}: empty Telugu name"
        assert len(scheme["description_te"]) > 0, f"{scheme['scheme_code']}: empty Telugu description"

    @pytest.mark.parametrize("scheme", load_all_schemes(), ids=lambda s: s.get("scheme_code", "unknown"))
    def test_scheme_code_format(self, scheme):
        code = scheme["scheme_code"]
        assert code == code.upper(), f"Scheme code should be uppercase: {code}"
        assert " " not in code, f"Scheme code should not contain spaces: {code}"


# ══════════════════════════════════════════════
# 2. RENAMED SCHEMES — VERIFY CURRENT BRANDING
# ══════════════════════════════════════════════

class TestSchemeRenaming:
    """Verify all TDP-era scheme renamings are correctly applied."""

    RENAMING_MAP = {
        "ysr_amma_vodi.json": ("THALLIKI-VANDANAM", "తల్లికి వందనం", "Thalliki Vandanam"),
        "ysr_rythu_bharosa.json": ("ANNADATA-SUKHIBHAVA", "అన్నదాత సుఖీభవ", "Annadata Sukhibhava"),
        "ysr_pension_kanuka.json": ("NTR-BHAROSA-PENSION", "ఎన్‌టీఆర్ భరోసా పెన్షన్", "NTR Bharosa Pension"),
        "ysr_aarogyasri.json": ("DR-NTR-VAIDYA-SEVA", "డాక్టర్ ఎన్‌టీఆర్ వైద్య సేవ", "Dr. NTR Vaidya Seva"),
        "ysr_kalyanamasthu.json": ("CHANDRANNA-PELLI-KANUKA", "చంద్రన్న పెళ్లి కానుక", "Chandranna Pelli Kanuka"),
        "ysr_vahana_mitra.json": ("AUTO-DRIVERS-SEVALO", "ఆటో డ్రైవర్ల సేవలో", "Auto Drivers Sevalo"),
        "jagananna_vidya_deevena.json": ("POST-MATRIC-SCHOLARSHIP-RTF", None, None),
        "jagananna_vasathi_deevena.json": ("POST-MATRIC-SCHOLARSHIP-MTF", None, None),
    }

    @pytest.mark.parametrize("filename,expected", list(RENAMING_MAP.items()),
                             ids=list(RENAMING_MAP.keys()))
    def test_scheme_code_updated(self, filename, expected):
        scheme = load_scheme(filename)
        expected_code, _, _ = expected
        assert scheme["scheme_code"] == expected_code, \
            f"{filename}: expected code '{expected_code}', got '{scheme['scheme_code']}'"

    @pytest.mark.parametrize("filename,expected", [
        (k, v) for k, v in RENAMING_MAP.items() if v[1] is not None
    ], ids=[k for k, v in RENAMING_MAP.items() if v[1] is not None])
    def test_telugu_name_updated(self, filename, expected):
        scheme = load_scheme(filename)
        _, expected_te, _ = expected
        assert scheme["name_te"] == expected_te

    @pytest.mark.parametrize("filename,expected", [
        (k, v) for k, v in RENAMING_MAP.items() if v[2] is not None
    ], ids=[k for k, v in RENAMING_MAP.items() if v[2] is not None])
    def test_english_name_updated(self, filename, expected):
        scheme = load_scheme(filename)
        _, _, expected_en = expected
        assert scheme["name_en"] == expected_en


# ══════════════════════════════════════════════
# 3. REAL DATA VALIDATION — AMOUNTS & CRITERIA
# ══════════════════════════════════════════════

class TestRealDataAmounts:
    """Verify benefit amounts match real government data."""

    def test_annadata_sukhibhava_amount(self):
        """Rythu Bharosa increased from ₹13,500 to ₹20,000."""
        scheme = load_scheme("ysr_rythu_bharosa.json")
        assert "20,000" in scheme["benefit_amount"], \
            f"Annadata Sukhibhava should be ₹20,000, got: {scheme['benefit_amount']}"

    def test_pension_amount_range(self):
        """NTR Bharosa Pension ranges from ₹4,000 to ₹15,000."""
        scheme = load_scheme("ysr_pension_kanuka.json")
        assert "4,000" in scheme["benefit_amount"]
        assert "15,000" in scheme["benefit_amount"]

    def test_vahana_mitra_increased(self):
        """Auto Drivers Sevalo increased from ₹10,000 to ₹15,000."""
        scheme = load_scheme("ysr_vahana_mitra.json")
        assert "15,000" in scheme["benefit_amount"]

    def test_thalliki_vandanam_amount(self):
        """Thalliki Vandanam is ₹15,000 per child."""
        scheme = load_scheme("ysr_amma_vodi.json")
        assert "15,000" in scheme["benefit_amount"]

    def test_aarogyasri_coverage(self):
        """Dr. NTR Vaidya Seva covers up to ₹25 lakhs."""
        scheme = load_scheme("ysr_aarogyasri.json")
        assert "25" in scheme["benefit_amount"]

    def test_stree_shakti_free(self):
        """Stree Shakti is free bus travel."""
        scheme = load_scheme("stree_shakti.json")
        assert "free" in scheme["benefit_amount"].lower() or "zero" in scheme["benefit_amount"].lower()

    def test_deepam_cylinders(self):
        """Deepam 2.0 provides 3 free LPG cylinders."""
        scheme = load_scheme("deepam_2.json")
        assert "3" in scheme["benefit_amount"]
        assert "LPG" in scheme["benefit_amount"] or "cylinder" in scheme["benefit_amount"].lower()

    def test_yuva_galam_amount(self):
        """Yuva Galam provides ₹3,000/month."""
        scheme = load_scheme("yuva_galam.json")
        assert "3,000" in scheme["benefit_amount"]


class TestRealPensionTypes:
    """Validate all 12+ pension types from sspensions.ap.gov.in."""

    @pytest.fixture
    def pension_scheme(self):
        return load_scheme("ysr_pension_kanuka.json")

    def test_has_old_age_pension(self, pension_scheme):
        assert "old_age_pension" in pension_scheme["eligibility_criteria"]

    def test_old_age_60_plus(self, pension_scheme):
        oap = pension_scheme["eligibility_criteria"]["old_age_pension"]
        assert "60" in oap["age"]

    def test_old_age_st_50_plus(self, pension_scheme):
        """ST eligible at 50+ per official portal."""
        oap = pension_scheme["eligibility_criteria"]["old_age_pension"]
        assert "50" in oap["age"]

    def test_has_widow_pension(self, pension_scheme):
        assert "widow_pension" in pension_scheme["eligibility_criteria"]

    def test_has_disabled_pension_tiers(self, pension_scheme):
        ec = pension_scheme["eligibility_criteria"]
        assert "disabled_pension_40_79" in ec
        assert "disabled_pension_80_plus" in ec

    def test_disabled_40_79_amount(self, pension_scheme):
        assert "6,000" in pension_scheme["eligibility_criteria"]["disabled_pension_40_79"]["amount"]

    def test_disabled_80_plus_amount(self, pension_scheme):
        assert "10,000" in pension_scheme["eligibility_criteria"]["disabled_pension_80_plus"]["amount"]

    def test_has_weavers_pension(self, pension_scheme):
        assert "weavers_pension" in pension_scheme["eligibility_criteria"]

    def test_has_toddy_tappers_pension(self, pension_scheme):
        assert "toddy_tappers_pension" in pension_scheme["eligibility_criteria"]

    def test_has_fishermen_pension(self, pension_scheme):
        assert "fishermen_pension" in pension_scheme["eligibility_criteria"]

    def test_has_single_women_pension(self, pension_scheme):
        assert "single_women_pension" in pension_scheme["eligibility_criteria"]

    def test_has_transgender_pension(self, pension_scheme):
        assert "transgender_pension" in pension_scheme["eligibility_criteria"]

    def test_has_art_plhiv_pension(self, pension_scheme):
        assert "art_plhiv_pension" in pension_scheme["eligibility_criteria"]

    def test_has_ckdu_pension(self, pension_scheme):
        ec = pension_scheme["eligibility_criteria"]
        assert "ckdu_pension" in ec
        assert "10,000" in ec["ckdu_pension"]["amount"]

    def test_has_bedridden_pension(self, pension_scheme):
        ec = pension_scheme["eligibility_criteria"]
        assert "completely_bedridden" in ec
        assert "15,000" in ec["completely_bedridden"]["amount"]

    def test_pension_type_count(self, pension_scheme):
        """Should have at least 12 pension sub-types."""
        ec = pension_scheme["eligibility_criteria"]
        pension_types = [k for k, v in ec.items()
                        if isinstance(v, dict) and k not in ("universal_criteria",)]
        assert len(pension_types) >= 12, f"Expected 12+ pension types, got {len(pension_types)}: {pension_types}"


class TestRealEligibilityCriteria:
    """Validate eligibility criteria match official government sources."""

    def test_thalliki_vandanam_income_limits(self):
        """Stricter income: Rural ≤ ₹10,000/month, Urban ≤ ₹12,000/month."""
        scheme = load_scheme("ysr_amma_vodi.json")
        income = scheme["eligibility_criteria"]["income"]
        assert "10,000" in income
        assert "12,000" in income

    def test_thalliki_vandanam_land_limits(self):
        """Land limit: < 3 acres wet OR < 10 acres dry."""
        scheme = load_scheme("ysr_amma_vodi.json")
        assert "land" in scheme["eligibility_criteria"]
        land = scheme["eligibility_criteria"]["land"]
        assert "3" in land
        assert "10" in land

    def test_thalliki_vandanam_electricity_limit(self):
        """Electricity < 300 units/month."""
        scheme = load_scheme("ysr_amma_vodi.json")
        assert "electricity" in scheme["eligibility_criteria"]
        assert "300" in scheme["eligibility_criteria"]["electricity"]

    def test_annadata_tenant_farmers_eligible(self):
        """Tenant farmers eligible with CCRC."""
        scheme = load_scheme("ysr_rythu_bharosa.json")
        assert "tenant" in scheme["eligibility_criteria"].get("tenant_farmers", "").lower()

    def test_annadata_pm_kisan_linked(self):
        """Must be registered under PM-KISAN."""
        scheme = load_scheme("ysr_rythu_bharosa.json")
        assert "pm_kisan" in scheme["eligibility_criteria"] or \
               "PM-KISAN" in str(scheme["eligibility_criteria"])

    def test_vaidya_seva_coverage_amount(self):
        """₹25 lakh coverage per family per year."""
        scheme = load_scheme("ysr_aarogyasri.json")
        assert "25" in scheme["benefit_amount"]

    def test_vaidya_seva_949_treatments(self):
        """949+ treatments covered."""
        scheme = load_scheme("ysr_aarogyasri.json")
        assert "949" in str(scheme["eligibility_criteria"]) or \
               "949" in scheme["description_en"]

    def test_pelli_kanuka_category_amounts(self):
        """Chandranna Pelli Kanuka has category-based amounts."""
        scheme = load_scheme("ysr_kalyanamasthu.json")
        ec = scheme["eligibility_criteria"]
        assert "benefit_by_category" in ec
        cat = ec["benefit_by_category"]
        assert "40,000" in cat.get("sc_st_same_community", "")
        assert "75,000" in cat.get("inter_caste_marriage", "")
        assert "1,00,000" in cat.get("physically_challenged", "")

    def test_cheyutha_marked_inactive(self):
        """YSR Cheyutha status uncertain under TDP — should be inactive."""
        scheme = load_scheme("ysr_cheyutha.json")
        assert scheme["is_active"] is False


# ══════════════════════════════════════════════
# 4. SUPER SIX SCHEMES — NEW DATA
# ══════════════════════════════════════════════

class TestSuperSixSchemes:
    """Validate the 3 new Super Six scheme files."""

    def test_deepam_exists(self):
        scheme = load_scheme("deepam_2.json")
        assert scheme["scheme_code"] == "DEEPAM-2"
        assert scheme["is_active"] is True

    def test_stree_shakti_exists(self):
        scheme = load_scheme("stree_shakti.json")
        assert scheme["scheme_code"] == "STREE-SHAKTI"
        assert scheme["is_active"] is True

    def test_yuva_galam_exists(self):
        scheme = load_scheme("yuva_galam.json")
        assert scheme["scheme_code"] == "YUVA-GALAM"
        assert scheme["is_active"] is True

    def test_deepam_women_only(self):
        scheme = load_scheme("deepam_2.json")
        assert "women" in scheme["eligibility_criteria"]["gender"].lower() or \
               "మహిళ" in scheme["eligibility_criteria"].get("gender", "")

    def test_stree_shakti_no_application_needed(self):
        scheme = load_scheme("stree_shakti.json")
        ec = scheme["eligibility_criteria"]
        assert "no_application_needed" in ec or \
               "application" in str(ec).lower()

    def test_yuva_galam_age_range(self):
        scheme = load_scheme("yuva_galam.json")
        age = scheme["eligibility_criteria"]["age"]
        assert "22" in age
        assert "35" in age


# ══════════════════════════════════════════════
# 5. FAQ DATA — MATCHES SCHEME CODES
# ══════════════════════════════════════════════

class TestFAQData:
    """Verify FAQs use updated scheme codes and contain useful info."""

    @pytest.fixture
    def faqs(self):
        return load_faqs()

    def test_faq_scheme_codes_match_files(self, faqs):
        """Every FAQ scheme_code should have a corresponding scheme file."""
        scheme_codes = set()
        for f in SCHEMES_DIR.glob("*.json"):
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
                scheme_codes.add(data["scheme_code"])

        for faq_code in faqs.keys():
            assert faq_code in scheme_codes, \
                f"FAQ code '{faq_code}' has no matching scheme file"

    def test_no_old_scheme_codes_in_faqs(self, faqs):
        """No old YSR/Jagananna codes should remain in FAQ keys."""
        old_codes = ["YSR-AMMA-VODI", "YSR-RYTHU-BHAROSA", "YSR-PENSION-KANUKA",
                     "YSR-AAROGYASRI", "YSR-KALYANAMASTHU", "YSR-VAHANA-MITRA",
                     "JAGANANNA-VIDYA-DEEVENA", "JAGANANNA-VASATHI-DEEVENA"]
        for old_code in old_codes:
            assert old_code not in faqs, f"Old code '{old_code}' still in FAQs"

    def test_renamed_schemes_have_faqs(self, faqs):
        """All renamed schemes should have FAQ entries."""
        expected = ["THALLIKI-VANDANAM", "ANNADATA-SUKHIBHAVA", "NTR-BHAROSA-PENSION",
                    "DR-NTR-VAIDYA-SEVA", "CHANDRANNA-PELLI-KANUKA", "AUTO-DRIVERS-SEVALO",
                    "POST-MATRIC-SCHOLARSHIP-RTF"]
        for code in expected:
            assert code in faqs, f"Missing FAQs for renamed scheme: {code}"

    def test_super_six_have_faqs(self, faqs):
        """Super Six schemes should have FAQ entries."""
        for code in ["DEEPAM-2", "STREE-SHAKTI", "YUVA-GALAM"]:
            assert code in faqs, f"Missing FAQs for Super Six scheme: {code}"

    @pytest.mark.parametrize("code", list(load_faqs().keys()))
    def test_faq_bilingual(self, faqs, code):
        """Every FAQ should have both Telugu and English versions."""
        for faq in faqs[code]:
            assert "question_te" in faq, f"{code}: missing question_te"
            assert "answer_te" in faq, f"{code}: missing answer_te"
            assert "question_en" in faq, f"{code}: missing question_en"
            assert "answer_en" in faq, f"{code}: missing answer_en"
            assert len(faq["answer_te"]) > 10, f"{code}: answer_te too short"
            assert len(faq["answer_en"]) > 10, f"{code}: answer_en too short"


# ══════════════════════════════════════════════
# 6. TELUGU ALIAS MAPPING — OLD & NEW NAMES
# ══════════════════════════════════════════════

class TestTeluguAliasMapping:
    """Verify Telugu/English aliases resolve to correct new scheme codes."""

    # Old names should map to new codes
    OLD_TO_NEW = [
        ("అమ్మ ఒడి", "THALLIKI-VANDANAM"),
        ("amma vodi", "THALLIKI-VANDANAM"),
        ("రైతు భరోసా", "ANNADATA-SUKHIBHAVA"),
        ("rythu bharosa", "ANNADATA-SUKHIBHAVA"),
        ("ఆరోగ్యశ్రీ", "DR-NTR-VAIDYA-SEVA"),
        ("aarogyasri", "DR-NTR-VAIDYA-SEVA"),
        ("పెన్షన్", "NTR-BHAROSA-PENSION"),
        ("pension", "NTR-BHAROSA-PENSION"),
        ("కల్యాణమస్తు", "CHANDRANNA-PELLI-KANUKA"),
        ("వాహన మిత్ర", "AUTO-DRIVERS-SEVALO"),
        ("vidya deevena", "POST-MATRIC-SCHOLARSHIP-RTF"),
    ]

    # New names should also work
    NEW_NAMES = [
        ("తల్లికి వందనం", "THALLIKI-VANDANAM"),
        ("thalliki vandanam", "THALLIKI-VANDANAM"),
        ("అన్నదాత సుఖీభవ", "ANNADATA-SUKHIBHAVA"),
        ("annadata sukhibhava", "ANNADATA-SUKHIBHAVA"),
        ("NTR భరోసా పెన్షన్", "NTR-BHAROSA-PENSION"),
        ("ntr bharosa pension", "NTR-BHAROSA-PENSION"),
        ("NTR వైద్య సేవ", "DR-NTR-VAIDYA-SEVA"),
        ("చంద్రన్న పెళ్లి కానుక", "CHANDRANNA-PELLI-KANUKA"),
        ("ఆటో డ్రైవర్ల సేవలో", "AUTO-DRIVERS-SEVALO"),
    ]

    # Super Six aliases
    SUPER_SIX = [
        ("దీపం", "DEEPAM-2"),
        ("deepam", "DEEPAM-2"),
        ("gas cylinder", "DEEPAM-2"),
        ("స్త్రీ శక్తి", "STREE-SHAKTI"),
        ("stree shakti", "STREE-SHAKTI"),
        ("free bus", "STREE-SHAKTI"),
        ("యువగళం", "YUVA-GALAM"),
        ("yuva galam", "YUVA-GALAM"),
        ("unemployment allowance", "YUVA-GALAM"),
    ]

    @pytest.mark.parametrize("alias,expected_code", OLD_TO_NEW,
                             ids=[a for a, _ in OLD_TO_NEW])
    def test_old_name_resolves(self, alias, expected_code):
        result = fuzzy_match_scheme(alias)
        assert result == expected_code, f"'{alias}' → expected '{expected_code}', got '{result}'"

    @pytest.mark.parametrize("alias,expected_code", NEW_NAMES,
                             ids=[a for a, _ in NEW_NAMES])
    def test_new_name_resolves(self, alias, expected_code):
        result = fuzzy_match_scheme(alias)
        assert result == expected_code, f"'{alias}' → expected '{expected_code}', got '{result}'"

    @pytest.mark.parametrize("alias,expected_code", SUPER_SIX,
                             ids=[a for a, _ in SUPER_SIX])
    def test_super_six_resolves(self, alias, expected_code):
        result = fuzzy_match_scheme(alias)
        assert result == expected_code, f"'{alias}' → expected '{expected_code}', got '{result}'"

    def test_no_old_codes_in_aliases(self):
        """No alias should still point to old codes."""
        old_codes = {"YSR-AMMA-VODI", "YSR-RYTHU-BHAROSA", "YSR-PENSION-KANUKA",
                     "YSR-AAROGYASRI", "YSR-KALYANAMASTHU", "YSR-VAHANA-MITRA",
                     "JAGANANNA-VIDYA-DEEVENA", "JAGANANNA-VASATHI-DEEVENA"}
        for alias, code in SCHEME_ALIASES.items():
            assert code not in old_codes, f"Alias '{alias}' still points to old code '{code}'"


# ══════════════════════════════════════════════
# 7. FORM TEMPLATES — SCHEME CODE CONSISTENCY
# ══════════════════════════════════════════════

class TestFormTemplateConsistency:
    """Verify form templates reference valid, updated scheme codes."""

    @pytest.fixture
    def templates(self):
        return load_form_templates()

    @pytest.fixture
    def valid_codes(self):
        codes = set()
        for f in SCHEMES_DIR.glob("*.json"):
            with open(f, encoding="utf-8") as fp:
                codes.add(json.load(fp)["scheme_code"])
        return codes

    def test_no_old_codes_in_templates(self, templates):
        old_codes = {"YSR-AMMA-VODI", "YSR-RYTHU-BHAROSA", "YSR-PENSION-KANUKA",
                     "YSR-AAROGYASRI", "YSR-KALYANAMASTHU", "YSR-VAHANA-MITRA",
                     "JAGANANNA-VIDYA-DEEVENA"}
        for tmpl in templates:
            code = tmpl.get("scheme_code", "")
            assert code not in old_codes, f"Template '{tmpl['name_en']}' uses old code '{code}'"

    def test_template_codes_exist_in_schemes(self, templates, valid_codes):
        for tmpl in templates:
            code = tmpl.get("scheme_code", "")
            if code:  # some templates may not have scheme_code
                assert code in valid_codes, \
                    f"Template '{tmpl['name_en']}' references unknown scheme '{code}'"


# ══════════════════════════════════════════════
# 8. REAL-WORLD QUERY SIMULATION
# ══════════════════════════════════════════════

class TestRealWorldQueries:
    """Simulate real employee queries and verify correct scheme resolution."""

    CITIZEN_QUERIES_TE = [
        # Telugu queries that secretariat employees would ask
        ("అమ్మ ఒడి అర్హత చెప్పండి", "THALLIKI-VANDANAM"),
        ("రైతు భరోసా ఎంత వస్తుంది", "ANNADATA-SUKHIBHAVA"),
        ("పెన్షన్ కావాలి", "NTR-BHAROSA-PENSION"),
        ("ఆరోగ్యశ్రీ card ఎలా తీసుకోవాలి", "DR-NTR-VAIDYA-SEVA"),
        ("దీపం scheme ఏమిటి", "DEEPAM-2"),
        ("free bus travel", "STREE-SHAKTI"),
        ("నిరుద్యోగ భృతి", "YUVA-GALAM"),
    ]

    @pytest.mark.parametrize("query,expected", CITIZEN_QUERIES_TE,
                             ids=[q[:20] for q, _ in CITIZEN_QUERIES_TE])
    def test_telugu_query_resolves(self, query, expected):
        normalized = normalize_telugu_text(query)
        result = fuzzy_match_scheme(normalized)
        assert result == expected, f"Query '{query}' → expected '{expected}', got '{result}'"

    def test_mixed_telugu_english_query(self):
        """Employee asking in mixed Telugu-English."""
        result = fuzzy_match_scheme("pension scheme details")
        assert result == "NTR-BHAROSA-PENSION"

    def test_language_detection_telugu(self):
        """Telugu text should be detected as Telugu."""
        assert detect_language("తల్లికి వందనం అర్హత ఏమిటి?") == "te"

    def test_language_detection_english(self):
        assert detect_language("What is the eligibility for pension scheme?") == "en"

    def test_language_detection_mixed(self):
        """Mixed text with Telugu majority should be Telugu."""
        assert detect_language("అమ్మ ఒడి scheme details చెప్పండి") == "te"


# ══════════════════════════════════════════════
# 9. CROSS-CONSISTENCY CHECKS
# ══════════════════════════════════════════════

class TestCrossConsistency:
    """Verify consistency across scheme files, FAQs, aliases, and templates."""

    def test_all_active_schemes_have_aliases(self):
        """Every active scheme updated with real data should have at least one alias."""
        alias_targets = set(SCHEME_ALIASES.values())
        # Only enforce for schemes we've actively updated/created
        MUST_HAVE_ALIAS = {
            "THALLIKI-VANDANAM", "ANNADATA-SUKHIBHAVA", "NTR-BHAROSA-PENSION",
            "DR-NTR-VAIDYA-SEVA", "CHANDRANNA-PELLI-KANUKA", "AUTO-DRIVERS-SEVALO",
            "POST-MATRIC-SCHOLARSHIP-RTF", "POST-MATRIC-SCHOLARSHIP-MTF",
            "DEEPAM-2", "STREE-SHAKTI", "YUVA-GALAM",
        }
        missing = []
        for f in SCHEMES_DIR.glob("*.json"):
            with open(f, encoding="utf-8") as fp:
                scheme = json.load(fp)
            if scheme["scheme_code"] in MUST_HAVE_ALIAS:
                if scheme["scheme_code"] not in alias_targets:
                    missing.append(scheme["scheme_code"])
        assert not missing, f"Active schemes missing aliases: {missing}"

    def test_all_faq_codes_have_aliases(self):
        """Every FAQ scheme code should be reachable via alias."""
        faqs = load_faqs()
        alias_targets = set(SCHEME_ALIASES.values())
        for code in faqs.keys():
            assert code in alias_targets, \
                f"FAQ code '{code}' has no alias mapping"

    def test_renamed_schemes_have_previous_name(self):
        """Renamed schemes should record previous_name for traceability."""
        renamed_files = [
            "ysr_amma_vodi.json", "ysr_rythu_bharosa.json", "ysr_pension_kanuka.json",
            "ysr_aarogyasri.json", "ysr_kalyanamasthu.json", "ysr_vahana_mitra.json",
            "jagananna_vidya_deevena.json", "jagananna_vasathi_deevena.json",
        ]
        for filename in renamed_files:
            scheme = load_scheme(filename)
            assert "previous_name" in scheme, \
                f"{filename}: missing 'previous_name' field for traceability"
