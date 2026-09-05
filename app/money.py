"""Money handling.

Amounts cross the tool boundary as integer minor units -- 4000000 is Rs 40,000.
Display strings are produced here rather than by the model, so the agent never
has to do currency arithmetic or formatting to answer "how much is outstanding".

`parse_amount_text` is the other half of that boundary: the model hands over the
words the user actually typed ("40k", "1.5 lakh", "Rs 40,000/-") and Python does
the conversion. Financial arithmetic is not the model's job.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

# Symbol and minor-unit exponent per currency.
CURRENCIES: dict[str, tuple[str, int]] = {
    "INR": ("₹", 2),
    "USD": ("$", 2),
    "EUR": ("€", 2),
    "GBP": ("£", 2),
    "AED": ("AED ", 2),
    "JPY": ("¥", 0),
}

# A sanity ceiling. Nothing legitimate for a freelancer exceeds this, and it
# catches an amount that arrived already multiplied by 100 twice over.
MAX_AMOUNT_MINOR = 10_000_000_000  # 100 million major units

# Words and symbols that name a currency in free text. Longest first so "rs."
# is matched before "r", and "inr" before "in".
CURRENCY_TOKENS: list[tuple[str, str]] = [
    ("₹", "INR"), ("rupees", "INR"), ("rupee", "INR"), ("inr", "INR"),
    ("rs.", "INR"), ("rs", "INR"),
    ("$", "USD"), ("dollars", "USD"), ("dollar", "USD"), ("usd", "USD"),
    ("€", "EUR"), ("euros", "EUR"), ("euro", "EUR"), ("eur", "EUR"),
    ("£", "GBP"), ("pounds", "GBP"), ("pound", "GBP"), ("gbp", "GBP"),
    ("aed", "AED"), ("dirhams", "AED"), ("dirham", "AED"),
    ("¥", "JPY"), ("yen", "JPY"), ("jpy", "JPY"),
]

# Scale words. The Indian units matter here -- "1.5 lakh" is how the amount is
# spoken, and getting it wrong is a 100x error.
MULTIPLIERS: dict[str, Decimal] = {
    "k": Decimal(1_000),
    "thousand": Decimal(1_000),
    "thousands": Decimal(1_000),
    "l": Decimal(100_000),
    "lac": Decimal(100_000),
    "lacs": Decimal(100_000),
    "lakh": Decimal(100_000),
    "lakhs": Decimal(100_000),
    "m": Decimal(1_000_000),
    "mn": Decimal(1_000_000),
    "million": Decimal(1_000_000),
    "millions": Decimal(1_000_000),
    "cr": Decimal(10_000_000),
    "crore": Decimal(10_000_000),
    "crores": Decimal(10_000_000),
    "b": Decimal(1_000_000_000),
    "bn": Decimal(1_000_000_000),
    "billion": Decimal(1_000_000_000),
}

# A number, optionally followed by a scale word.
_AMOUNT_RE = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*([a-z]+)?",
    re.IGNORECASE,
)


class InvalidAmount(ValueError):
    """Raised when an amount cannot be trusted as money."""


def normalise_currency(currency: str | None) -> str:
    code = (currency or "INR").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise InvalidAmount(f"'{currency}' is not a 3-letter currency code.")
    return code


def minor_exponent(currency: str) -> int:
    """How many minor units make one major unit, as a power of ten."""
    return CURRENCIES.get(currency.upper(), ("", 2))[1]


def validate_amount_minor(amount_minor) -> int:
    """Return a trusted positive integer amount, or raise InvalidAmount.

    Rejects bools (which are ints in Python), floats carrying fractions of a
    paisa, zero, negatives, and implausibly large values.
    """
    if isinstance(amount_minor, bool):
        raise InvalidAmount("Amount must be a number, not a boolean.")
    if isinstance(amount_minor, float):
        if amount_minor != int(amount_minor):
            raise InvalidAmount(
                f"Amount {amount_minor} is not a whole number of minor units. "
                "Pass paise/cents as an integer, e.g. 4000000 for Rs 40,000."
            )
        amount_minor = int(amount_minor)
    if isinstance(amount_minor, str):
        stripped = amount_minor.strip().replace(",", "").replace("_", "")
        if not stripped.lstrip("-").isdigit():
            raise InvalidAmount(f"'{amount_minor}' is not a valid amount.")
        amount_minor = int(stripped)
    if not isinstance(amount_minor, int):
        raise InvalidAmount(f"'{amount_minor}' is not a valid amount.")
    if amount_minor <= 0:
        raise InvalidAmount("Amount must be greater than zero.")
    if amount_minor > MAX_AMOUNT_MINOR:
        raise InvalidAmount(
            f"Amount {amount_minor} minor units is implausibly large. "
            "Amounts are in paise/cents, so Rs 40,000 is 4000000."
        )
    return amount_minor


def format_money(amount_minor: int, currency: str = "INR") -> str:
    """Render minor units as a display string, e.g. 4000000 -> 'Rs 40,000.00'."""
    symbol, exponent = CURRENCIES.get(currency.upper(), (f"{currency.upper()} ", 2))
    value = Decimal(int(amount_minor)) / (Decimal(10) ** exponent)
    return f"{symbol}{value:,.{exponent}f}"


def detect_currency(text: str) -> str | None:
    """Find a currency named in free text, or None if it does not say."""
    lowered = text.lower()
    for token, code in CURRENCY_TOKENS:
        if token.isalpha():
            # Word tokens must stand alone, so "k" in "lakh" is not a match and
            # "in" inside "invoice" is not read as INR.
            if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", lowered):
                return code
        elif token in lowered:
            return code
    return None


def parse_amount_text(text: str, default_currency: str = "INR") -> dict:
    """Convert an amount as a person would write it into minor units.

    Handles "40k", "1.5 lakh", "Rs 40,000/-", "$250", "2 crore", "40000.50".

    Returns a dict with amount_minor, currency and a human-readable
    interpretation. Raises InvalidAmount when the text does not contain exactly
    one unambiguous amount -- the caller is expected to ask rather than guess.
    """
    if not text or not str(text).strip():
        raise InvalidAmount("No amount was given.")

    raw = str(text).strip()
    currency = detect_currency(raw) or normalise_currency(default_currency)

    if re.search(r"(?:^|\s)(?:minus|negative)\s+\d|-\s*\d", raw, re.IGNORECASE):
        raise InvalidAmount(
            f"'{raw}' looks like a negative amount. Amounts must be positive."
        )

    # Drop currency words so their letters cannot be read as scale words.
    cleaned = raw.lower()
    for token, _ in CURRENCY_TOKENS:
        if token.isalpha():
            cleaned = re.sub(rf"(?<![a-z]){re.escape(token)}(?![a-z])", " ", cleaned)
        else:
            cleaned = cleaned.replace(token, " ")
    cleaned = cleaned.replace("/-", " ")

    matches = _AMOUNT_RE.findall(cleaned)
    if not matches:
        raise InvalidAmount(f"Could not find an amount in '{raw}'.")

    parsed = []
    for number, unit in matches:
        unit = (unit or "").strip().lower()
        if unit and unit not in MULTIPLIERS:
            # A trailing word that is not a scale word, e.g. "40000 rupees paid"
            # once the currency word is stripped. Treat the number as bare.
            unit = ""
        try:
            value = Decimal(number.replace(",", ""))
        except InvalidOperation:
            raise InvalidAmount(f"'{number}' is not a valid number.") from None
        parsed.append(value * MULTIPLIERS.get(unit, Decimal(1)))

    if len(parsed) > 1:
        raise InvalidAmount(
            f"'{raw}' contains more than one amount "
            f"({', '.join(f'{p:,.2f}' for p in parsed)}). "
            "Ask which one is meant, and pass a single amount."
        )

    major = parsed[0]
    exponent = minor_exponent(currency)
    minor = major * (Decimal(10) ** exponent)

    if minor != minor.to_integral_value():
        raise InvalidAmount(
            f"'{raw}' is more precise than {currency} allows "
            f"({exponent} decimal places)."
        )

    amount_minor = validate_amount_minor(int(minor))
    return {
        "amount_minor": amount_minor,
        "currency": currency,
        "amount_display": format_money(amount_minor, currency),
    }
