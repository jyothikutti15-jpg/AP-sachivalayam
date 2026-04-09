"""
Telugu language utilities — backward-compatible wrapper around the generic
language_config module. All existing imports continue to work.

New code should use app.core.language_config directly.
"""

import re

from rapidfuzz import fuzz, process

from app.core.language_config import (
    SUPPORTED_LANGUAGES,
    detect_language_from_text,
    get_language_config,
)

# Telugu digit mapping (kept for backward compatibility)
TELUGU_DIGITS = "౦౧౨౩౪౫౬౭౮౯"
ARABIC_DIGITS = "0123456789"

# Common scheme name aliases (Telugu → canonical English code)
SCHEME_ALIASES: dict[str, str] = {
    # Thalliki Vandanam (formerly YSR Amma Vodi)
    "తల్లికి వందనం": "THALLIKI-VANDANAM",
    "thalliki vandanam": "THALLIKI-VANDANAM",
    "అమ్మ ఒడి": "THALLIKI-VANDANAM",
    "amma vodi": "THALLIKI-VANDANAM",
    "జగనన్న అమ్మ ఒడి": "THALLIKI-VANDANAM",
    # Annadata Sukhibhava (formerly YSR Rythu Bharosa)
    "అన్నదాత సుఖీభవ": "ANNADATA-SUKHIBHAVA",
    "annadata sukhibhava": "ANNADATA-SUKHIBHAVA",
    "రైతు భరోసా": "ANNADATA-SUKHIBHAVA",
    "rythu bharosa": "ANNADATA-SUKHIBHAVA",
    # NTR Bharosa Pension (formerly YSR Pension Kanuka)
    "NTR భరోసా పెన్షన్": "NTR-BHAROSA-PENSION",
    "ntr bharosa pension": "NTR-BHAROSA-PENSION",
    "పెన్షన్": "NTR-BHAROSA-PENSION",
    "pension": "NTR-BHAROSA-PENSION",
    "పెన్షన్ కానుక": "NTR-BHAROSA-PENSION",
    # Dr. NTR Vaidya Seva (formerly YSR Aarogyasri)
    "NTR వైద్య సేవ": "DR-NTR-VAIDYA-SEVA",
    "ntr vaidya seva": "DR-NTR-VAIDYA-SEVA",
    "ఆరోగ్యశ్రీ": "DR-NTR-VAIDYA-SEVA",
    "aarogyasri": "DR-NTR-VAIDYA-SEVA",
    "పేదల వైద్యం": "DR-NTR-VAIDYA-SEVA",
    # Chandranna Pelli Kanuka (formerly YSR Kalyanamasthu)
    "చంద్రన్న పెళ్లి కానుక": "CHANDRANNA-PELLI-KANUKA",
    "chandranna pelli kanuka": "CHANDRANNA-PELLI-KANUKA",
    "కల్యాణమస్తు": "CHANDRANNA-PELLI-KANUKA",
    "kalyanamastu": "CHANDRANNA-PELLI-KANUKA",
    "పెళ్ళి కానుక": "CHANDRANNA-PELLI-KANUKA",
    "pelli kanuka": "CHANDRANNA-PELLI-KANUKA",
    # Auto Drivers Sevalo (formerly YSR Vahana Mitra)
    "ఆటో డ్రైవర్ల సేవలో": "AUTO-DRIVERS-SEVALO",
    "auto drivers sevalo": "AUTO-DRIVERS-SEVALO",
    "వాహన మిత్ర": "AUTO-DRIVERS-SEVALO",
    "vahana mitra": "AUTO-DRIVERS-SEVALO",
    # Post Matric Scholarship RTF (formerly Vidya Deevena)
    "పోస్ట్ మెట్రిక్ స్కాలర్‌షిప్": "POST-MATRIC-SCHOLARSHIP-RTF",
    "post matric scholarship": "POST-MATRIC-SCHOLARSHIP-RTF",
    "జగనన్న విద్యా దీవెన": "POST-MATRIC-SCHOLARSHIP-RTF",
    "vidya deevena": "POST-MATRIC-SCHOLARSHIP-RTF",
    # Post Matric Scholarship MTF (formerly Vasathi Deevena)
    "జగనన్న వసతి దీవెన": "POST-MATRIC-SCHOLARSHIP-MTF",
    "vasathi deevena": "POST-MATRIC-SCHOLARSHIP-MTF",
    # YSR Cheyutha (status uncertain)
    "చేయూత": "YSR-CHEYUTHA",
    "cheyutha": "YSR-CHEYUTHA",
    # Super Six — New schemes
    "దీపం": "DEEPAM-2",
    "deepam": "DEEPAM-2",
    "gas cylinder": "DEEPAM-2",
    "స్త్రీ శక్తి": "STREE-SHAKTI",
    "stree shakti": "STREE-SHAKTI",
    "free bus": "STREE-SHAKTI",
    "ఉచిత బస్సు": "STREE-SHAKTI",
    "యువగళం": "YUVA-GALAM",
    "yuva galam": "YUVA-GALAM",
    "నిరుద్యోగ భృతి": "YUVA-GALAM",
    "nirudyoga bruthi": "YUVA-GALAM",
    "unemployment allowance": "YUVA-GALAM",
    # Unchanged schemes
    "ఆసరా": "YSR-ASARA",
    "asara": "YSR-ASARA",
    "నవశకం": "NAVASAKAM",
    "navasakam": "NAVASAKAM",
    "జల కళ": "YSR-JALA-KALA",
    "jala kala": "YSR-JALA-KALA",
    "సున్నా వడ్డీ": "YSR-SUNNA-VADDI",
    "sunna vaddi": "YSR-SUNNA-VADDI",
    "మత్స్యకార భరోసా": "YSR-MATSYAKARA-BHAROSA",
    "matsyakara bharosa": "YSR-MATSYAKARA-BHAROSA",
    "నేతన్న నేస్తం": "YSR-NETHANNA-NESTHAM",
    "nethanna nestham": "YSR-NETHANNA-NESTHAM",
    "బీమా": "YSR-BIMA",
    "bima": "YSR-BIMA",
    "కంటి వెలుగు": "YSR-KANTI-VELUGU",
    "kanti velugu": "YSR-KANTI-VELUGU",
    "జగనన్న తోడు": "JAGANANNA-THODU",
    "jagananna thodu": "JAGANANNA-THODU",
    "చేదోడు": "JAGANANNA-CHEDODU",
    "chedodu": "JAGANANNA-CHEDODU",
    "పేదలందరికీ ఇళ్ళు": "PEDALANDARIKI-ILLU",
    "pedalandariki illu": "PEDALANDARIKI-ILLU",
    "ఇళ్ళ పథకం": "PEDALANDARIKI-ILLU",
    "housing scheme": "PEDALANDARIKI-ILLU",
    "గోరుముద్ద": "JAGANANNA-GORUMUDDA",
    "gorumudda": "JAGANANNA-GORUMUDDA",
    "mid day meal": "JAGANANNA-GORUMUDDA",
    "విద్యా కానుక": "JAGANANNA-VIDYA-KANUKA",
    "vidya kanuka": "JAGANANNA-VIDYA-KANUKA",
    "school kit": "JAGANANNA-VIDYA-KANUKA",
    "నవోదయం": "YSR-NAVODAYAM",
    "navodayam": "YSR-NAVODAYAM",
    "యంత్ర సేవ": "YSR-YANTRA-SEVA",
    "yantra seva": "YSR-YANTRA-SEVA",
    "లా నేస్తం": "YSR-LAW-NESTHAM",
    "law nestham": "YSR-LAW-NESTHAM",
    "సంపూర్ణ పోషణ": "YSR-SAMPOORNA-POSHANA",
    "sampoorna poshana": "YSR-SAMPOORNA-POSHANA",
    "ఉద్యోగ హామీ": "YSR-EHF",
    "employment guarantee": "YSR-EHF",
    "mgnregs": "YSR-EHF",
    "జగనన్న సురక్ష": "JAGANANNA-SURAKSHA",
    "suraksha": "JAGANANNA-SURAKSHA",
}


def telugu_to_arabic(text: str) -> str:
    """Convert Telugu digits to Arabic digits."""
    table = str.maketrans(TELUGU_DIGITS, ARABIC_DIGITS)
    return text.translate(table)


def arabic_to_telugu(text: str) -> str:
    """Convert Arabic digits to Telugu digits."""
    table = str.maketrans(ARABIC_DIGITS, TELUGU_DIGITS)
    return text.translate(table)


def normalize_telugu_text(text: str) -> str:
    """Normalize Telugu text for consistent processing."""
    # Convert Telugu digits to Arabic for processing
    text = telugu_to_arabic(text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Remove zero-width characters common in Telugu text
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    return text


def detect_language(text: str) -> str:
    """Detect language from text. Supports Telugu, Hindi, Kannada, Tamil, Malayalam, Marathi, English.

    Uses the generic multi-language detection from language_config,
    but defaults to settings.default_language instead of "en" when no script detected.
    """
    return detect_language_from_text(text)


def fuzzy_match_scheme(query: str, threshold: int = 70) -> str | None:
    """Fuzzy match a query to a known scheme alias."""
    query_lower = query.lower().strip()

    # Exact match first
    if query_lower in SCHEME_ALIASES:
        return SCHEME_ALIASES[query_lower]

    # Fuzzy match
    aliases = list(SCHEME_ALIASES.keys())
    match = process.extractOne(query_lower, aliases, scorer=fuzz.token_set_ratio)
    if match and match[1] >= threshold:
        return SCHEME_ALIASES[match[0]]

    return None


def split_telugu_sentences(text: str) -> list[str]:
    """Split Telugu text into sentences. Telugu uses '।' and '.' as sentence endings."""
    sentences = re.split(r"[।.!?]\s*", text)
    return [s.strip() for s in sentences if s.strip()]


# ══════════════════════════════════════════════════════════════
# GENERIC MULTI-LANGUAGE HELPERS
# ══════════════════════════════════════════════════════════════


def native_digits_to_arabic(text: str, lang_code: str = "te") -> str:
    """Convert native script digits to Arabic digits for any supported language."""
    config = get_language_config(lang_code)
    if config.digit_map == ARABIC_DIGITS:
        return text
    table = str.maketrans(config.digit_map, ARABIC_DIGITS)
    return text.translate(table)


def normalize_text(text: str, lang_code: str | None = None) -> str:
    """Normalize text for any supported language.

    Auto-detects language if lang_code is not provided.
    """
    if lang_code is None:
        lang_code = detect_language(text)
    # Convert native digits to Arabic
    text = native_digits_to_arabic(text, lang_code)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Remove zero-width characters
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    return text


def split_sentences(text: str, lang_code: str | None = None) -> list[str]:
    """Split text into sentences for any supported language."""
    if lang_code is None:
        lang_code = detect_language(text)
    config = get_language_config(lang_code)
    pattern = f"[{re.escape(config.sentence_delimiters)}]\\s*"
    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]
