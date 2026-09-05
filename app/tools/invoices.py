"""Invoice tools exposed to the Strands agent.

The governing rule of this module: the tool enforces reality, the model
interprets it. The model never chooses an invoice number, never computes a
balance, and never decides whether an invoice is overdue -- it asks.
"""

from __future__ import annotations

import sqlite3

from strands import tool

from app.config import INVOICE_PREFIX
from app.database import get_db, next_counter, normalise_name
from app.dates import InvalidDate, days_between, parse_date, today_iso
from app.models import INVOICE_SELECT, invoice_to_dict
from app.money import InvalidAmount, normalise_currency, validate_amount_minor

VALID_STATUSES = ("UNPAID", "PARTIALLY_PAID", "PAID", "CANCELLED")

DUPLICATE_WHERE = """
 WHERE i.client_id = ?
   AND LOWER(TRIM(i.project)) = ?
   AND i.amount_minor = ?
   AND i.issue_date = ?
   AND i.status != 'CANCELLED'
 ORDER BY i.id DESC LIMIT 1
"""


def format_invoice_number(sequence: int) -> str:
    """Render a counter value as a document number, e.g. 8 becomes FF-0008."""
    return f"{INVOICE_PREFIX}-{sequence:04d}"


def reserve_invoice_number(conn: sqlite3.Connection) -> str:
    """Consume the next invoice number inside the caller's transaction.

    Called only from create_invoice, so a rolled-back insert returns the number
    rather than leaving a gap in the sequence.
    """
    return format_invoice_number(next_counter(conn, "invoice"))


@tool
def get_next_invoice_number() -> dict:
    """Show what the next invoice number will be, without reserving it.

    This is a preview for answering questions. Do not pass the result to
    create_invoice -- that tool assigns its own number from the database.

    Returns:
        status "ok" with the next invoice number.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT value FROM counters WHERE name = 'invoice'"
        ).fetchone()
    current = int(row["value"]) if row else 0
    return {
        "status": "ok",
        "next_invoice_number": format_invoice_number(current + 1),
        "note": "Preview only. create_invoice assigns the real number.",
    }


@tool
def create_invoice(
    client_id: int,
    project: str,
    amount_minor: int,
    currency: str = "INR",
    issue_date: str | None = None,
    due_date: str | None = None,
    description: str | None = None,
    allow_duplicate: bool = False,
) -> dict:
    """Create an invoice for an existing client.

    The invoice number is assigned by the database, not by you. Amounts are in
    minor units: 40000 rupees is 4000000, 250 dollars is 25000.

    Args:
        client_id: Numeric id of an existing client, from find_client.
        project: What the invoice is for, e.g. "Website development".
        amount_minor: Total amount in paise/cents. Must be a positive integer.
        currency: 3-letter code. Defaults to INR.
        issue_date: YYYY-MM-DD. Defaults to today.
        due_date: YYYY-MM-DD. Optional, but ask the user for it rather than
            inventing one.
        description: Longer free-text description of the work.
        allow_duplicate: Only set this to true after the user has confirmed they
            really do want a second identical invoice.

    Returns:
        status "created" with the invoice, "not_found" if the client does not
        exist, "duplicate_suspected" with the existing invoice, or "error".
    """
    if not project or not project.strip():
        return {
            "status": "error",
            "error": "An invoice needs a project or description of the work.",
        }

    try:
        amount_minor = validate_amount_minor(amount_minor)
        currency = normalise_currency(currency)
    except InvalidAmount as exc:
        return {"status": "error", "error": str(exc)}

    try:
        issue = parse_date(issue_date or today_iso(), "issue date").isoformat()
        due = parse_date(due_date, "due date").isoformat() if due_date else None
    except InvalidDate as exc:
        return {"status": "error", "error": str(exc)}

    if due and days_between(issue, due) < 0:
        return {
            "status": "error",
            "error": f"Due date {due} is before the issue date {issue}.",
        }

    project = project.strip()

    with get_db() as conn:
        client = conn.execute(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        if not client:
            return {
                "status": "not_found",
                "client_id": client_id,
                "error": f"No client with id {client_id}.",
                "hint": "Use find_client, and ask the user before creating one.",
            }

        if not allow_duplicate:
            existing = conn.execute(
                INVOICE_SELECT + DUPLICATE_WHERE,
                (client_id, normalise_name(project), amount_minor, issue),
            ).fetchone()
            if existing:
                return {
                    "status": "duplicate_suspected",
                    "existing_invoice": invoice_to_dict(existing),
                    "hint": (
                        "An identical invoice already exists for this client "
                        "today. Ask the user whether they really want a second "
                        "one before retrying with allow_duplicate=true."
                    ),
                }

        invoice_number = reserve_invoice_number(conn)
        cur = conn.execute(
            """INSERT INTO invoices
                 (invoice_number, client_id, project, description,
                  amount_minor, currency, issue_date, due_date, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'UNPAID')""",
            (
                invoice_number,
                client_id,
                project,
                description,
                amount_minor,
                currency,
                issue,
                due,
            ),
        )
        row = conn.execute(
            INVOICE_SELECT + " WHERE i.id = ?", (cur.lastrowid,)
        ).fetchone()
        return {"status": "created", "invoice": invoice_to_dict(row)}


@tool
def get_invoice(
    invoice_number: str | None = None, invoice_id: int | None = None
) -> dict:
    """Look up one invoice by its number or its numeric id.

    Args:
        invoice_number: The document number, e.g. "FF-0008".
        invoice_id: The numeric id, if you have it from another tool.

    Returns:
        status "found" with the invoice including its outstanding balance and
        overdue state, or "not_found".
    """
    if not invoice_number and invoice_id is None:
        return {
            "status": "error",
            "error": "Provide either an invoice_number or an invoice_id.",
        }

    with get_db() as conn:
        if invoice_id is not None:
            row = conn.execute(
                INVOICE_SELECT + " WHERE i.id = ?", (invoice_id,)
            ).fetchone()
        else:
            row = conn.execute(
                INVOICE_SELECT + " WHERE UPPER(i.invoice_number) = ?",
                (invoice_number.strip().upper(),),
            ).fetchone()

    if not row:
        return {
            "status": "not_found",
            "invoice_number": invoice_number,
            "invoice_id": invoice_id,
        }
    return {"status": "found", "invoice": invoice_to_dict(row)}


@tool
def list_invoices(
    client_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict:
    """List invoices, most recent first, optionally filtered.

    Args:
        client_id: Restrict to one client, from find_client.
        status: One of UNPAID, PARTIALLY_PAID, PAID, CANCELLED.
        limit: Maximum number of invoices to return.

    Returns:
        status "ok" with a count and the list of invoices, each carrying its
        outstanding balance and overdue state.
    """
    limit = max(1, min(int(limit or 50), 200))
    where: list[str] = []
    params: list = []

    if client_id is not None:
        where.append("i.client_id = ?")
        params.append(client_id)

    if status:
        normalised = status.strip().upper()
        if normalised not in VALID_STATUSES:
            return {
                "status": "error",
                "error": (
                    f"Unknown status '{status}'. "
                    f"Use one of {list(VALID_STATUSES)}."
                ),
            }
        where.append("i.status = ?")
        params.append(normalised)

    sql = INVOICE_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY i.id DESC LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    invoices = [invoice_to_dict(r) for r in rows]
    return {
        "status": "ok",
        "count": len(invoices),
        "invoices": invoices,
        "total_outstanding_minor": sum(i["outstanding_minor"] for i in invoices),
    }


@tool
def generate_invoice_pdf(invoice_id: int) -> dict:
    """Generate (or regenerate) the PDF document for an invoice.

    Every figure on the document is read from the database, so run this again
    after a payment to refresh the balance shown on the page.

    Args:
        invoice_id: The numeric id of the invoice, from create_invoice or
            get_invoice.

    Returns:
        status "created" with the pdf_path, "not_found" if there is no such
        invoice, or "error" if the document could not be written. Do not tell
        the user a document exists unless this returned "created".
    """
    from app.pdf_generator import create_invoice_pdf

    return create_invoice_pdf(invoice_id)
