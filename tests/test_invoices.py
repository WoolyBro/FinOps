"""Phase 2: invoice creation, numbering, retrieval and validation."""

import pytest

from app.dates import add_days, today_iso
from app.tools.clients import create_client
from app.tools.invoices import (
    create_invoice,
    get_invoice,
    get_next_invoice_number,
    list_invoices,
)


def call(t, **kw):
    """Invoke a Strands @tool directly, without going through an agent."""
    return t(**kw)


@pytest.fixture
def client_id():
    return call(create_client, name="Rahul Sharma")["client"]["client_id"]


def make_invoice(client_id, **overrides):
    kwargs = dict(
        client_id=client_id,
        project="Website development",
        amount_minor=4_000_000,
    )
    kwargs.update(overrides)
    return call(create_invoice, **kwargs)


# --- creation -------------------------------------------------------------


def test_creates_invoice(client_id):
    result = make_invoice(client_id)
    assert result["status"] == "created"
    invoice = result["invoice"]
    assert invoice["client_id"] == client_id
    assert invoice["client_name"] == "Rahul Sharma"
    assert invoice["project"] == "Website development"


def test_first_invoice_number_is_ff_0001(client_id):
    assert make_invoice(client_id)["invoice"]["invoice_number"] == "FF-0001"


def test_invoice_number_increments(client_id):
    numbers = [
        make_invoice(client_id, project=f"Project {n}")["invoice"]["invoice_number"]
        for n in range(3)
    ]
    assert numbers == ["FF-0001", "FF-0002", "FF-0003"]


def test_next_invoice_number_previews_without_consuming(client_id):
    assert call(get_next_invoice_number)["next_invoice_number"] == "FF-0001"
    # Previewing twice must not burn a number.
    assert call(get_next_invoice_number)["next_invoice_number"] == "FF-0001"
    assert make_invoice(client_id)["invoice"]["invoice_number"] == "FF-0001"
    assert call(get_next_invoice_number)["next_invoice_number"] == "FF-0002"


def test_amount_is_stored_in_minor_units(client_id):
    invoice = make_invoice(client_id, amount_minor=4_000_000)["invoice"]
    assert invoice["amount_minor"] == 4_000_000
    assert invoice["amount_display"] == "₹40,000.00"


def test_new_invoice_starts_unpaid_with_full_balance(client_id):
    invoice = make_invoice(client_id)["invoice"]
    assert invoice["invoice_status"] == "UNPAID"
    assert invoice["amount_paid_minor"] == 0
    assert invoice["outstanding_minor"] == 4_000_000


def test_issue_date_defaults_to_today(client_id):
    assert make_invoice(client_id)["invoice"]["issue_date"] == today_iso()


def test_due_date_is_optional_and_not_invented(client_id):
    assert make_invoice(client_id)["invoice"]["due_date"] is None


def test_currency_is_normalised(client_id):
    invoice = make_invoice(client_id, currency="usd", amount_minor=25_000)["invoice"]
    assert invoice["currency"] == "USD"
    assert invoice["amount_display"] == "$250.00"


# --- validation -----------------------------------------------------------


def test_rejects_nonexistent_client():
    result = make_invoice(9999)
    assert result["status"] == "not_found"
    assert "invoice" not in result


def test_nonexistent_client_creates_nothing():
    make_invoice(9999)
    assert call(list_invoices)["count"] == 0
    # The failed attempt must not have consumed an invoice number.
    assert call(get_next_invoice_number)["next_invoice_number"] == "FF-0001"


@pytest.mark.parametrize("amount", [0, -1, -4_000_000, 40.5, True, "not a number"])
def test_rejects_invalid_amount(client_id, amount):
    assert make_invoice(client_id, amount_minor=amount)["status"] == "error"


def test_rejects_implausibly_large_amount(client_id):
    assert make_invoice(client_id, amount_minor=10**15)["status"] == "error"


@pytest.mark.parametrize("bad_date", ["15-09-2026", "September 15", "2026-13-01"])
def test_rejects_invalid_due_date(client_id, bad_date):
    assert make_invoice(client_id, due_date=bad_date)["status"] == "error"


def test_empty_due_date_means_absent_not_invalid(client_id):
    result = make_invoice(client_id, due_date="")
    assert result["status"] == "created"
    assert result["invoice"]["due_date"] is None


def test_rejects_due_date_before_issue_date(client_id):
    result = make_invoice(client_id, issue_date="2026-09-05", due_date="2026-09-01")
    assert result["status"] == "error"
    assert "before the issue date" in result["error"]


def test_rejects_empty_project(client_id):
    assert make_invoice(client_id, project="   ")["status"] == "error"


def test_rejects_invalid_currency(client_id):
    assert make_invoice(client_id, currency="rupees")["status"] == "error"


# --- duplicate safety -----------------------------------------------------


def test_identical_invoice_is_flagged_not_silently_duplicated(client_id):
    first = make_invoice(client_id)
    second = make_invoice(client_id)
    assert second["status"] == "duplicate_suspected"
    assert (
        second["existing_invoice"]["invoice_number"]
        == first["invoice"]["invoice_number"]
    )
    assert call(list_invoices)["count"] == 1


def test_duplicate_can_be_created_once_confirmed(client_id):
    make_invoice(client_id)
    second = make_invoice(client_id, allow_duplicate=True)
    assert second["status"] == "created"
    assert second["invoice"]["invoice_number"] == "FF-0002"
    assert call(list_invoices)["count"] == 2


def test_different_amount_is_not_a_duplicate(client_id):
    make_invoice(client_id)
    assert make_invoice(client_id, amount_minor=2_500_000)["status"] == "created"


# --- retrieval ------------------------------------------------------------


def test_get_invoice_by_number(client_id):
    make_invoice(client_id)
    result = call(get_invoice, invoice_number="FF-0001")
    assert result["status"] == "found"
    assert result["invoice"]["amount_minor"] == 4_000_000


def test_get_invoice_by_number_is_case_insensitive(client_id):
    make_invoice(client_id)
    assert call(get_invoice, invoice_number="ff-0001")["status"] == "found"


def test_get_invoice_by_id(client_id):
    invoice_id = make_invoice(client_id)["invoice"]["invoice_id"]
    assert call(get_invoice, invoice_id=invoice_id)["status"] == "found"


def test_get_missing_invoice_reports_not_found():
    result = call(get_invoice, invoice_number="FF-9999")
    assert result["status"] == "not_found"
    assert "invoice" not in result


def test_get_invoice_requires_an_identifier():
    assert call(get_invoice)["status"] == "error"


def test_list_invoices(client_id):
    make_invoice(client_id, project="Website")
    make_invoice(client_id, project="Logo", amount_minor=1_000_000)
    result = call(list_invoices)
    assert result["count"] == 2
    assert result["total_outstanding_minor"] == 5_000_000
    # Most recent first.
    assert result["invoices"][0]["project"] == "Logo"


def test_list_invoices_filters_by_client(client_id):
    other = call(create_client, name="Priya")["client"]["client_id"]
    make_invoice(client_id)
    make_invoice(other, project="Brand design")
    assert call(list_invoices, client_id=other)["count"] == 1


def test_list_invoices_rejects_unknown_status():
    assert call(list_invoices, status="OVERDUE")["status"] == "error"


# --- derived overdue state ------------------------------------------------


def test_overdue_is_derived_from_due_date(client_id):
    past = add_days(today_iso(), -7)
    invoice = make_invoice(
        client_id, issue_date=add_days(today_iso(), -30), due_date=past
    )["invoice"]
    assert invoice["is_overdue"] is True
    assert invoice["days_overdue"] == 7
    # Overdue is a derived read, never a stored status.
    assert invoice["invoice_status"] == "UNPAID"


def test_future_due_date_is_not_overdue(client_id):
    invoice = make_invoice(client_id, due_date=add_days(today_iso(), 10))["invoice"]
    assert invoice["is_overdue"] is False
    assert invoice["days_overdue"] == 0
