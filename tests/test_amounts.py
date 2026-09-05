"""Phase 2.7: turning what a person types into minor units, deterministically."""

import pytest

from app.money import InvalidAmount, detect_currency, format_money, parse_amount_text
from app.tools.amounts import parse_amount


def call(t, **kw):
    """Invoke a Strands @tool directly, without going through an agent."""
    return t(**kw)


def minor(text, currency="INR"):
    return parse_amount_text(text, currency)["amount_minor"]


# --- plain numbers --------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("40000", 4_000_000),
        ("40,000", 4_000_000),
        ("40000.50", 4_000_050),
        ("0.75", 75),
        ("1", 100),
    ],
)
def test_plain_numbers(text, expected):
    assert minor(text) == expected


# --- scale words ----------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("40k", 4_000_000),
        ("40K", 4_000_000),
        ("40 k", 4_000_000),
        ("1.5k", 150_000),
        ("15k", 1_500_000),
        ("40 thousand", 4_000_000),
    ],
)
def test_thousands(text, expected):
    assert minor(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1 lakh", 10_000_000),
        ("1.5 lakh", 15_000_000),
        ("2 lakhs", 20_000_000),
        ("1 lac", 10_000_000),
        ("1 crore", 1_000_000_000),
    ],
)
def test_indian_scale_words(text, expected):
    """A lakh misread as a thousand is a 100x error, so these are load-bearing."""
    assert minor(text) == expected


@pytest.mark.parametrize(
    "text,expected", [("2m", 200_000_000), ("2 million", 200_000_000), ("2mn", 200_000_000)]
)
def test_millions(text, expected):
    assert minor(text) == expected


# --- currency -------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected_currency",
    [
        ("40k", "INR"),
        ("₹40,000", "INR"),
        ("Rs 40,000", "INR"),
        ("Rs. 40000", "INR"),
        ("INR 40000", "INR"),
        ("40000 rupees", "INR"),
        ("$250", "USD"),
        ("250 dollars", "USD"),
        ("USD 250", "USD"),
        ("€250", "EUR"),
        ("£250", "GBP"),
    ],
)
def test_currency_is_detected_from_the_text(text, expected_currency):
    assert parse_amount_text(text)["currency"] == expected_currency


def test_symbol_in_text_overrides_the_default_currency():
    assert parse_amount_text("$250", default_currency="INR")["currency"] == "USD"


def test_default_currency_is_used_when_text_is_silent():
    assert parse_amount_text("250", default_currency="USD")["currency"] == "USD"


def test_indian_notation_with_trailing_slash():
    assert minor("Rs 40,000/-") == 4_000_000


def test_zero_decimal_currency():
    """JPY has no minor unit, so 40k yen is 40000 minor units, not 4000000."""
    result = parse_amount_text("40k yen")
    assert result["currency"] == "JPY"
    assert result["amount_minor"] == 40_000


def test_currency_word_is_not_read_as_a_scale_word():
    # The "k" in "lakh" must not be stripped as a thousands marker, and the
    # "in" in "INR" must not swallow the number.
    assert minor("INR 1 lakh") == 10_000_000


# --- rejection ------------------------------------------------------------


@pytest.mark.parametrize("text", ["", "   ", "some money", "a few thousand"])
def test_rejects_text_with_no_number(text):
    with pytest.raises(InvalidAmount):
        parse_amount_text(text)


@pytest.mark.parametrize("text", ["-40k", "-40000", "minus 40k"])
def test_rejects_negative_amounts(text):
    with pytest.raises(InvalidAmount):
        parse_amount_text(text)


def test_rejects_zero():
    with pytest.raises(InvalidAmount):
        parse_amount_text("0")


def test_rejects_more_than_one_amount():
    """Rather than guessing which number the user meant."""
    with pytest.raises(InvalidAmount, match="more than one amount"):
        parse_amount_text("40000 and 15000")


def test_rejects_sub_paisa_precision():
    with pytest.raises(InvalidAmount, match="more precise"):
        parse_amount_text("40000.505")


def test_rejects_implausibly_large_amount():
    with pytest.raises(InvalidAmount):
        parse_amount_text("500 crore")


# --- the tool wrapper -----------------------------------------------------


def test_tool_returns_ok_with_display_string():
    result = call(parse_amount, text="40k")
    assert result["status"] == "ok"
    assert result["amount_minor"] == 4_000_000
    assert result["currency"] == "INR"
    assert result["amount_display"] == "₹40,000.00"
    assert result["input"] == "40k"


def test_tool_returns_error_rather_than_raising():
    result = call(parse_amount, text="some money")
    assert result["status"] == "error"
    assert "amount_minor" not in result
    assert result["error"]


def test_tool_ambiguity_error_explains_what_to_do():
    result = call(parse_amount, text="40000 and 15000")
    assert result["status"] == "error"
    assert "more than one amount" in result["error"]


def test_tool_default_currency():
    assert call(parse_amount, text="250", default_currency="USD")["currency"] == "USD"


# --- round trip -----------------------------------------------------------


@pytest.mark.parametrize(
    "text,display",
    [
        ("40k", "₹40,000.00"),
        ("1.5 lakh", "₹150,000.00"),
        ("$250", "$250.00"),
    ],
)
def test_parsed_amount_formats_back_for_display(text, display):
    parsed = parse_amount_text(text)
    assert format_money(parsed["amount_minor"], parsed["currency"]) == display


def test_detect_currency_returns_none_when_unnamed():
    assert detect_currency("40000") is None
