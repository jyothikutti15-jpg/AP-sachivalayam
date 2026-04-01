import re

from rapidfuzz import fuzz, process

# Telugu digit mapping
TELUGU_DIGITS = "౦౧౨౩౪౫౬౭౮౯"
ARABIC_DIGITS = "0123456789"

# Common scheme name aliases (Telugu → canonical English code)
SCHEME_ALIASES: dict[str, str] = {
    "అమ్మ ఒడి": "YSR-AMMA-VODI",
    "amma vodi": "YSR-AMMA-VODI",
    "రైతు భరోసా": "YSR-RYTHU-BHAROSA",
    "rythu bharosa": "YSR-RYTHU-BHAROSA",
    "ఆసరా": "YSR-ASARA",
    "asara": "YSR-ASARA",
    "జగనన్న విద్యా దీవెన": "JAGANANNA-VIDYA-DEEVENA",
    "vidya deevena": "JAGANANNA-VIDYA-DEEVENA",
    "జగనన్న వసతి దీవెన": "JAGANANNA-VASATHI-DEEVENA",
    "vasathi deevena": "JAGANANNA-VASATHI-DEEVENA",
    "ఆరోగ్యశ్రీ": "YSR-AAROGYASRI",
    "aarogyasri": "YSR-AAROGYASRI",
    "పేదల వైద్యం": "YSR-AAROGYASRI",
    "చేయూత": "YSR-CHEYUTHA",
    "cheyutha": "YSR-CHEYUTHA",
    "కల్యాణమస్తు": "YSR-KALYANAMASTHU",
    "kalyanamastu": "YSR-KALYANAMASTHU",
    "జగనన్న అమ్మ ఒడి": "YSR-AMMA-VODI",
    "పెన్షన్": "YSR-PENSION-KANUKA",
    "pension": "YSR-PENSION-KANUKA",
    "నవశకం": "NAVASAKAM",
    "navasakam": "NAVASAKAM",
    "జల కళ": "YSR-JALA-KALA",
    "jala kala": "YSR-JALA-KALA",
    "సున్నా వడ్డీ": "YSR-SUNNA-VADDI",
    "sunna vaddi": "YSR-SUNNA-VADDI",
    # Additional schemes
    "మత్స్యకార భరోసా": "YSR-MATSYAKARA-BHAROSA",
    "matsyakara bharosa": "YSR-MATSYAKARA-BHAROSA",
    "వాహన మిత్ర": "YSR-VAHANA-MITRA",
    "vahana mitra": "YSR-VAHANA-MITRA",
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
    "పెళ్ళి కానుక": "YSR-PELLI-KANUKA",
    "pelli kanuka": "YSR-PELLI-KANUKA",
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
    """Detect if text is predominantly Telugu or English."""
    telugu_chars = len(re.findall(r"[\u0C00-\u0C7F]", text))
    total_alpha = len(re.findall(r"[a-zA-Z\u0C00-\u0C7F]", text))
    if total_alpha == 0:
        return "te"
    return "te" if telugu_chars / total_alpha > 0.15 else "en"


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
