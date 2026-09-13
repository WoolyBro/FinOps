"""Payment tools exposed to the Strands agent.

The payments table is the source of truth for what has been received. There is
no `amount_paid` column on invoices and the model never computes a balance --
every figure here is `SUM(payments.amount_minor)` read back out of SQLite.

Invoice status is a cache of that sum, recalculated inside the same transaction
as every write, so it cannot drift from the ledger.
"""

from __future__ import annotations

import sqlite3

from strands import tool

from app.database import get_db
from app.dates import InvalidDate, parse_date, today_iso
from app.models import INVOICE_SELECT, PAYMENT_SELECT, invoice_to_dict, payment_to_dict
from app.money import InvalidAmount, format_money, validate_amount_minor

# Statuses that cannot receive money.
CLOSED_STATUSES = ("CANCELLED",)


def paid_total(conn: sqlite3.Connection, invoice_id: int) -> int:
    """What has been received against an invoice, from the ledger alone."""
    row = conn.execute(
        "SELECT COALESCE(SUM(amount_minor), 0) AS total FROM payments WHERE invoice_id = ?",
        (invoice_id,),
    ).fetchone()
    return int(row["total"])


def recalculate_status(conn: sqlite3.Connection, invoice_id: int) -> str:
    """Derive the invoice status from the ledger and store it.

    UNPAID -> PARTIALLY_PAID -> PAID, and back down again if a payment is ever
    removed. A cancelled invoice keeps its status; money is not accepted
    against it in the first place.
    """
    invoice = conn.execute(
        "SELECT amount_minor, status FROM invoices WHERE id = ?", (invoice_id,)
    ).fetchone()
    if invoice is None:
        raise ValueError(f"No invoice with id {invoice_id}")
    if invoice["status"] in CLOSED_STATUSES:
        return invoice["status"]

    total = int(invoice["amount_minor"])
    paid = paid_total(conn, invoice_id)

    if paid <= 0:
        status = "UNPAID"
    elif paid >= total:
        status = "PAID"
    else:
        status = "PARTIALLY_PAID"

    conn.execute("UPDATE invoices SET status = ? WHERE id = ?", (status, invoice_id))
    return status


def _invoice_dict(conn: sqlite3.Connection, invoice_id: int) -> dict:
    row = conn.execute(INVOICE_SELECT + " WHERE i.id = ?", (invoice_id,)).fetchone()
    return invoice_to_dict(row)


@tool
def record_payment(
    invoice_id: int,
    amount_minor: int,
    payment_date: str | None = None,
    method: str | None = None,
    reference: str | None = None,
    allow_duplicate: bool = False,
) -> dict:
    """Record money received against an invoice.

    Amounts are in minor units -- use parse_amount first. The new balance and
    the invoice status are recalculated from the payment ledger; do not compute
    them yourself.

    Args:
        invoice_id: Numeric id of the invoice, from get_invoice or find_client.
        amount_minor: Amount received, in paise/cents. Positive integer.
        payment_date: YYYY-MM-DD. Defaults to today.
        method: How it arrived -- "UPI", "NEFT", "cash" -- only if the user
            said so. Omit it otherwise; do not guess.
        reference: Transaction reference or cheque number, only if the user
            gave one.
        allow_duplicate: Only set this to true after the user has confirmed a
            second identical payment really did arrive.

    Returns:
        status "recorded" with the payment and the refreshed invoice,
        "not_found", "duplicate_suspected", or "error" explaining the refusal.
    """
    try:
        amount_minor = validate_amount_minor(amount_minor)
    except InvalidAmount as exc:
        return {"status": "error", "error": str(exc)}

    try:
        paid_on = parse_date(payment_date or today_iso(), "payment date").isoformat()
    except InvalidDate as exc:
        return {"status": "error", "error": str(exc)}

    with get_db() as conn:
        invoice = conn.execute(
            "SELECT * FROM invoices WHERE id = ?", (invoice_id,)
        ).fetchone()
        if not invoice:
            return {
                "status": "not_found",
                "invoice_id": invoice_id,
                "error": f"No invoice with id {invoice_id}.",
            }

        currency = invoice["currency"]

        if invoice["status"] in CLOSED_STATUSES:
            return {
                "status": "error",
                "invoice_number": invoice["invoice_number"],
                "error": (
                    f"Invoice {invoice['invoice_number']} is "
                    f"{invoice['status']} and cannot take a payment."
                ),
            }

        total = int(invoice["amount_minor"])
        already_paid = paid_total(conn, invoice_id)
        outstanding = total - already_paid

        if outstanding <= 0:
            return {
                "status": "error",
                "invoice_number": invoice["invoice_number"],
                "error": (
                    f"Invoice {invoice['invoice_number']} is already paid in "
                    f"full ({format_money(total, currency)})."
                ),
            }

        if amount_minor > outstanding:
            return {
                "status": "error",
                "invoice_number": invoice["invoice_number"],
                "outstanding_minor": outstanding,
                "outstanding_display": format_money(outstanding, currency),
                "error": (
                    f"{format_money(amount_minor, currency)} is more than the "
                    f"{format_money(outstanding, currency)} outstanding on "
                    f"{invoice['invoice_number']}. Ask the user whether the "
                    "amount or the invoice is wrong."
                ),
            }

        if not allow_duplicate:
            existing = conn.execute(
                PAYMENT_SELECT
                + """ WHERE p.invoice_id = ?
                        AND p.amount_minor = ?
                        AND p.payment_date = ?
                        AND IFNULL(p.reference, '') = IFNULL(?, '')
                      ORDER BY p.id DESC LIMIT 1""",
                (invoice_id, amount_minor, paid_on, reference),
            ).fetchone()
            if existing:
                return {
                    "status": "duplicate_suspected",
                    "existing_payment": payment_to_dict(existing),
                    "hint": (
                        "An identical payment is already recorded against this "
                        "invoice on that date. Ask the user whether a second "
                        "payment really arrived before retrying with "
                        "allow_duplicate=true."
                    ),
                }

        cur = conn.execute(
            """INSERT INTO payments (invoice_id, amount_minor, payment_date,
                                     method, reference)
               VALUES (?, ?, ?, ?, ?)""",
            (invoice_id, amount_minor, paid_on, method, reference),
        )
        recalculate_status(conn, invoice_id)

        payment = conn.execute(
            PAYMENT_SELECT + " WHERE p.id = ?", (cur.lastrowid,)
        ).fetchone()

        return {
            "status": "recorded",
            "payment": payment_to_dict(payment),
            "invoice": _invoice_dict(conn, invoice_id),
        }


@tool
def get_payment(payment_id: int) -> dict:
    """Look up one payment by its numeric id.

    Args:
        payment_id: The payment's id, from record_payment or list_payments.

    Returns:
        status "found" with the payment, including the balance as it stood
        after that payment, or "not_found".
    """
    with get_db() as conn:
        row = conn.execute(
            PAYMENT_SELECT + " WHERE p.id = ?", (payment_id,)
        ).fetchone()
    if not row:
        return {"status": "not_found", "payment_id": payment_id}
    return {"status": "found", "payment": payment_to_dict(row)}


@tool
def list_payments(
    invoice_id: int | None = None,
    client_id: int | None = None,
    limit: int = 50,
) -> dict:
    """List recorded payments, most recent first.

    Args:
        invoice_id: Restrict to one invoice.
        client_id: Restrict to one client, across all their invoices.
        limit: Maximum number of payments to return.

    Returns:
        status "ok" with a count, the payments, and their total.
    """
    limit = max(1, min(int(limit or 50), 200))
    where: list[str] = []
    params: list = []

    if invoice_id is not None:
        where.append("p.invoice_id = ?")
        params.append(invoice_id)
    if client_id is not None:
        where.append("i.client_id = ?")
        params.append(client_id)

    sql = PAYMENT_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY p.id DESC LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    payments = [payment_to_dict(r) for r in rows]
    return {
        "status": "ok",
        "count": len(payments),
        "payments": payments,
        "total_received_minor": sum(p["amount_minor"] for p in payments),
    }


@tool
def generate_receipt(payment_id: int, regenerate: bool = False) -> dict:
    """Produce the receipt document for a payment that has been recorded.

    A receipt is only ever issued against a real payment record, and a payment
    keeps one receipt number for life. Calling this again returns the existing
    receipt rather than issuing a second number.

    Args:
        payment_id: The payment's id, from record_payment.
        regenerate: Redraw the PDF for a receipt that already exists, keeping
            its original receipt number.

    Returns:
        status "created" with the receipt_number and receipt_path,
        "already_exists" with the receipt already on file, "not_found", or
        "error". Do not tell the user a receipt exists unless this returned
        "created" or "already_exists".
    """
    from app.pdf_generator import create_receipt_pdf

    return create_receipt_pdf(payment_id, regenerate=regenerate)
