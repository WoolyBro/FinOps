"""Money handling.

Amounts cross the tool boundary as integer minor units -- 4000000 is Rs 40,000.
Display strings are produced here rather than by the model, so the agent never
has to do currency arithmetic or formatting to answer "how much is outstanding".
"""

from __future__ import annotations

from decimal import Decimal

# Symbol and minor-unit exponent per currency.
CURRENCIES: dict[str, tuple[str, int]] = {
    "INR": ("\u20b9", 2),
    "USD": ("$", 2),
    "EUR": ("\u20ac", 2),
    "GBP": ("\u00a3", 2),
    "AED": ("AED ", 2),
    "JPY": ("\u00a5", 0),
}

# A sanity ceiling. Nothing legitimate for a freelancer exceeds this, and it
# catches an amount that arrived already multiplied by 100 twice over.
MAX_AMOUNT_MINOR = 10_000_000_000  # 100 million major units


class InvalidAmount(ValueError):
    """Raised when an amount cannot be trusted as money."""


def normalise_currency(currency: str | None) -> str:
    code = (currency or "INR").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise InvalidAmount(f"'{currency}' is not a 3-letter currency code.")
    return code


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
