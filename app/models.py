"""Row -> plain-dict converters.

Tool return values are what the model actually reads, so they are kept flat,
JSON-safe and free of database internals the agent has no business reasoning about.
"""

from __future__ import annotations

import sqlite3


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
