"""Unit coverage for the shared phone-number rule (M1.9-R3 Gap C)."""
import pytest
from app.utils.phone import normalize_phone


def test_none_and_blank_stay_optional():
    assert normalize_phone(None) is None
    assert normalize_phone("") is None
    assert normalize_phone("   ") is None


def test_valid_ten_digit_number_passes_through():
    assert normalize_phone("9876543210") == "9876543210"


def test_whitespace_and_separators_are_trimmed():
    assert normalize_phone("  9876543210  ") == "9876543210"
    assert normalize_phone("98765-43210") == "9876543210"
    assert normalize_phone("98765 43210") == "9876543210"


def test_country_and_std_prefixes_are_stripped():
    assert normalize_phone("+91 98765 43210") == "9876543210"
    assert normalize_phone("919876543210") == "9876543210"
    assert normalize_phone("09876543210") == "9876543210"


@pytest.mark.parametrize("bad", [
    "abc123",           # alphabetic garbage — the exact M1.9-R2 repro case
    "98abc54321",       # partial alphabetic
    "12345",            # too short
    "98765432",         # 8 digits
    "987654321",        # 9 digits
    "98765432100",      # 11 digits, no valid prefix to strip
    "5876543210",       # first digit outside 6-9
    "0876543210",       # first digit outside 6-9
    "987-654-321",      # 9 digits after stripping separators
])
def test_rejects_invalid_input(bad):
    with pytest.raises(ValueError):
        normalize_phone(bad)
