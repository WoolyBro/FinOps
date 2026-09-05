"""Indian digit grouping for INR, western grouping for everything else."""

import pytest

from app.money import format_money, group_indian


@pytest.mark.parametrize(
    "digits,expected",
    [
        ("0", "0"),
        ("7", "7"),
        ("70", "70"),
        ("700", "700"),
        ("7000", "7,000"),
        ("40000", "40,000"),
        ("150000", "1,50,000"),
        ("1000000", "10,00,000"),
        ("12550000", "1,25,50,000"),
        ("1000000000", "1,00,00,00,000"),
    ],
)
def test_group_indian(digits, expected):
    assert group_indian(digits) == expected


@pytest.mark.parametrize(
    "amount_minor,expected",
    [
        (0, "\u20b90.00"),
        (100, "\u20b91.00"),
        (4_000_000, "\u20b940,000.00"),
        (15_000_000, "\u20b91,50,000.00"),
        (1_255_000_000, "\u20b91,25,50,000.00"),
        (4_000_050, "\u20b940,000.50"),
        (99, "\u20b90.99"),
    ],
)
def test_inr_uses_indian_grouping(amount_minor, expected):
    assert format_money(amount_minor, "INR") == expected


@pytest.mark.parametrize(
    "amount_minor,expected",
    [
        (0, "$0.00"),
        (25_000, "$250.00"),
        (15_000_000, "$150,000.00"),
        (1_255_000_000, "$12,550,000.00"),
    ],
)
def test_usd_uses_western_grouping(amount_minor, expected):
    assert format_money(amount_minor, "USD") == expected


@pytest.mark.parametrize(
    "amount_minor,expected",
    [
        (0, "\u00a50"),
        (150_000, "\u00a5150,000"),
        (12_550_000, "\u00a512,550,000"),
    ],
)
def test_zero_decimal_currency_has_no_decimal_places(amount_minor, expected):
    assert format_money(amount_minor, "JPY") == expected


def test_other_currencies_keep_their_decimal_rules():
    assert format_money(25_000, "EUR") == "\u20ac250.00"
    assert format_money(25_000, "GBP") == "\u00a3250.00"
    assert format_money(25_000, "AED") == "AED 250.00"


def test_unknown_currency_falls_back_to_its_code():
    assert format_money(25_000, "CAD") == "CAD 250.00"


def test_negative_amounts_keep_the_sign_outside_the_symbol():
    assert format_money(-15_000_000, "INR") == "-\u20b91,50,000.00"


def test_ascii_symbol_for_outputs_that_cannot_render_the_rupee_sign():
    assert format_money(15_000_000, "INR", ascii_symbol=True) == "Rs. 1,50,000.00"
    # Other currencies are unaffected -- their symbols are in the core fonts.
    assert format_money(25_000, "USD", ascii_symbol=True) == "$250.00"


def test_formatting_is_exact_at_scale():
    """Integer arithmetic only -- nothing here should ever round."""
    assert format_money(999_999_999, "INR") == "\u20b999,99,999.99"
