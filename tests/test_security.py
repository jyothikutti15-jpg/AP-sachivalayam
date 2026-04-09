from app.core.security import hash_aadhaar, mask_aadhaar, strip_pii, verify_aadhaar


def test_hash_aadhaar():
    h1 = hash_aadhaar("1234 5678 9012")
    # Spaces stripped before hashing — both formats must verify against the same hash.
    assert verify_aadhaar("123456789012", h1)
    # Different Aadhaar must not verify.
    assert not verify_aadhaar("123456789013", h1)
    # bcrypt hashes start with $2b$ (cost factor prefix).
    assert h1.startswith("$2b$")


def test_mask_aadhaar():
    assert mask_aadhaar("1234 5678 9012") == "XXXX XXXX 9012"
    assert mask_aadhaar("123456789012") == "XXXX XXXX 9012"


def test_strip_pii_aadhaar():
    text = "Citizen Aadhaar is 1234 5678 9012 and phone is 9876543210"
    result = strip_pii(text)
    assert "[AADHAAR]" in result
    assert "1234 5678 9012" not in result


def test_strip_pii_phone():
    text = "Call me at 9876543210 or +919876543210"
    result = strip_pii(text)
    assert "[PHONE]" in result
    assert "9876543210" not in result


def test_strip_pii_no_pii():
    text = "What is Amma Vodi eligibility?"
    result = strip_pii(text)
    assert result == text
