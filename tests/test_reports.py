"""Phase 4.1-4.2, 4.6-4.8: overdue, outstanding, client balance, financial summary.

Every figure here is derived at query time. There is no stored overdue flag,
monthly revenue, or running balance anywhere in this module.
"""

import pytest

from app.database import get_db
from app.dates import add_days, today_iso
from app.tools.clients import create_client
from app.tools.invoices import create_invoice
from app.tools.payments import record_payment
from app.tools.reports import (
    get_client_balance,
    get_financial_summary,
    get_outstanding_invoices,
    get_overdue_invoices,
)


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


PAST = add_days(today_iso(), -7)
FUTURE = add_days(today_iso(), 10)
TODAY = today_iso()


# --- get_overdue_invoices --------------------------------------------------


def test_unpaid_past_due_is_overdue():
    client = make_client()
    make_invoice(client, issue_date=add_days(PAST, -10), due_date=PAST)
    result = call(get_overdue_invoices)
    assert result["count"] == 1
    assert result["invoices"][0]["invoice_number"] == "FF-0001"


def test_partially_paid_past_due_is_overdue():
    client = make_client()
    invoice = make_invoice(client, issue_date=add_days(PAST, -10), due_date=PAST)
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=1_000_000)
    result = call(get_overdue_invoices)
    assert result["count"] == 1
    assert result["invoices"][0]["invoice_status"] == "PARTIALLY_PAID"


def test_fully_paid_past_due_is_not_overdue():
    client = make_client()
    invoice = make_invoice(client, issue_date=add_days(PAST, -10), due_date=PAST)
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=4_000_000)
    assert call(get_overdue_invoices)["count"] == 0


def test_future_due_date_is_not_overdue():
    client = make_client()
    make_invoice(client, due_date=FUTURE)
    assert call(get_overdue_invoices)["count"] == 0


def test_due_today_is_not_overdue():
    client = make_client()
    make_invoice(client, due_date=TODAY)
    assert call(get_overdue_invoices)["count"] == 0


def test_cancelled_invoice_is_not_overdue():
    client = make_client()
    invoice = make_invoice(client, issue_date=add_days(PAST, -10), due_date=PAST)
    cancel(invoice["invoice_id"])
    assert call(get_overdue_invoices)["count"] == 0


def test_invoice_with_no_due_date_is_never_overdue():
    client = make_client()
    make_invoice(client, issue_date=add_days(PAST, -10))
    assert call(get_overdue_invoices)["count"] == 0


def test_multiple_overdue_invoices_sorted_most_overdue_first():
    client = make_client()
    make_invoice(
        client,
        project="A",
        issue_date=add_days(PAST, -30),
        due_date=add_days(TODAY, -2),
    )
    make_invoice(
        client,
        project="B",
        issue_date=add_days(PAST, -30),
        due_date=add_days(TODAY, -10),
    )
    result = call(get_overdue_invoices)
    assert result["count"] == 2
    assert [i["project"] for i in result["invoices"]] == ["B", "A"]


def test_days_overdue_is_calculated_not_stored():
    client = make_client()
    make_invoice(
        client, issue_date=add_days(TODAY, -30), due_date=add_days(TODAY, -4)
    )
    result = call(get_overdue_invoices)
    assert result["invoices"][0]["days_overdue"] == 4


def test_overdue_total_is_broken_down_by_currency():
    client = make_client()
    make_invoice(
        client, amount_minor=4_000_000, currency="INR",
        issue_date=add_days(PAST, -10), due_date=PAST,
    )
    make_invoice(
        client, amount_minor=25_000, currency="USD",
        issue_date=add_days(PAST, -10), due_date=PAST,
    )
    totals = {t["currency"]: t["total_display"] for t in call(get_overdue_invoices)["overdue_total"]}
    assert totals == {"INR": "₹40,000.00", "USD": "$250.00"}


def test_get_overdue_invoices_filters_by_client():
    a = make_client("Rahul")
    b = make_client("Priya")
    make_invoice(a, issue_date=add_days(PAST, -10), due_date=PAST)
    make_invoice(b, issue_date=add_days(PAST, -10), due_date=PAST)
    assert call(get_overdue_invoices, client_id=a)["count"] == 1


# --- get_outstanding_invoices ----------------------------------------------


def test_outstanding_includes_both_overdue_and_not_yet_due():
    client = make_client()
    make_invoice(client, project="Overdue", issue_date=add_days(PAST, -10), due_date=PAST)
    make_invoice(client, project="Not due yet", due_date=FUTURE)
    result = call(get_outstanding_invoices)
    assert result["count"] == 2
    assert {i["project"] for i in result["invoices"]} == {"Overdue", "Not due yet"}


def test_outstanding_excludes_fully_paid():
    client = make_client()
    invoice = make_invoice(client)
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=4_000_000)
    assert call(get_outstanding_invoices)["count"] == 0


def test_outstanding_excludes_cancelled():
    client = make_client()
    invoice = make_invoice(client)
    cancel(invoice["invoice_id"])
    assert call(get_outstanding_invoices)["count"] == 0


def test_outstanding_sorted_by_soonest_due_date_first():
    client = make_client()
    make_invoice(client, project="Later", due_date=add_days(TODAY, 20))
    make_invoice(client, project="Sooner", due_date=add_days(TODAY, 5))
    make_invoice(client, project="No due date")
    result = call(get_outstanding_invoices)
    projects = [i["project"] for i in result["invoices"]]
    assert projects == ["Sooner", "Later", "No due date"]


def test_outstanding_total_matches_sum_of_balances():
    client = make_client()
    make_invoice(client, amount_minor=4_000_000)
    invoice = make_invoice(client, amount_minor=2_000_000)
    call(record_payment, invoice_id=invoice["invoice_id"], amount_minor=500_000)
    result = call(get_outstanding_invoices)
    assert result["outstanding_total"][0]["total_minor"] == 5_500_000


# --- get_client_balance -----------------------------------------------------


def test_client_balance_reports_not_found():
    assert call(get_client_balance, client_id=9999)["status"] == "not_found"


def test_client_balance_totals():
    client = make_client()
    a = make_invoice(client, amount_minor=4_000_000)
    make_invoice(client, amount_minor=2_000_000)
    call(record_payment, invoice_id=a["invoice_id"], amount_minor=1_500_000)

    result = call(get_client_balance, client_id=client)
    assert result["status"] == "ok"
    assert result["client_name"] == "Rahul Sharma"
    assert result["invoice_count"] == 2
    assert result["invoiced_total"][0]["total_minor"] == 6_000_000
    assert result["paid_total"][0]["total_minor"] == 1_500_000
    assert result["outstanding_total"][0]["total_minor"] == 4_500_000


def test_client_balance_counts_by_status():
    client = make_client()
    paid = make_invoice(client, project="Paid")
    call(record_payment, invoice_id=paid["invoice_id"], amount_minor=4_000_000)
    partial = make_invoice(client, project="Partial")
    call(record_payment, invoice_id=partial["invoice_id"], amount_minor=1_000_000)
    make_invoice(client, project="Unpaid")

    counts = call(get_client_balance, client_id=client)["invoice_counts_by_status"]
    assert counts == {"UNPAID": 1, "PARTIALLY_PAID": 1, "PAID": 1}


def test_client_balance_includes_overdue_subset():
    client = make_client()
    make_invoice(client, issue_date=add_days(PAST, -10), due_date=PAST)
    make_invoice(client, due_date=FUTURE)

    result = call(get_client_balance, client_id=client)
    assert result["overdue_total"][0]["total_minor"] == 4_000_000
    assert result["outstanding_total"][0]["total_minor"] == 8_000_000


def test_client_balance_ignores_other_clients():
    a = make_client("Rahul")
    b = make_client("Priya")
    make_invoice(a, amount_minor=4_000_000)
    make_invoice(b, amount_minor=9_000_000)
    assert call(get_client_balance, client_id=a)["invoiced_total"][0]["total_minor"] == 4_000_000


def test_client_with_no_invoices_has_empty_totals():
    client = make_client()
    result = call(get_client_balance, client_id=client)
    assert result["invoice_count"] == 0
    assert result["invoiced_total"] == []
    assert result["outstanding_total"] == []


# --- get_financial_summary --------------------------------------------------


def test_summary_defaults_to_the_current_month():
    from app.dates import current_month_bounds

    start, end = current_month_bounds()
    result = call(get_financial_summary)
    assert result["period_start"] == start
    assert result["period_end"] == end


def test_summary_received_scoped_to_period():
    client = make_client()
    invoice = make_invoice(client, amount_minor=4_000_000)
    call(
        record_payment,
        invoice_id=invoice["invoice_id"],
        amount_minor=1_500_000,
        payment_date="2026-06-15",
    )
    call(
        record_payment,
        invoice_id=invoice["invoice_id"],
        amount_minor=1_000_000,
        payment_date="2026-07-01",
    )

    june = call(get_financial_summary, start_date="2026-06-01", end_date="2026-06-30")
    assert june["received_total"][0]["total_minor"] == 1_500_000

    july = call(get_financial_summary, start_date="2026-07-01", end_date="2026-07-31")
    assert july["received_total"][0]["total_minor"] == 1_000_000


def test_summary_outstanding_is_not_period_scoped():
    """An invoice issued long before the period is still counted as owed today."""
    client = make_client()
    make_invoice(client, issue_date="2020-01-01", amount_minor=4_000_000)

    result = call(get_financial_summary, start_date="2026-01-01", end_date="2026-01-31")
    assert result["outstanding_total"][0]["total_minor"] == 4_000_000
    assert result["invoices_issued_in_period"] == 0


def test_summary_overdue_is_not_period_scoped():
    client = make_client()
    make_invoice(client, issue_date=add_days(PAST, -30), due_date=PAST)

    result = call(get_financial_summary, start_date="2020-01-01", end_date="2020-01-31")
    assert result["overdue_total"][0]["total_minor"] == 4_000_000


def test_summary_counts_invoices_issued_in_period_by_status():
    client = make_client()
    a = make_invoice(client, project="A", issue_date="2026-06-10")
    call(record_payment, invoice_id=a["invoice_id"], amount_minor=4_000_000, payment_date="2026-06-11")
    make_invoice(client, project="B", issue_date="2026-06-15")
    make_invoice(client, project="C", issue_date="2026-07-01")  # outside period

    result = call(get_financial_summary, start_date="2026-06-01", end_date="2026-06-30")
    assert result["invoices_issued_in_period"] == 2
    assert result["invoice_counts_in_period"] == {"UNPAID": 1, "PARTIALLY_PAID": 0, "PAID": 1}


def test_summary_rejects_end_before_start():
    result = call(get_financial_summary, start_date="2026-09-10", end_date="2026-09-01")
    assert result["status"] == "error"


def test_summary_rejects_invalid_dates():
    assert call(get_financial_summary, start_date="not-a-date")["status"] == "error"


def test_summary_by_currency_does_not_mix_amounts():
    client = make_client()
    inr = make_invoice(client, amount_minor=4_000_000, currency="INR")
    usd = make_invoice(client, amount_minor=25_000, currency="USD")
    call(record_payment, invoice_id=inr["invoice_id"], amount_minor=4_000_000, payment_date=TODAY)
    call(record_payment, invoice_id=usd["invoice_id"], amount_minor=25_000, payment_date=TODAY)

    result = call(get_financial_summary)
    by_currency = {r["currency"]: r["total_minor"] for r in result["received_total"]}
    assert by_currency == {"INR": 4_000_000, "USD": 25_000}
