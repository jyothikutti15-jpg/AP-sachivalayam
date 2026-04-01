from app.core.telugu import (
    arabic_to_telugu,
    detect_language,
    fuzzy_match_scheme,
    normalize_telugu_text,
    split_telugu_sentences,
    telugu_to_arabic,
)


def test_telugu_to_arabic():
    assert telugu_to_arabic("౧౨౩") == "123"
    assert telugu_to_arabic("₹౧౫,౦౦౦") == "₹15,000"


def test_arabic_to_telugu():
    assert arabic_to_telugu("123") == "౧౨౩"


def test_detect_language_telugu():
    assert detect_language("అమ్మ ఒడి అర్హత ఏమిటి?") == "te"


def test_detect_language_english():
    assert detect_language("What is Amma Vodi eligibility?") == "en"


def test_detect_language_mixed():
    # Mixed text with more Telugu should be detected as Telugu
    assert detect_language("అమ్మ ఒడి scheme eligibility") == "te"


def test_normalize_telugu_text():
    text = "  అమ్మ   ఒడి   ₹౧౫,౦౦౦  "
    result = normalize_telugu_text(text)
    assert "15,000" in result  # Telugu digits converted
    assert "  " not in result  # Whitespace normalized


def test_fuzzy_match_scheme_exact():
    assert fuzzy_match_scheme("అమ్మ ఒడి") == "YSR-AMMA-VODI"
    assert fuzzy_match_scheme("amma vodi") == "YSR-AMMA-VODI"


def test_fuzzy_match_scheme_fuzzy():
    assert fuzzy_match_scheme("రైతు భరోసా") == "YSR-RYTHU-BHAROSA"


def test_fuzzy_match_scheme_no_match():
    assert fuzzy_match_scheme("random text xyz") is None


def test_split_telugu_sentences():
    text = "ఇది మొదటి వాక్యం. ఇది రెండవ వాక్యం. ఇది మూడవ వాక్యం."
    sentences = split_telugu_sentences(text)
    assert len(sentences) == 3
