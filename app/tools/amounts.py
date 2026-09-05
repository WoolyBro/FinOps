"""The amount-parsing tool.

This exists to keep financial arithmetic out of the model. The user says
"40k"; the agent passes those characters here verbatim and gets back
4000000 paise. It does not multiply anything itself.
"""

from __future__ import annotations

from strands import tool

from app.money import InvalidAmount, parse_amount_text


@tool
def parse_amount(text: str, default_currency: str = "INR") -> dict:
    """Convert an amount written the way a person says it into minor units.

    Always use this before create_invoice or record_payment. Pass the user's
    own words -- "40k", "1.5 lakh", "Rs 40,000", "$250" -- rather than
    converting the number yourself.

    Pass only the amount phrase, not the whole sentence: "40k", not
    "40k due on the 15th".

    Args:
        text: The amount as the user wrote it.
        default_currency: Currency to assume when the text does not name one.

    Returns:
        status "ok" with amount_minor, currency and amount_display, or "error"
        with an explanation when the text is not a single unambiguous amount.
    """
    try:
        parsed = parse_amount_text(text, default_currency)
    except InvalidAmount as exc:
        return {"status": "error", "input": text, "error": str(exc)}

    return {
        "status": "ok",
        "input": text,
        "amount_minor": parsed["amount_minor"],
        "currency": parsed["currency"],
        "amount_display": parsed["amount_display"],
    }
