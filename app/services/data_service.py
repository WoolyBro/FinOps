"""Read access to the business data, for the dashboard.

The API's read endpoints go through here rather than importing tools directly,
so a route handler stays a thin translation of HTTP to a service call. Every
figure still comes from the same deterministic tools the agent uses -- the
dashboard and the agent cannot disagree, because they read the same code.

Nothing in this module writes. Writes happen through the agent, or through the
tools directly, never as a side effect of rendering a page. The one exception
is document rendering, which is idempotent and marked as such below.
"""

from __future__ import annotations

from pathlib import Path

from app.pdf_generator import create_invoice_pdf, create_receipt_pdf
from app.tools.clients import find_client, list_clients
from app.tools.invoices import get_invoice, list_invoices
from app.tools.payments import get_payment, list_payments
from app.tools.reports import (
    get_client_balance,
    get_financial_summary,
    get_outstanding_invoices,
    get_overdue_invoices,
)


class NotFound(LookupError):
    """The requested record does not exist."""

    def __init__(self, kind: str, identifier):
        self.kind = kind
        self.identifier = identifier
        super().__init__(f"No {kind} matching {identifier!r}")


class DocumentUnavailable(RuntimeError):
    """The document could not be produced."""


# --- clients ---------------------------------------------------------------


def clients(limit: int = 100) -> dict:
    return list_clients(limit=limit)


def client_detail(client_id: int) -> dict:
    """A client with their balance and invoice history, for the client page."""
    balance = get_client_balance(client_id=client_id)
    if balance["status"] == "not_found":
        raise NotFound("client", client_id)

    invoices = list_invoices(client_id=client_id, limit=200)
    payments = list_payments(client_id=client_id, limit=200)
    return {
        "balance": balance,
        "invoices": invoices["invoices"],
        "payments": payments["payments"],
    }


def search_clients(name: str) -> dict:
    return find_client(name=name)


# --- invoices --------------------------------------------------------------


def invoices(client_id: int | None = None, status: str | None = None,
             limit: int = 100) -> dict:
    result = list_invoices(client_id=client_id, status=status, limit=limit)
    if result["status"] == "error":
        raise ValueError(result["error"])
    return result


def invoice_detail(invoice_id: int) -> dict:
    """One invoice with the payments recorded against it."""
    result = get_invoice(invoice_id=invoice_id)
    if result["status"] != "found":
        raise NotFound("invoice", invoice_id)

    history = list_payments(invoice_id=invoice_id, limit=200)
    return {"invoice": result["invoice"], "payments": history["payments"]}


def invoice_pdf(invoice_id: int) -> Path:
    """The invoice document, rendered if it is not on disk yet.

    Rendering is idempotent and derives every figure from the database, so a
    GET that produces the file changes no business state -- it only ensures the
    document matching current state exists.
    """
    result = get_invoice(invoice_id=invoice_id)
    if result["status"] != "found":
        raise NotFound("invoice", invoice_id)

    existing = result["invoice"].get("pdf_path")
    if existing and Path(existing).exists():
        return Path(existing)

    generated = create_invoice_pdf(invoice_id)
    if generated["status"] != "created":
        raise DocumentUnavailable(
            generated.get("error", "The invoice document could not be generated.")
        )
    return Path(generated["pdf_path"])


# --- payments --------------------------------------------------------------


def payments(invoice_id: int | None = None, client_id: int | None = None,
             limit: int = 100) -> dict:
    return list_payments(invoice_id=invoice_id, client_id=client_id, limit=limit)


def payment_detail(payment_id: int) -> dict:
    result = get_payment(payment_id=payment_id)
    if result["status"] != "found":
        raise NotFound("payment", payment_id)
    return result


def receipt_pdf(payment_id: int) -> Path:
    """The receipt for a payment, issued if it does not exist yet.

    A payment keeps one receipt number for life, so calling this repeatedly
    returns the same document rather than issuing a second receipt.
    """
    result = get_payment(payment_id=payment_id)
    if result["status"] != "found":
        raise NotFound("payment", payment_id)

    existing = result["payment"].get("receipt_path")
    if existing and Path(existing).exists():
        return Path(existing)

    generated = create_receipt_pdf(payment_id)
    if generated["status"] == "not_found":
        raise NotFound("payment", payment_id)
    if generated["status"] == "error":
        raise DocumentUnavailable(
            generated.get("error", "The receipt could not be generated.")
        )

    path = Path(generated["receipt_path"])
    if not path.exists():
        raise DocumentUnavailable("The receipt file is missing from disk.")
    return path


# --- reports ---------------------------------------------------------------


def summary(start_date: str | None = None, end_date: str | None = None) -> dict:
    result = get_financial_summary(start_date=start_date, end_date=end_date)
    if result["status"] == "error":
        raise ValueError(result["error"])
    return result


def overdue(client_id: int | None = None) -> dict:
    return get_overdue_invoices(client_id=client_id)


def outstanding(client_id: int | None = None) -> dict:
    return get_outstanding_invoices(client_id=client_id)
