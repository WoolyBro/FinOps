"""Payment reminder tools.

A reminder is drafted from real data and never sent by these tools -- there is
no email or messaging integration here. The lifecycle is DRAFT -> APPROVED,
with a human required at that step; SENT is reserved for whichever channel
integration eventually delivers it (phase 5+), and CANCELLED for a reminder
that should not go out at all.

The wording is built entirely from tool data: invoice number, client name,
outstanding balance and days overdue all come from the invoice, never from the
model's own phrasing of a number.
"""

from __future__ import annotations

from strands import tool

from app.config import BUSINESS_NAME
from app.database import get_db
from app.models import INVOICE_SELECT, REMINDER_SELECT, invoice_to_dict, reminder_to_dict

# Reminders in these states are still "live" -- preparing another one for the
# same invoice while one of these exists is very likely a duplicate.
ACTIVE_REMINDER_STATUSES = ("DRAFT", "APPROVED")


def _compose_message(invoice: dict) -> str:
    """Build the reminder text from the invoice's own figures."""
    due_clause = ""
    if invoice.get("due_date"):
        from app.pdf_generator import format_long_date

        due_clause = f", due {format_long_date(invoice['due_date'])},"

    overdue_clause = ""
    if invoice["is_overdue"]:
        days = invoice["days_overdue"]
        plural = "day" if days == 1 else "days"
        overdue_clause = f" This invoice is now {days} {plural} overdue."

    return (
        f"Hi {invoice['client_name']}, this is a reminder that invoice "
        f"{invoice['invoice_number']} for {invoice['project']}{due_clause} "
        f"has an outstanding balance of {invoice['outstanding_display']}."
        f"{overdue_clause} Please let us know if you have any questions. "
        f"Thank you, {BUSINESS_NAME}."
    )


@tool
def create_payment_reminder(invoice_id: int, force: bool = False) -> dict:
    """Prepare a payment reminder for an invoice with money still owed.

    This only drafts the reminder -- it does not send anything. Every figure in
    the message (invoice number, amount, due date, days overdue) is taken from
    the invoice; do not edit those figures into the message yourself. Show the
    draft to the user and get approve_reminder called before it goes anywhere.

    Args:
        invoice_id: The invoice to remind about, from get_overdue_invoices,
            get_outstanding_invoices, or get_invoice.
        force: Prepare a new reminder even though one is already drafted or
            approved for this invoice. Only set this after the user has asked
            for another one.

    Returns:
        status "prepared" with the new reminder, "already_exists" with the
        live reminder already on file, "not_found", or "error" (invoice fully
        paid or cancelled -- there is nothing to remind about).
    """
    with get_db() as conn:
        row = conn.execute(
            INVOICE_SELECT + " WHERE i.id = ?", (invoice_id,)
        ).fetchone()
        if not row:
            return {"status": "not_found", "invoice_id": invoice_id}

        invoice = invoice_to_dict(row)

        if invoice["invoice_status"] == "CANCELLED":
            return {
                "status": "error",
                "invoice_number": invoice["invoice_number"],
                "error": f"Invoice {invoice['invoice_number']} is cancelled.",
            }
        if invoice["outstanding_minor"] <= 0:
            return {
                "status": "error",
                "invoice_number": invoice["invoice_number"],
                "error": (
                    f"Invoice {invoice['invoice_number']} is fully paid. "
                    "There is nothing to remind the client about."
                ),
            }

        if not force:
            placeholders = ",".join("?" * len(ACTIVE_REMINDER_STATUSES))
            existing = conn.execute(
                REMINDER_SELECT
                + f""" WHERE r.invoice_id = ? AND r.status IN ({placeholders})
                       ORDER BY r.id DESC LIMIT 1""",
                (invoice_id, *ACTIVE_REMINDER_STATUSES),
            ).fetchone()
            if existing:
                return {
                    "status": "already_exists",
                    "reminder": reminder_to_dict(existing),
                    "hint": (
                        "A reminder for this invoice is already drafted or "
                        "approved. Ask the user before preparing another one, "
                        "then retry with force=true."
                    ),
                }

        message = _compose_message(invoice)
        cur = conn.execute(
            "INSERT INTO reminders (invoice_id, message) VALUES (?, ?)",
            (invoice_id, message),
        )
        reminder = conn.execute(
            REMINDER_SELECT + " WHERE r.id = ?", (cur.lastrowid,)
        ).fetchone()

    return {"status": "prepared", "reminder": reminder_to_dict(reminder)}


@tool
def approve_reminder(reminder_id: int) -> dict:
    """Approve a drafted reminder for sending.

    This still does not send anything -- there is no delivery channel wired up
    yet. It records that a human reviewed and accepted the draft, which is the
    gate a reminder must pass before any future send step is allowed to use it.

    Args:
        reminder_id: The reminder's id, from create_payment_reminder or
            list_reminders.

    Returns:
        status "approved" with the reminder, "not_found", or "error" if it is
        not in a state that can be approved (already sent or cancelled).
    """
    with get_db() as conn:
        row = conn.execute(
            REMINDER_SELECT + " WHERE r.id = ?", (reminder_id,)
        ).fetchone()
        if not row:
            return {"status": "not_found", "reminder_id": reminder_id}

        if row["status"] == "APPROVED":
            return {"status": "approved", "reminder": reminder_to_dict(row)}
        if row["status"] != "DRAFT":
            return {
                "status": "error",
                "reminder_id": reminder_id,
                "error": f"Reminder is {row['status']} and cannot be approved.",
            }

        conn.execute(
            "UPDATE reminders SET status = 'APPROVED' WHERE id = ?", (reminder_id,)
        )
        updated = conn.execute(
            REMINDER_SELECT + " WHERE r.id = ?", (reminder_id,)
        ).fetchone()

    return {"status": "approved", "reminder": reminder_to_dict(updated)}


@tool
def cancel_reminder(reminder_id: int) -> dict:
    """Withdraw a reminder so it does not go out.

    The reminder is kept, marked CANCELLED, rather than deleted: what was
    drafted about a client's money stays on record. Once cancelled, a new
    reminder can be prepared for the same invoice without force.

    Args:
        reminder_id: The reminder's id, from create_payment_reminder or
            list_reminders.

    Returns:
        status "cancelled" with the reminder, "not_found", or "error" if it
        has already been sent.
    """
    with get_db() as conn:
        row = conn.execute(
            REMINDER_SELECT + " WHERE r.id = ?", (reminder_id,)
        ).fetchone()
        if not row:
            return {"status": "not_found", "reminder_id": reminder_id}

        if row["status"] == "CANCELLED":
            return {"status": "cancelled", "reminder": reminder_to_dict(row)}
        if row["status"] == "SENT":
            return {
                "status": "error",
                "reminder_id": reminder_id,
                "error": "Reminder has already been sent and cannot be cancelled.",
            }

        conn.execute(
            "UPDATE reminders SET status = 'CANCELLED' WHERE id = ?", (reminder_id,)
        )
        updated = conn.execute(
            REMINDER_SELECT + " WHERE r.id = ?", (reminder_id,)
        ).fetchone()

    return {"status": "cancelled", "reminder": reminder_to_dict(updated)}


@tool
def list_reminders(
    invoice_id: int | None = None,
    client_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict:
    """List prepared reminders, most recent first.

    Args:
        invoice_id: Restrict to one invoice.
        client_id: Restrict to one client, across all their invoices.
        status: One of DRAFT, APPROVED, SENT, CANCELLED.
        limit: Maximum number of reminders to return.

    Returns:
        status "ok" with a count and the reminders.
    """
    limit = max(1, min(int(limit or 50), 200))
    where: list[str] = []
    params: list = []

    if invoice_id is not None:
        where.append("r.invoice_id = ?")
        params.append(invoice_id)
    if client_id is not None:
        where.append("i.client_id = ?")
        params.append(client_id)
    if status:
        normalised = status.strip().upper()
        valid = ("DRAFT", "APPROVED", "SENT", "CANCELLED")
        if normalised not in valid:
            return {
                "status": "error",
                "error": f"Unknown status '{status}'. Use one of {list(valid)}.",
            }
        where.append("r.status = ?")
        params.append(normalised)

    sql = REMINDER_SELECT
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY r.id DESC LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    reminders = [reminder_to_dict(r) for r in rows]
    return {"status": "ok", "count": len(reminders), "reminders": reminders}
