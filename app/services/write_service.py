"""Write operations for the dashboard.

The agent is one way to change the ledger; this is the other. Both go through
exactly the same deterministic tools, so a client created by hand and a client
created by the agent are validated identically -- there is no second, weaker
path into the database.

That matters for more than tidiness: every guarantee the tools enforce
(duplicate detection, overpayment refusal, ledger-derived balances, gapless
invoice numbers) applies here automatically, because this module adds no
business logic of its own. It translates HTTP shapes into tool calls and
returns what the tool said.
"""

from __future__ import annotations

from app.money import InvalidAmount, parse_amount_text
from app.security import scrub
from app.tools.clients import create_client, update_client
from app.tools.invoices import create_invoice
from app.tools.payments import record_payment
from app.tools.reminders import (
    approve_reminder,
    cancel_reminder,
    create_payment_reminder,
)


class Rejected(ValueError):
    """A tool refused the operation. Carries the tool's own explanation."""

    def __init__(self, detail: str, status: str = "error", payload: dict | None = None):
        self.detail = detail
        self.tool_status = status
        self.payload = payload or {}
        super().__init__(detail)


def _unwrap(result: dict, ok_statuses: tuple[str, ...]) -> dict:
    """Return the tool result, or raise with the tool's own message.

    The tools already produce careful, human-readable refusals. Re-wording them
    here would only make the API vaguer than the thing it is wrapping.
    """
    status = result.get("status")
    if status in ok_statuses:
        return scrub(result)
    raise Rejected(
        result.get("error") or result.get("hint") or f"The operation was {status}.",
        status=status or "error",
        payload=scrub(result),
    )


# --- amounts ---------------------------------------------------------------


def parse_amount(text: str, default_currency: str = "INR") -> dict:
    """Turn what a person typed into minor units.

    The form lets you type "40k" or "1.5 lakh" exactly as you would say it, and
    the same parser the agent uses does the conversion. The browser never does
    money arithmetic.
    """
    try:
        return parse_amount_text(text, default_currency)
    except InvalidAmount as exc:
        raise Rejected(str(exc), status="invalid_amount") from exc


# --- clients ---------------------------------------------------------------


def add_client(
    name: str,
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    notes: str | None = None,
) -> dict:
    result = create_client(
        name=name, email=email, phone=phone, address=address, notes=notes
    )
    # already_exists is a success for a form: the client is on file either way,
    # and the caller is told which case it was.
    return _unwrap(result, ("created", "already_exists"))


def edit_client(client_id: int, field: str, value: str) -> dict:
    return _unwrap(update_client(client_id=client_id, field=field, value=value),
                   ("updated",))


# --- invoices --------------------------------------------------------------


def add_invoice(
    client_id: int,
    project: str,
    amount_minor: int,
    currency: str = "INR",
    issue_date: str | None = None,
    due_date: str | None = None,
    description: str | None = None,
    allow_duplicate: bool = False,
) -> dict:
    result = create_invoice(
        client_id=client_id,
        project=project,
        amount_minor=amount_minor,
        currency=currency,
        issue_date=issue_date,
        due_date=due_date,
        description=description,
        allow_duplicate=allow_duplicate,
    )
    # duplicate_suspected is surfaced as a refusal so the UI can ask, rather
    # than quietly writing a second identical invoice.
    return _unwrap(result, ("created",))


# --- payments --------------------------------------------------------------


def add_payment(
    invoice_id: int,
    amount_minor: int,
    payment_date: str | None = None,
    method: str | None = None,
    reference: str | None = None,
    allow_duplicate: bool = False,
) -> dict:
    result = record_payment(
        invoice_id=invoice_id,
        amount_minor=amount_minor,
        payment_date=payment_date,
        method=method,
        reference=reference,
        allow_duplicate=allow_duplicate,
    )
    return _unwrap(result, ("recorded",))


# --- reminders -------------------------------------------------------------


def draft_reminder(invoice_id: int, force: bool = False) -> dict:
    result = create_payment_reminder(invoice_id=invoice_id, force=force)
    return _unwrap(result, ("prepared", "already_exists"))


def approve(reminder_id: int) -> dict:
    return _unwrap(approve_reminder(reminder_id=reminder_id), ("approved",))


def cancel(reminder_id: int) -> dict:
    return _unwrap(cancel_reminder(reminder_id=reminder_id), ("cancelled",))
