"""Row -> plain-dict converters.

Tool return values are what the model actually reads, so they are kept flat,
JSON-safe and free of database internals the agent has no business reasoning about.
"""

from __future__ import annotations

import sqlite3

# Every invoice read goes through this so `amount_paid_minor` is always present
# and always comes from the payment ledger rather than a stored column.
INVOICE_SELECT = """
SELECT i.*,
       c.name AS client_name,
       c.email AS client_email,
       c.phone AS client_phone,
       c.address AS client_address,
       COALESCE((SELECT SUM(p.amount_minor)
                   FROM payments p
                  WHERE p.invoice_id = i.id), 0) AS amount_paid_minor
  FROM invoices i
  JOIN clients c ON c.id = i.client_id
"""


def client_to_dict(row: sqlite3.Row) -> dict:
    return {
        "client_id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "phone": row["phone"],
        "address": row["address"],
        "notes": row["notes"],
        "created_at": row["created_at"],
    }


def invoice_to_dict(row: sqlite3.Row, as_of: str | None = None) -> dict:
    """Flatten an invoice row, computing every derived figure here.

    `amount_paid_minor` must already be on the row (see INVOICE_SELECT). Paid,
    outstanding and overdue are all derived rather than stored, so the balance
    can never drift out of step with the payment ledger.
    """
    from app.dates import days_between, is_overdue, today_iso
    from app.money import format_money

    currency = row["currency"]
    amount = int(row["amount_minor"])
    paid = int(row["amount_paid_minor"] or 0)
    outstanding = amount - paid
    as_of = as_of or today_iso()
    overdue = is_overdue(row["due_date"], outstanding, as_of)

    return {
        "invoice_id": row["id"],
        "invoice_number": row["invoice_number"],
        "client_id": row["client_id"],
        "client_name": row["client_name"],
        "project": row["project"],
        "description": row["description"],
        "currency": currency,
        "amount_minor": amount,
        "amount_paid_minor": paid,
        "outstanding_minor": outstanding,
        "amount_display": format_money(amount, currency),
        "amount_paid_display": format_money(paid, currency),
        "outstanding_display": format_money(outstanding, currency),
        "issue_date": row["issue_date"],
        "due_date": row["due_date"],
        "invoice_status": row["status"],
        "is_overdue": overdue,
        "days_overdue": days_between(row["due_date"], as_of) if overdue else 0,
        "pdf_path": row["pdf_path"],
        "created_at": row["created_at"],
    }


# A payment carries its invoice and client with it, plus the running total paid
# up to and including this payment. That running total is what a receipt needs:
# the balance as it stood when this money arrived, not the balance today.
PAYMENT_SELECT = """
SELECT p.*,
       i.invoice_number,
       i.project,
       i.description AS invoice_description,
       i.currency,
       i.amount_minor AS invoice_amount_minor,
       i.status        AS invoice_status,
       i.issue_date    AS invoice_issue_date,
       i.due_date      AS invoice_due_date,
       i.client_id,
       c.name    AS client_name,
       c.email   AS client_email,
       c.phone   AS client_phone,
       c.address AS client_address,
       COALESCE((SELECT SUM(p2.amount_minor)
                   FROM payments p2
                  WHERE p2.invoice_id = p.invoice_id
                    AND p2.id <= p.id), 0) AS paid_to_date_minor
  FROM payments p
  JOIN invoices i ON i.id = p.invoice_id
  JOIN clients  c ON c.id = i.client_id
"""


def payment_to_dict(row: sqlite3.Row) -> dict:
    """Flatten a payment row, with the balance as it stood at that payment."""
    from app.money import format_money

    currency = row["currency"]
    amount = int(row["amount_minor"])
    invoice_amount = int(row["invoice_amount_minor"])
    paid_to_date = int(row["paid_to_date_minor"] or 0)
    outstanding_after = invoice_amount - paid_to_date

    return {
        "payment_id": row["id"],
        "invoice_id": row["invoice_id"],
        "invoice_number": row["invoice_number"],
        "client_id": row["client_id"],
        "client_name": row["client_name"],
        "project": row["project"],
        "currency": currency,
        "amount_minor": amount,
        "amount_display": format_money(amount, currency),
        "payment_date": row["payment_date"],
        "method": row["method"],
        "reference": row["reference"],
        "receipt_number": row["receipt_number"],
        "receipt_path": row["receipt_path"],
        "invoice_amount_minor": invoice_amount,
        "invoice_amount_display": format_money(invoice_amount, currency),
        "paid_to_date_minor": paid_to_date,
        "paid_to_date_display": format_money(paid_to_date, currency),
        "outstanding_after_minor": outstanding_after,
        "outstanding_after_display": format_money(outstanding_after, currency),
        "invoice_status": row["invoice_status"],
        "created_at": row["created_at"],
    }


# A reminder carries the invoice and client it was written for, plus the
# balance at the moment it was prepared -- not a live view, the same way a
# receipt is not a live view. The wording does not change if the balance
# moves after the reminder was drafted; a new reminder is prepared instead.
REMINDER_SELECT = """
SELECT r.*,
       i.invoice_number,
       i.project,
       i.currency,
       i.amount_minor AS invoice_amount_minor,
       i.due_date      AS invoice_due_date,
       i.status        AS invoice_status,
       i.client_id,
       c.name  AS client_name,
       c.email AS client_email
  FROM reminders r
  JOIN invoices i ON i.id = r.invoice_id
  JOIN clients  c ON c.id = i.client_id
"""


def reminder_to_dict(row: sqlite3.Row) -> dict:
    """Flatten a reminder row for the agent and the tests."""
    return {
        "reminder_id": row["id"],
        "invoice_id": row["invoice_id"],
        "invoice_number": row["invoice_number"],
        "client_id": row["client_id"],
        "client_name": row["client_name"],
        "client_email": row["client_email"],
        "project": row["project"],
        "channel": row["channel"],
        "message": row["message"],
        "reminder_status": row["status"],
        "created_at": row["created_at"],
        "sent_at": row["sent_at"],
    }
