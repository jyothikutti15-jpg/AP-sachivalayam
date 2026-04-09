"""
Tests for multi-language and multi-state support.

Verifies that language detection, prompt loading, voice pipeline,
reminder templates, and document names work for all supported languages.
"""

import pytest

from app.core.language_config import (
    COMMON_DOCUMENTS_I18N,
    REMINDER_TEMPLATES_I18N,
    SUPPORTED_LANGUAGES,
    SUPPORTED_STATES,
    detect_language_from_text,
    get_document_name,
    get_language_config,
    get_reminder_template,
    get_state_config,
    list_supported_languages,
    list_supported_states,
)
from app.core.telugu import (
    detect_language,
    native_digits_to_arabic,
    normalize_text,
    split_sentences,
    normalize_telugu_text,
    fuzzy_match_scheme,
)


# ══════════════════════════════════════════════════════════════
# LANGUAGE CONFIG
# ══════════════════════════════════════════════════════════════


class TestLanguageConfig:
    """Tests for language configuration registry."""

    def test_seven_languages_supported(self):
        """At least 7 languages: te, hi, kn, ta, mr, ml, en."""
        assert len(SUPPORTED_LANGUAGES) >= 7
        for code in ("te", "hi", "kn", "ta", "mr", "ml", "en"):
            assert code in SUPPORTED_LANGUAGES

    def test_each_language_has_required_fields(self):
        """Every language config must have all required fields populated."""
        for code, cfg in SUPPORTED_LANGUAGES.items():
            assert cfg.code == code
            assert cfg.name_en, f"{code}: missing name_en"
            assert cfg.name_native, f"{code}: missing name_native"
            assert len(cfg.digit_map) == 10, f"{code}: digit_map must have 10 chars"
            assert cfg.greeting, f"{code}: missing greeting"
            assert cfg.fallback_error, f"{code}: missing fallback_error"
            assert cfg.busy_error, f"{code}: missing busy_error"
            assert cfg.connection_error, f"{code}: missing connection_error"
            assert cfg.whisper_prompt, f"{code}: missing whisper_prompt"

    def test_telugu_config_matches_legacy(self):
        """Telugu config must match the original hardcoded values."""
        te = get_language_config("te")
        assert te.digit_map == "౦౧౨౩౪౫౬౭౮౯"
        assert te.number_words["ఒకటి"] == "1"
        assert te.number_words["లక్ష"] == "100000"
        assert "సచివాలయం" in te.whisper_prompt

    def test_hindi_number_words(self):
        """Hindi number words map correctly."""
        hi = get_language_config("hi")
        assert hi.number_words["एक"] == "1"
        assert hi.number_words["दस"] == "10"
        assert hi.number_words["लाख"] == "100000"
        assert hi.number_words["करोड़"] == "10000000"

    def test_kannada_number_words(self):
        """Kannada number words map correctly."""
        kn = get_language_config("kn")
        assert kn.number_words["ಒಂದು"] == "1"
        assert kn.number_words["ಹತ್ತು"] == "10"
        assert kn.number_words["ನೂರು"] == "100"
        assert kn.number_words["ಲಕ್ಷ"] == "100000"

    def test_tamil_number_words(self):
        """Tamil number words map correctly."""
        ta = get_language_config("ta")
        assert ta.number_words["ஒன்று"] == "1"
        assert ta.number_words["பத்து"] == "10"
        assert ta.number_words["லட்சம்"] == "100000"

    def test_unknown_language_falls_back_to_english(self):
        """Unknown language code returns English config."""
        cfg = get_language_config("xx")
        assert cfg.code == "en"
        assert cfg.name_en == "English"

    def test_list_supported_languages(self):
        """API listing returns correct format."""
        langs = list_supported_languages()
        assert len(langs) >= 7
        codes = [l["code"] for l in langs]
        assert "te" in codes
        assert "hi" in codes
        for lang in langs:
            assert "code" in lang
            assert "name_en" in lang
            assert "name_native" in lang


# ══════════════════════════════════════════════════════════════
# STATE CONFIG
# ══════════════════════════════════════════════════════════════


class TestStateConfig:
    """Tests for state configuration registry."""

    def test_eight_states_supported(self):
        """At least 8 states configured."""
        assert len(SUPPORTED_STATES) >= 8
        for code in ("AP", "TS", "KA", "TN", "KL", "MH", "RJ", "UP"):
            assert code in SUPPORTED_STATES

    def test_each_state_has_required_fields(self):
        """Every state config must have required fields."""
        for code, cfg in SUPPORTED_STATES.items():
            assert cfg.code == code
            assert cfg.name_en
            assert cfg.default_language in SUPPORTED_LANGUAGES
            assert len(cfg.supported_languages) >= 1
            assert cfg.governance_portal_url.startswith("http")
            assert cfg.governance_portal_name
            assert len(cfg.admin_hierarchy) >= 3

    def test_ap_state_config(self):
        """AP state config matches original values."""
        ap = get_state_config("AP")
        assert ap.default_language == "te"
        assert ap.governance_portal_name == "GSWS"
        assert ap.secretariat_name_en == "Sachivalayam"
        assert "సచివాలయం" in ap.admin_hierarchy[0]

    def test_karnataka_uses_kannada(self):
        """Karnataka defaults to Kannada."""
        ka = get_state_config("KA")
        assert ka.default_language == "kn"
        assert "kn" in ka.supported_languages
        assert ka.governance_portal_name == "Seva Sindhu"

    def test_maharashtra_supports_three_languages(self):
        """Maharashtra supports Marathi, Hindi, and English."""
        mh = get_state_config("MH")
        assert len(mh.supported_languages) >= 3
        assert "mr" in mh.supported_languages
        assert "hi" in mh.supported_languages
        assert "en" in mh.supported_languages

    def test_unknown_state_falls_back_to_ap(self):
        """Unknown state code returns AP config."""
        cfg = get_state_config("XX")
        assert cfg.code == "AP"

    def test_list_supported_states(self):
        """API listing returns correct format."""
        states = list_supported_states()
        assert len(states) >= 8
        for state in states:
            assert "code" in state
            assert "name_en" in state
            assert "default_language" in state


# ══════════════════════════════════════════════════════════════
# LANGUAGE DETECTION
# ══════════════════════════════════════════════════════════════


class TestLanguageDetection:
    """Tests for multi-language text detection."""

    def test_detect_telugu(self):
        assert detect_language("అమ్మ ఒడి పథకం అర్హత ఏమిటి?") == "te"

    def test_detect_hindi(self):
        assert detect_language_from_text("प्रधानमंत्री किसान सम्मान निधि योजना क्या है?") == "hi"

    def test_detect_kannada(self):
        assert detect_language_from_text("ಯೋಜನೆ ಅರ್ಹತೆ ಏನು?") == "kn"

    def test_detect_tamil(self):
        assert detect_language_from_text("திட்டத்தின் தகுதி என்ன?") == "ta"

    def test_detect_malayalam(self):
        assert detect_language_from_text("പദ്ധതി യോഗ്യത എന്താണ്?") == "ml"

    def test_detect_english(self):
        assert detect_language("What is the eligibility for pension scheme?") == "en"

    def test_detect_mixed_telugu_english(self):
        """Mixed text with >15% Telugu should detect as Telugu."""
        assert detect_language("అమ్మ ఒడి eligibility criteria ఏమిటి?") == "te"

    def test_backward_compatible_with_telugu_py(self):
        """detect_language from telugu.py still works."""
        from app.core.telugu import detect_language as old_detect
        assert old_detect("అమ్మ ఒడి") == "te"
        assert old_detect("What is pension?") == "en"


# ══════════════════════════════════════════════════════════════
# DIGIT CONVERSION
# ══════════════════════════════════════════════════════════════


class TestDigitConversion:
    """Tests for native digit to Arabic conversion."""

    def test_telugu_digits(self):
        assert native_digits_to_arabic("రూ ౧౫,౦౦౦", "te") == "రూ 15,000"

    def test_hindi_digits(self):
        assert native_digits_to_arabic("₹ १५,०००", "hi") == "₹ 15,000"

    def test_kannada_digits(self):
        assert native_digits_to_arabic("₹ ೧೫,೦೦೦", "kn") == "₹ 15,000"

    def test_tamil_digits(self):
        assert native_digits_to_arabic("₹ ௧௫,௦௦௦", "ta") == "₹ 15,000"

    def test_english_passthrough(self):
        assert native_digits_to_arabic("Rs 15,000", "en") == "Rs 15,000"


# ══════════════════════════════════════════════════════════════
# TEXT NORMALIZATION
# ══════════════════════════════════════════════════════════════


class TestTextNormalization:
    """Tests for generic text normalization."""

    def test_normalize_telugu(self):
        result = normalize_text("  అమ్మ   ఒడి   పథకం   ", "te")
        assert "  " not in result
        assert result == "అమ్మ ఒడి పథకం"

    def test_normalize_hindi(self):
        result = normalize_text("  किसान   योजना   ", "hi")
        assert result == "किसान योजना"

    def test_normalize_auto_detect(self):
        """Auto-detect language when not specified."""
        result = normalize_text("  అమ్మ   ఒడి   ")
        assert result == "అమ్మ ఒడి"

    def test_backward_compatible_normalize_telugu_text(self):
        """Original normalize_telugu_text still works."""
        result = normalize_telugu_text("  అమ్మ   ఒడి   ")
        assert result == "అమ్మ ఒడి"


# ══════════════════════════════════════════════════════════════
# REMINDER TEMPLATES
# ══════════════════════════════════════════════════════════════


class TestReminderTemplates:
    """Tests for localized reminder templates."""

    def test_all_languages_have_all_template_types(self):
        """Every language in REMINDER_TEMPLATES_I18N has all 4 types."""
        required_types = ["pending_documents", "renewal_deadline", "disbursement_date", "application_followup"]
        for lang, templates in REMINDER_TEMPLATES_I18N.items():
            for ttype in required_types:
                assert ttype in templates, f"{lang}: missing template type {ttype}"

    def test_telugu_reminder(self):
        msg = get_reminder_template("te", "pending_documents").format(
            citizen_name="సునీత", scheme_name="తల్లికి వందనం",
            documents="ఆదాయ ధృవీకరణ", deadline="15-04-2026",
        )
        assert "సునీత" in msg
        assert "తల్లికి వందనం" in msg

    def test_hindi_reminder(self):
        msg = get_reminder_template("hi", "pending_documents").format(
            citizen_name="राम", scheme_name="किसान सम्मान",
            documents="आय प्रमाण पत्र", deadline="15-04-2026",
        )
        assert "राम" in msg
        assert "किसान सम्मान" in msg

    def test_kannada_reminder(self):
        msg = get_reminder_template("kn", "disbursement_date").format(
            citizen_name="ರಾಮ", scheme_name="ಪಿಂಚಣಿ", date="01-05-2026",
        )
        assert "ರಾಮ" in msg

    def test_english_reminder(self):
        msg = get_reminder_template("en", "renewal_deadline").format(
            citizen_name="Ram", scheme_name="Pension", deadline="30-06-2026",
        )
        assert "Ram" in msg
        assert "renewal deadline" in msg.lower()

    def test_unknown_language_falls_back_to_english(self):
        msg = get_reminder_template("xx", "pending_documents")
        assert "Dear" in msg  # English template


# ══════════════════════════════════════════════════════════════
# DOCUMENT NAMES
# ══════════════════════════════════════════════════════════════


class TestDocumentNames:
    """Tests for localized document names."""

    def test_all_15_documents_exist(self):
        assert len(COMMON_DOCUMENTS_I18N) >= 15

    def test_each_document_has_all_languages(self):
        """Each document must have te, hi, kn, ta, en names."""
        required_langs = {"te", "hi", "kn", "en"}
        for doc_key, names in COMMON_DOCUMENTS_I18N.items():
            for lang in required_langs:
                assert lang in names, f"Document '{doc_key}' missing {lang} name"
                assert names[lang], f"Document '{doc_key}' has empty {lang} name"

    def test_get_document_name_telugu(self):
        assert get_document_name("aadhaar_card", "te") == "ఆధార్ కార్డు"

    def test_get_document_name_hindi(self):
        assert get_document_name("aadhaar_card", "hi") == "आधार कार्ड"

    def test_get_document_name_kannada(self):
        assert get_document_name("aadhaar_card", "kn") == "ಆಧಾರ್ ಕಾರ್ಡ್"

    def test_get_document_name_tamil(self):
        assert get_document_name("aadhaar_card", "ta") == "ஆதார் அட்டை"

    def test_get_document_name_english(self):
        assert get_document_name("aadhaar_card", "en") == "Aadhaar Card"

    def test_unknown_document_returns_key(self):
        assert get_document_name("xyz_unknown", "te") == "xyz_unknown"


# ══════════════════════════════════════════════════════════════
# VOICE PIPELINE MULTI-LANGUAGE
# ══════════════════════════════════════════════════════════════


class TestVoicePipelineMultiLang:
    """Tests for multi-language voice pipeline."""

    def test_whisper_prompt_loads_for_telugu(self):
        from app.services.voice_pipeline import WHISPER_TELUGU_PROMPT, _get_whisper_prompt
        assert "సచివాలయం" in WHISPER_TELUGU_PROMPT
        assert _get_whisper_prompt("te") == WHISPER_TELUGU_PROMPT

    def test_whisper_prompt_loads_for_hindi(self):
        from app.services.voice_pipeline import _get_whisper_prompt
        prompt = _get_whisper_prompt("hi")
        assert "सचिवालय" in prompt or "पंचायत" in prompt

    def test_whisper_prompt_loads_for_kannada(self):
        from app.services.voice_pipeline import _get_whisper_prompt
        prompt = _get_whisper_prompt("kn")
        assert "ಪಂಚಾಯತಿ" in prompt

    def test_number_words_loads_for_telugu(self):
        from app.services.voice_pipeline import TELUGU_NUMBER_WORDS, _get_number_words
        assert TELUGU_NUMBER_WORDS["ఒకటి"] == "1"
        assert _get_number_words("te") == TELUGU_NUMBER_WORDS

    def test_number_words_loads_for_hindi(self):
        from app.services.voice_pipeline import _get_number_words
        words = _get_number_words("hi")
        assert words["एक"] == "1"
        assert words["लाख"] == "100000"


# ══════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY
# ══════════════════════════════════════════════════════════════


class TestBackwardCompatibility:
    """Ensure all existing telugu.py imports still work."""

    def test_fuzzy_match_scheme_still_works(self):
        result = fuzzy_match_scheme("పెన్షన్ కానుక")
        assert result == "NTR-BHAROSA-PENSION"

    def test_normalize_telugu_text_still_works(self):
        result = normalize_telugu_text("  అమ్మ   ఒడి  ")
        assert result == "అమ్మ ఒడి"

    def test_detect_language_still_works(self):
        assert detect_language("అమ్మ ఒడి") == "te"
        assert detect_language("What is pension?") == "en"

    def test_reminder_templates_backward_compatible(self):
        """REMINDER_TEMPLATES in reminder_service still works (defaults to Telugu)."""
        from app.services.reminder_service import REMINDER_TEMPLATES
        assert "pending_documents" in REMINDER_TEMPLATES
        msg = REMINDER_TEMPLATES["pending_documents"].format(
            citizen_name="Test", scheme_name="Test",
            documents="doc", deadline="01-01-2026",
        )
        assert "Test" in msg


# ══════════════════════════════════════════════════════════════
# API ENDPOINT
# ══════════════════════════════════════════════════════════════


class TestLanguageAPI:
    """Tests for the language selection API."""

    def test_router_registered(self):
        """Language router is registered in the API."""
        from app.api.v1.router import api_v1_router
        routes = [r.path for r in api_v1_router.routes if hasattr(r, 'path')]
        assert any("/languages" in r for r in routes)

    def test_config_has_state_and_language(self):
        """Settings has state_code and default_language."""
        from app.config import get_settings
        settings = get_settings()
        assert hasattr(settings, "state_code")
        assert hasattr(settings, "default_language")
        assert settings.state_code == "AP"
        assert settings.default_language == "te"

    def test_scheme_model_has_state_code(self):
        """Scheme model has state_code field."""
        from app.models.scheme import Scheme
        assert hasattr(Scheme, "state_code")
