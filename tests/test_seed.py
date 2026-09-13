"""The demo seed: realistic, internally consistent, and never destructive."""

from __future__ import annotations

import pytest

from app.seed import seed
from app.services import views
from app.tools.clients import create_client
from app.tools.invoices import get_invoice
from app.tools.reminders import list_reminders


def test_seed_builds_a_consistent_ledger():
    assert seed() == {"clients": 6, "invoices": 10}

    view = views.overview()
    assert view["client_count"] == 6
    # Three settled in full, seven still open.
    assert view["open_invoice_count"] == 7
    assert view["oldest_overdue"]["invoice_number"] == "FF-0004"
    assert view["oldest_overdue"]["days_overdue"] == 37


def test_the_demo_payment_is_left_for_the_agent_to_record():
    seed()
    invoice = get_invoice(invoice_number="FF-0005")["invoice"]
    assert invoice["client_name"] == "Rahul Sharma"
    assert invoice["invoice_status"] == "UNPAID"
    assert invoice["outstanding_display"] == "₹40,000.00"


def test_one_reminder_awaits_review_and_one_is_approved():
    seed()
    statuses = sorted(r["reminder_status"] for r in list_reminders()["reminders"])
    assert statuses == ["APPROVED", "DRAFT"]


def test_seed_refuses_a_database_that_has_data():
    create_client(name="Someone Real")
    with pytest.raises(SystemExit, match="Refusing to seed"):
        seed()
