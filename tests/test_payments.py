"""Phase 3: recording money, deriving balances, and moving invoice status.

The payments table is the source of truth. Every assertion about a balance here
reads it back from the ledger rather than from whatever the caller passed in.
"""

import pytest

from app.database import get_db
from app.tools.clients import create_client
from app.tools.invoices import create_invoice, get_invoice
from app.tools.payments import (
    get_payment,
    list_payments,
    paid_total,
    record_payment,
)


def call(t, **kw):
    return t(**kw)


@pytest.fixture
def invoice():
    client = call(create_client, name="Rahul Sharma")["client"]
    return call(
        create_invoice,
        client_id=client["client_id"],
        project="Website development",
        amount_minor=4_000_000,
        due_date="2026-09-15",
    )["invoice"]


def status_of(invoice_number="FF-0001"):
    return call(get_invoice, invoice_number=invoice_number)["invoice"]


def cancel(invoice_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE invoices SET status = 'CANCELLED' WHERE id = ?", (invoice_id,)
        )


# --- recording ------------------------------------------------------------


def test_records_a_payment(invoice):
    result = call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000)
    assert result["status"] == "recorded"
    payment = result["payment"]
    assert payment["amount_minor"] == 1_500_000
    assert payment["amount_display"] == "₹15,000.00"
    assert payment["invoice_number"] == "FF-0001"
    assert payment["client_name"] == "Rahul Sharma"


def test_payment_date_defaults_to_today(invoice):
    from app.dates import today_iso

    result = call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=100)
    assert result["payment"]["payment_date"] == today_iso()


def test_method_and_reference_are_stored(invoice):
    result = call(
        record_payment,
        invoice_id=invoice["invoice_id"],
        amount_minor=1_500_000,
        method="UPI",
        reference="TXN-99881",
    )
    assert result["payment"]["method"] == "UPI"
    assert result["payment"]["reference"] == "TXN-99881"


# --- balance from the ledger ---------------------------------------------


def test_balance_is_derived_from_the_ledger(invoice):
    result = call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000)
    assert result["invoice"]["amount_paid_minor"] == 1_500_000
    assert result["invoice"]["outstanding_minor"] == 2_500_000
    assert result["invoice"]["outstanding_display"] == "₹25,000.00"


def test_multiple_payments_sum(invoice):
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000)
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_000_000)
    refreshed = status_of()
    assert refreshed["amount_paid_minor"] == 2_500_000
    assert refreshed["outstanding_minor"] == 1_500_000


def test_invoices_still_have_no_amount_paid_column():
    """The architectural rule, asserted rather than trusted."""
    with get_db() as conn:
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(invoices)").fetchall()
        }
    assert "amount_paid" not in columns
    assert "amount_paid_minor" not in columns
    assert "outstanding" not in columns


def test_paid_total_reads_the_ledger_directly(invoice):
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000)
    with get_db() as conn:
        assert paid_total(conn, invoice["invoice_id"]) == 1_500_000


def test_deleting_a_payment_would_lower_the_balance(invoice):
    """Nothing caches the total, so removing a row changes the answer."""
    result = call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000)
    with get_db() as conn:
        conn.execute("DELETE FROM payments WHERE id = ?", (result["payment"]["payment_id"],))
    assert status_of()["amount_paid_minor"] == 0


# --- status transitions ---------------------------------------------------


def test_unpaid_to_partially_paid(invoice):
    assert invoice["invoice_status"] == "UNPAID"
    result = call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000)
    assert result["invoice"]["invoice_status"] == "PARTIALLY_PAID"
    assert status_of()["invoice_status"] == "PARTIALLY_PAID"


def test_unpaid_to_paid_in_one_payment(invoice):
    result = call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=4_000_000)
    assert result["invoice"]["invoice_status"] == "PAID"
    assert result["invoice"]["outstanding_minor"] == 0


def test_partially_paid_to_paid(invoice):
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000)
    assert status_of()["invoice_status"] == "PARTIALLY_PAID"
    result = call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=2_500_000)
    assert result["invoice"]["invoice_status"] == "PAID"
    assert result["invoice"]["outstanding_minor"] == 0


def test_a_paid_invoice_is_not_overdue_even_past_its_due_date():
    client = call(create_client, name="Studio X")["client"]
    inv = call(
        create_invoice,
        client_id=client["client_id"],
        project="Landing page",
        amount_minor=1_000_000,
        issue_date="2020-01-01",
        due_date="2020-02-01",
    )["invoice"]
    assert inv["is_overdue"] is True

    result = call(record_payment, invoice_id=inv["invoice_id"], amount_minor=1_000_000)
    assert result["invoice"]["invoice_status"] == "PAID"
    assert result["invoice"]["is_overdue"] is False


# --- validation -----------------------------------------------------------


def test_rejects_payment_larger_than_outstanding(invoice):
    result = call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=5_000_000)
    assert result["status"] == "error"
    assert "more than the" in result["error"]
    assert result["outstanding_display"] == "₹40,000.00"
    assert call(list_payments)["count"] == 0


def test_rejects_payment_that_would_overshoot_a_partial_balance(invoice):
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000)
    result = call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=3_000_000)
    assert result["status"] == "error"
    assert result["outstanding_minor"] == 2_500_000
    assert status_of()["amount_paid_minor"] == 1_500_000


def test_exact_outstanding_amount_is_accepted(invoice):
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000)
    result = call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=2_500_000)
    assert result["status"] == "recorded"


@pytest.mark.parametrize("amount", [0, -1, -1_500_000, 40.5, True, "not a number"])
def test_rejects_invalid_amounts(invoice, amount):
    result = call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=amount)
    assert result["status"] == "error"
    assert call(list_payments)["count"] == 0


def test_rejects_nonexistent_invoice():
    result = call(record_payment, invoice_id=9999, amount_minor=1_500_000)
    assert result["status"] == "not_found"
    assert "payment" not in result


def test_rejects_payment_on_a_fully_paid_invoice(invoice):
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=4_000_000)
    result = call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=100)
    assert result["status"] == "error"
    assert "already paid in full" in result["error"]
    assert call(list_payments)["count"] == 1


def test_rejects_payment_on_a_cancelled_invoice(invoice):
    cancel(invoice["invoice_id"])
    result = call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000)
    assert result["status"] == "error"
    assert "CANCELLED" in result["error"]
    assert call(list_payments)["count"] == 0


def test_rejects_invalid_payment_date(invoice):
    result = call(
        record_payment,
        invoice_id=invoice["invoice_id"],
        amount_minor=1_500_000,
        payment_date="15-09-2026",
    )
    assert result["status"] == "error"


def test_cancelled_invoice_status_is_not_overwritten_by_recalculation(invoice):
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000)
    cancel(invoice["invoice_id"])
    from app.tools.payments import recalculate_status

    with get_db() as conn:
        assert recalculate_status(conn, invoice["invoice_id"]) == "CANCELLED"


# --- duplicate protection -------------------------------------------------


def test_identical_payment_is_flagged_not_silently_recorded(invoice):
    first = call(
        record_payment,
        invoice_id=invoice["invoice_id"],
        amount_minor=1_500_000,
        payment_date="2026-09-05",
    )
    second = call(
        record_payment,
        invoice_id=invoice["invoice_id"],
        amount_minor=1_500_000,
        payment_date="2026-09-05",
    )
    assert second["status"] == "duplicate_suspected"
    assert (
        second["existing_payment"]["payment_id"] == first["payment"]["payment_id"]
    )
    assert call(list_payments)["count"] == 1
    assert status_of()["amount_paid_minor"] == 1_500_000


def test_duplicate_can_be_recorded_once_confirmed(invoice):
    call(
        record_payment,
        invoice_id=invoice["invoice_id"],
        amount_minor=1_500_000,
        payment_date="2026-09-05",
    )
    second = call(
        record_payment,
        invoice_id=invoice["invoice_id"],
        amount_minor=1_500_000,
        payment_date="2026-09-05",
        allow_duplicate=True,
    )
    assert second["status"] == "recorded"
    assert status_of()["amount_paid_minor"] == 3_000_000


def test_same_amount_on_a_different_date_is_not_a_duplicate(invoice):
    call(
        record_payment,
        invoice_id=invoice["invoice_id"],
        amount_minor=1_500_000,
        payment_date="2026-09-05",
    )
    second = call(
        record_payment,
        invoice_id=invoice["invoice_id"],
        amount_minor=1_500_000,
        payment_date="2026-09-06",
    )
    assert second["status"] == "recorded"


def test_different_reference_is_not_a_duplicate(invoice):
    call(
        record_payment,
        invoice_id=invoice["invoice_id"],
        amount_minor=1_500_000,
        payment_date="2026-09-05",
        reference="TXN-1",
    )
    second = call(
        record_payment,
        invoice_id=invoice["invoice_id"],
        amount_minor=1_500_000,
        payment_date="2026-09-05",
        reference="TXN-2",
    )
    assert second["status"] == "recorded"


# --- retrieval ------------------------------------------------------------


def test_get_payment(invoice):
    recorded = call(
        record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000
    )["payment"]
    found = call(get_payment, payment_id=recorded["payment_id"])
    assert found["status"] == "found"
    assert found["payment"]["amount_minor"] == 1_500_000
    assert found["payment"]["outstanding_after_minor"] == 2_500_000


def test_get_missing_payment():
    result = call(get_payment, payment_id=4242)
    assert result["status"] == "not_found"
    assert "payment" not in result


def test_payment_history_is_most_recent_first(invoice):
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_000_000)
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=2_000_000)
    result = call(list_payments, invoice_id=invoice["invoice_id"])
    assert result["count"] == 2
    assert result["payments"][0]["amount_minor"] == 2_000_000
    assert result["total_received_minor"] == 3_000_000


def test_payment_history_filters_by_client(invoice):
    other = call(create_client, name="Priya")["client"]
    other_invoice = call(
        create_invoice,
        client_id=other["client_id"],
        project="Brand design",
        amount_minor=1_000_000,
    )["invoice"]
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_000_000)
    call(record_payment, invoice_id=other_invoice["invoice_id"], amount_minor=500_000)

    assert call(list_payments, client_id=other["client_id"])["count"] == 1
    assert call(list_payments)["count"] == 2


def test_running_balance_is_recorded_per_payment(invoice):
    """Each payment knows the balance as it stood when it arrived."""
    first = call(
        record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_500_000
    )["payment"]
    second = call(
        record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_000_000
    )["payment"]

    assert first["paid_to_date_minor"] == 1_500_000
    assert first["outstanding_after_minor"] == 2_500_000
    assert second["paid_to_date_minor"] == 2_500_000
    assert second["outstanding_after_minor"] == 1_500_000

    # And the first payment still reports its own historical balance.
    refetched = call(get_payment, payment_id=first["payment_id"])["payment"]
    assert refetched["outstanding_after_minor"] == 2_500_000
