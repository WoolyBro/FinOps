"""Phase 4.3-4.5: payment reminders, drafted and never sent.

create_payment_reminder must never invent a number -- every figure in the
message is asserted against the invoice it was built from.
"""

import pytest

from app.database import get_db
from app.dates import add_days, today_iso
from app.tools.clients import create_client
from app.tools.invoices import create_invoice
from app.tools.payments import record_payment
from app.tools.reminders import approve_reminder, create_payment_reminder, list_reminders


def call(t, **kw):
    return t(**kw)


def make_client(name="Rahul Sharma"):
    return call(create_client, name=name)["client"]["client_id"]


def make_invoice(client_id, **overrides):
    kwargs = dict(project="Website development", amount_minor=4_000_000)
    kwargs.update(overrides)
    return call(create_invoice, client_id=client_id, **kwargs)["invoice"]


def cancel(invoice_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE invoices SET status = 'CANCELLED' WHERE id = ?", (invoice_id,)
        )


PAST = add_days(today_iso(), -4)


# --- drafting ---------------------------------------------------------------


def test_prepares_a_reminder_for_an_outstanding_invoice():
    client = make_client()
    invoice = make_invoice(client, due_date=PAST, issue_date=add_days(PAST, -20))
    result = call(create_payment_reminder, invoice_id=invoice["invoice_id"])

    assert result["status"] == "prepared"
    reminder = result["reminder"]
    assert reminder["reminder_status"] == "DRAFT"
    assert reminder["invoice_number"] == "FF-0001"
    assert reminder["client_name"] == "Rahul Sharma"


def test_message_contains_the_real_invoice_number_and_amount():
    client = make_client()
    invoice = make_invoice(
        client, amount_minor=15_000_000, due_date=PAST, issue_date=add_days(PAST, -20)
    )
    message = call(create_payment_reminder, invoice_id=invoice["invoice_id"])["reminder"]["message"]

    assert "FF-0001" in message
    assert "Rahul Sharma" in message
    assert "₹1,50,000.00" in message


def test_message_reports_days_overdue():
    client = make_client()
    invoice = make_invoice(
        client, due_date=add_days(today_iso(), -6), issue_date=add_days(PAST, -20)
    )
    message = call(create_payment_reminder, invoice_id=invoice["invoice_id"])["reminder"]["message"]
    assert "6 days overdue" in message


def test_message_uses_singular_day_when_exactly_one():
    client = make_client()
    invoice = make_invoice(
        client, due_date=add_days(today_iso(), -1), issue_date=add_days(PAST, -20)
    )
    message = call(create_payment_reminder, invoice_id=invoice["invoice_id"])["reminder"]["message"]
    assert "1 day overdue" in message
    assert "1 days overdue" not in message


def test_message_omits_overdue_language_when_not_yet_due():
    client = make_client()
    invoice = make_invoice(client, due_date=add_days(today_iso(), 10))
    message = call(create_payment_reminder, invoice_id=invoice["invoice_id"])["reminder"]["message"]
    assert "overdue" not in message


def test_message_mentions_the_due_date_when_present():
    client = make_client()
    invoice = make_invoice(client, due_date="2026-09-15")
    message = call(create_payment_reminder, invoice_id=invoice["invoice_id"])["reminder"]["message"]
    assert "September 15, 2026" in message


def test_message_omits_due_date_clause_when_absent():
    client = make_client()
    invoice = make_invoice(client, due_date=None)
    message = call(create_payment_reminder, invoice_id=invoice["invoice_id"])["reminder"]["message"]
    assert ", due" not in message


def test_reflects_partial_payment_in_the_outstanding_amount():
    client = make_client()
    invoice = make_invoice(client, amount_minor=4_000_000, due_date=PAST, issue_date=add_days(PAST, -20))
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000)

    message = call(create_payment_reminder, invoice_id=invoice["invoice_id"])["reminder"]["message"]
    assert "₹25,000.00" in message
    assert "₹40,000.00" not in message


# --- refusal ------------------------------------------------------------


def test_refuses_a_fully_paid_invoice():
    client = make_client()
    invoice = make_invoice(client)
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=4_000_000)

    result = call(create_payment_reminder, invoice_id=invoice["invoice_id"])
    assert result["status"] == "error"
    assert "fully paid" in result["error"]


def test_refuses_a_cancelled_invoice():
    client = make_client()
    invoice = make_invoice(client)
    cancel(invoice["invoice_id"])
    result = call(create_payment_reminder, invoice_id=invoice["invoice_id"])
    assert result["status"] == "error"
    assert "cancelled" in result["error"]


def test_reports_not_found_for_a_missing_invoice():
    result = call(create_payment_reminder, invoice_id=9999)
    assert result["status"] == "not_found"


# --- deduplication -----------------------------------------------------


def test_second_call_returns_the_existing_draft():
    client = make_client()
    invoice = make_invoice(client, due_date=PAST, issue_date=add_days(PAST, -20))
    first = call(create_payment_reminder, invoice_id=invoice["invoice_id"])
    second = call(create_payment_reminder, invoice_id=invoice["invoice_id"])

    assert second["status"] == "already_exists"
    assert second["reminder"]["reminder_id"] == first["reminder"]["reminder_id"]
    assert call(list_reminders, invoice_id=invoice["invoice_id"])["count"] == 1


def test_forcing_creates_a_second_reminder():
    client = make_client()
    invoice = make_invoice(client, due_date=PAST, issue_date=add_days(PAST, -20))
    call(create_payment_reminder, invoice_id=invoice["invoice_id"])
    second = call(create_payment_reminder, invoice_id=invoice["invoice_id"], force=True)

    assert second["status"] == "prepared"
    assert call(list_reminders, invoice_id=invoice["invoice_id"])["count"] == 2


def test_an_approved_reminder_still_blocks_a_new_draft():
    client = make_client()
    invoice = make_invoice(client, due_date=PAST, issue_date=add_days(PAST, -20))
    first = call(create_payment_reminder, invoice_id=invoice["invoice_id"])
    call(approve_reminder, reminder_id=first["reminder"]["reminder_id"])

    second = call(create_payment_reminder, invoice_id=invoice["invoice_id"])
    assert second["status"] == "already_exists"
    assert second["reminder"]["reminder_status"] == "APPROVED"


def test_a_cancelled_reminder_does_not_block_a_new_one():
    client = make_client()
    invoice = make_invoice(client, due_date=PAST, issue_date=add_days(PAST, -20))
    first = call(create_payment_reminder, invoice_id=invoice["invoice_id"])
    with get_db() as conn:
        conn.execute(
            "UPDATE reminders SET status = 'CANCELLED' WHERE id = ?",
            (first["reminder"]["reminder_id"],),
        )
    second = call(create_payment_reminder, invoice_id=invoice["invoice_id"])
    assert second["status"] == "prepared"


# --- approval ------------------------------------------------------------


def test_approve_moves_draft_to_approved():
    client = make_client()
    invoice = make_invoice(client, due_date=PAST, issue_date=add_days(PAST, -20))
    reminder = call(create_payment_reminder, invoice_id=invoice["invoice_id"])["reminder"]

    result = call(approve_reminder, reminder_id=reminder["reminder_id"])
    assert result["status"] == "approved"
    assert result["reminder"]["reminder_status"] == "APPROVED"


def test_approving_twice_is_idempotent():
    client = make_client()
    invoice = make_invoice(client, due_date=PAST, issue_date=add_days(PAST, -20))
    reminder = call(create_payment_reminder, invoice_id=invoice["invoice_id"])["reminder"]
    call(approve_reminder, reminder_id=reminder["reminder_id"])
    result = call(approve_reminder, reminder_id=reminder["reminder_id"])
    assert result["status"] == "approved"


def test_cannot_approve_a_cancelled_reminder():
    client = make_client()
    invoice = make_invoice(client, due_date=PAST, issue_date=add_days(PAST, -20))
    reminder = call(create_payment_reminder, invoice_id=invoice["invoice_id"])["reminder"]
    with get_db() as conn:
        conn.execute(
            "UPDATE reminders SET status = 'CANCELLED' WHERE id = ?",
            (reminder["reminder_id"],),
        )
    result = call(approve_reminder, reminder_id=reminder["reminder_id"])
    assert result["status"] == "error"


def test_approve_reports_not_found():
    assert call(approve_reminder, reminder_id=9999)["status"] == "not_found"


# --- listing --------------------------------------------------------------


def test_list_reminders_most_recent_first():
    client = make_client()
    a = make_invoice(client, project="A", due_date=PAST, issue_date=add_days(PAST, -20))
    b = make_invoice(client, project="B", due_date=PAST, issue_date=add_days(PAST, -20))
    call(create_payment_reminder, invoice_id=a["invoice_id"])
    call(create_payment_reminder, invoice_id=b["invoice_id"])

    result = call(list_reminders)
    assert result["count"] == 2
    assert result["reminders"][0]["invoice_number"] == "FF-0002"


def test_list_reminders_filters_by_status():
    client = make_client()
    invoice = make_invoice(client, due_date=PAST, issue_date=add_days(PAST, -20))
    reminder = call(create_payment_reminder, invoice_id=invoice["invoice_id"])["reminder"]
    call(approve_reminder, reminder_id=reminder["reminder_id"])

    assert call(list_reminders, status="APPROVED")["count"] == 1
    assert call(list_reminders, status="DRAFT")["count"] == 0


def test_list_reminders_filters_by_client():
    a = make_client("Rahul")
    b = make_client("Priya")
    invoice_a = make_invoice(a, due_date=PAST, issue_date=add_days(PAST, -20))
    invoice_b = make_invoice(b, due_date=PAST, issue_date=add_days(PAST, -20))
    call(create_payment_reminder, invoice_id=invoice_a["invoice_id"])
    call(create_payment_reminder, invoice_id=invoice_b["invoice_id"])

    assert call(list_reminders, client_id=a)["count"] == 1


def test_list_reminders_rejects_unknown_status():
    assert call(list_reminders, status="SNOOZED")["status"] == "error"
