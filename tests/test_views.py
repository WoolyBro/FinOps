"""Dashboard views: every number a screen shows is derived on the server.

The browser used to add these up itself -- and the first version of the Reports
screen showed an invoice partition summing to 15 against 12 invoices. These
tests pin the properties that make a figure trustworthy: partitions that add
up, totals that do not depend on a page size, and cards that come from what a
tool returned rather than what the model said.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.database import get_db
from app.dates import add_days, current_month_bounds, today_iso
from app.services import views
from app.services.agent_service import result_card
from app.tools.clients import create_client
from app.tools.invoices import create_invoice
from app.tools.payments import record_payment
from app.tools.reminders import (
    approve_reminder,
    cancel_reminder,
    create_payment_reminder,
)
from app.tracing import ToolCall

TODAY = today_iso()
MONTH_START, MONTH_END = current_month_bounds()
LAST_MONTH = (date.fromisoformat(MONTH_START) - timedelta(days=1)).isoformat()


def make_client(name="Rahul Sharma"):
    return create_client(name=name)["client"]["client_id"]


def make_invoice(client_id, amount=4_000_000, **overrides):
    kwargs = dict(project="Website development", amount_minor=amount, allow_duplicate=True)
    kwargs.update(overrides)
    return create_invoice(client_id=client_id, **kwargs)["invoice"]


def pay(invoice_id, amount, on=TODAY):
    return record_payment(
        invoice_id=invoice_id, amount_minor=amount, payment_date=on, allow_duplicate=True
    )


def cancel_invoice(invoice_id):
    with get_db() as conn:
        conn.execute("UPDATE invoices SET status = 'CANCELLED' WHERE id = ?", (invoice_id,))


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pdf_generator.INVOICES_DIR", tmp_path / "invoices")
    monkeypatch.setattr("app.pdf_generator.RECEIPTS_DIR", tmp_path / "receipts")
    with TestClient(create_app()) as client:
        yield client


# --- cancel_reminder --------------------------------------------------------


def _drafted_reminder():
    client = make_client()
    invoice = make_invoice(client, issue_date=add_days(TODAY, -40), due_date=add_days(TODAY, -10))
    return invoice, create_payment_reminder(invoice_id=invoice["invoice_id"])["reminder"]


def test_a_draft_can_be_cancelled_and_stays_on_record():
    _, reminder = _drafted_reminder()
    result = cancel_reminder(reminder_id=reminder["reminder_id"])
    assert result["status"] == "cancelled"
    assert result["reminder"]["reminder_status"] == "CANCELLED"
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0] == 1


def test_an_approved_reminder_can_be_cancelled():
    _, reminder = _drafted_reminder()
    approve_reminder(reminder_id=reminder["reminder_id"])
    assert cancel_reminder(reminder_id=reminder["reminder_id"])["status"] == "cancelled"


def test_cancelling_frees_the_invoice_for_a_new_reminder_without_force():
    invoice, reminder = _drafted_reminder()
    cancel_reminder(reminder_id=reminder["reminder_id"])
    again = create_payment_reminder(invoice_id=invoice["invoice_id"])
    assert again["status"] == "prepared"


def test_a_sent_reminder_cannot_be_cancelled():
    _, reminder = _drafted_reminder()
    with get_db() as conn:
        conn.execute("UPDATE reminders SET status = 'SENT' WHERE id = ?", (reminder["reminder_id"],))
    result = cancel_reminder(reminder_id=reminder["reminder_id"])
    assert result["status"] == "error"
    assert "already been sent" in result["error"]


def test_cancelling_twice_is_idempotent():
    _, reminder = _drafted_reminder()
    cancel_reminder(reminder_id=reminder["reminder_id"])
    assert cancel_reminder(reminder_id=reminder["reminder_id"])["status"] == "cancelled"


def test_a_payment_after_drafting_flags_the_reminder_as_out_of_date(api):
    invoice, reminder = _drafted_reminder()
    fresh = api.get("/api/reminders").json()["reminders"][0]
    assert fresh["balance_changed"] is False
    assert fresh["current_outstanding_display"] == "₹40,000.00"

    pay(invoice["invoice_id"], 1_000_000)
    stale = api.get("/api/reminders").json()["reminders"][0]
    assert stale["balance_changed"] is True
    assert stale["current_outstanding_display"] == "₹30,000.00"
    assert "₹40,000.00" in stale["message"]  # the snapshot itself is untouched


def test_a_withdrawn_reminder_is_never_flagged(api):
    invoice, reminder = _drafted_reminder()
    cancel_reminder(reminder_id=reminder["reminder_id"])
    pay(invoice["invoice_id"], 1_000_000)
    assert api.get("/api/reminders").json()["reminders"][0]["balance_changed"] is False


def test_cancel_endpoint(api):
    _, reminder = _drafted_reminder()
    response = api.post(f"/api/reminders/{reminder['reminder_id']}/cancel")
    assert response.status_code == 200
    assert response.json()["reminder"]["reminder_status"] == "CANCELLED"

    missing = api.post("/api/reminders/999/cancel")
    assert missing.status_code == 409
    assert missing.json()["error"] == "not_found"


# --- period summary: the partition must add up -------------------------------


def test_the_invoice_partition_adds_up_and_overdue_is_a_qualifier():
    client = make_client()
    paid = make_invoice(client, issue_date=MONTH_START)
    pay(paid["invoice_id"], 4_000_000, on=MONTH_START)
    make_invoice(client, issue_date=MONTH_START, due_date=MONTH_START)  # unpaid, maybe late
    doomed = make_invoice(client, issue_date=MONTH_START)
    cancel_invoice(doomed["invoice_id"])

    summary = views.period_summary(MONTH_START, MONTH_END)
    counts = summary["invoice_counts_in_period"]

    issued = summary["invoices_issued_in_period"]
    assert sum(counts.values()) == issued == 2
    assert summary["cancelled_in_period"] == 1
    # Overdue counts invoices already inside the partition, never extra ones.
    assert summary["overdue_in_period"] <= counts["UNPAID"] + counts["PARTIALLY_PAID"]


def test_invoiced_total_excludes_cancelled_and_payments_are_counted():
    client = make_client()
    kept = make_invoice(client, amount=4_000_000, issue_date=MONTH_START)
    doomed = make_invoice(client, amount=9_900_000, issue_date=MONTH_START)
    cancel_invoice(doomed["invoice_id"])
    pay(kept["invoice_id"], 1_000_000, on=MONTH_START)
    pay(kept["invoice_id"], 500_000, on=MONTH_START)

    summary = views.period_summary(MONTH_START, MONTH_END)
    assert summary["invoiced_total"] == [
        {"currency": "INR", "total_minor": 4_000_000, "total_display": "₹40,000.00"}
    ]
    assert summary["payments_in_period"] == 2


def test_oldest_overdue_names_the_worst_invoice():
    rahul = make_client("Rahul Sharma")
    priya = make_client("Priya Deshmukh")
    make_invoice(rahul, issue_date=add_days(TODAY, -30), due_date=add_days(TODAY, -5))
    worst = make_invoice(priya, issue_date=add_days(TODAY, -60), due_date=add_days(TODAY, -37))

    oldest = views.period_summary()["oldest_overdue"]
    assert oldest["invoice_number"] == worst["invoice_number"]
    assert oldest["client_name"] == "Priya Deshmukh"
    assert oldest["days_overdue"] == 37


def test_summary_endpoint_carries_the_new_fields(api):
    body = api.get("/api/reports/summary").json()
    for key in ("invoiced_total", "payments_in_period", "cancelled_in_period",
                "overdue_in_period", "open_invoice_count", "oldest_overdue"):
        assert key in body


# --- monthly series -----------------------------------------------------------


@pytest.mark.parametrize(
    "peak,scale",
    [
        (14_725_000, 15_000_000),   # ₹1,47,250 -> ₹1,50,000 in ₹50,000 steps
        (15_000_000, 15_000_000),
        (6_200_000, 7_500_000),     # ₹62,000 -> ₹75,000 in ₹25,000 steps
        (100, 150),                 # ₹1 -> ₹1.50 in 50-paise steps
        (0, 0),
    ],
)
def test_the_axis_rounds_up_to_clean_intervals(peak, scale):
    assert views._nice_scale(peak) == scale


def test_monthly_ends_with_the_current_month_and_buckets_correctly():
    client = make_client()
    this_month = make_invoice(client, amount=6_000_000, issue_date=MONTH_START)
    make_invoice(client, amount=2_000_000, issue_date=LAST_MONTH)
    pay(this_month["invoice_id"], 1_500_000, on=MONTH_START)

    result = views.monthly(months=6)
    months = result["months"]
    assert len(months) == 6
    assert months[-1]["month"] == MONTH_START[:7]
    assert months[-1]["invoiced_minor"] == 6_000_000
    assert months[-1]["received_minor"] == 1_500_000
    assert months[-2]["invoiced_minor"] == 2_000_000
    assert result["scale_max_minor"] >= 6_000_000
    assert [t["display"] for t in result["ticks"]][0] == "₹0"


def test_an_empty_ledger_has_no_axis():
    result = views.monthly()
    assert result["scale_max_minor"] == 0
    assert result["ticks"] == []


def test_monthly_endpoint(api):
    assert api.get("/api/reports/monthly?months=3").json()["months"].__len__() == 3


# --- per-client breakdown -----------------------------------------------------


def test_clients_are_sorted_by_what_they_owe():
    small = make_client("Small Balance")
    large = make_client("Large Balance")
    settled = make_client("All Settled")
    make_invoice(small, amount=1_000_000)
    make_invoice(large, amount=9_000_000)
    paid = make_invoice(settled, amount=2_000_000)
    pay(paid["invoice_id"], 2_000_000)

    rows = views.client_breakdown()["clients"]
    assert [r["name"] for r in rows] == ["Large Balance", "Small Balance", "All Settled"]
    assert rows[2]["outstanding_total"] == []
    assert rows[2]["paid_invoice_count"] == 1


def test_a_period_scopes_invoiced_and_received_but_not_outstanding():
    client = make_client()
    make_invoice(client, amount=3_000_000, issue_date=LAST_MONTH)

    row = views.client_breakdown(MONTH_START, MONTH_END)["clients"][0]
    assert row["invoiced_total"] == []
    assert row["outstanding_total"][0]["total_minor"] == 3_000_000


# --- the payments ledger ------------------------------------------------------


def test_the_total_covers_every_match_not_just_the_page():
    client = make_client()
    invoice = make_invoice(client, amount=9_000_000)
    for _ in range(3):
        pay(invoice["invoice_id"], 1_000_000)

    ledger = views.payments_ledger(limit=1)
    assert len(ledger["payments"]) == 1
    assert ledger["count"] == 3
    assert ledger["received_total"][0]["total_minor"] == 3_000_000


def test_the_ledger_filters_by_date(api):
    client = make_client()
    invoice = make_invoice(client, amount=9_000_000, issue_date=LAST_MONTH)
    pay(invoice["invoice_id"], 1_000_000, on=LAST_MONTH)
    pay(invoice["invoice_id"], 2_000_000, on=MONTH_START)

    body = api.get(f"/api/payments?start_date={MONTH_START}&end_date={MONTH_END}").json()
    assert body["count"] == 1
    assert body["received_total"][0]["total_display"] == "₹20,000.00"
    assert "receipt_path" not in body["payments"][0]


def test_a_bad_date_is_refused(api):
    assert api.get("/api/payments?start_date=yesterday").status_code == 422


# --- overview -----------------------------------------------------------------


def test_overview_derives_every_headline_figure():
    rahul = make_client("Rahul Sharma")
    priya = make_client("Priya Deshmukh")
    make_client("No Invoices Yet")

    billed = make_invoice(rahul, amount=10_000_000, issue_date=MONTH_START)
    pay(billed["invoice_id"], 4_000_000, on=MONTH_START)
    make_invoice(priya, amount=2_850_000, issue_date=add_days(TODAY, -60),
                 due_date=add_days(TODAY, -37))

    view = views.overview()
    assert view["client_count"] == 3
    assert view["clients_with_balance"] == 2
    assert view["open_invoice_count"] == 2
    assert view["overdue_invoice_count"] == 1
    assert view["oldest_overdue"]["days_overdue"] == 37
    assert view["month"]["collection_rate_percent"] == 40
    assert view["needs_attention"][0]["client_name"] == "Priya Deshmukh"
    assert view["recent_activity"][0]["date"] >= view["recent_activity"][-1]["date"]


def test_average_days_to_payment_uses_the_settling_payment():
    client = make_client()
    invoice = make_invoice(client, amount=2_000_000, issue_date=add_days(TODAY, -30))
    pay(invoice["invoice_id"], 1_000_000, on=add_days(TODAY, -20))
    pay(invoice["invoice_id"], 1_000_000, on=add_days(TODAY, -6))

    view = views.overview()
    assert view["average_days_to_payment"] == 24
    assert view["settled_invoice_count"] == 1


def test_an_empty_ledger_has_no_rate_and_no_average(api):
    body = api.get("/api/reports/overview").json()
    assert body["month"]["collection_rate_percent"] is None
    assert body["average_days_to_payment"] is None
    assert body["needs_attention"] == []


def test_clients_endpoint(api):
    make_client()
    assert api.get("/api/reports/clients").json()["count"] == 1


# --- result cards come from tool results, never from the reply ---------------


def _call(name, result=None, error=None):
    return ToolCall(name=name, arguments={}, result=result, error=error)


def test_a_recorded_payment_produces_a_payment_card():
    client = make_client()
    invoice = make_invoice(client)
    recorded = pay(invoice["invoice_id"], 1_500_000)

    card = result_card([_call("find_client", {"status": "found"}),
                        _call("record_payment", recorded)])
    assert card["type"] == "payment"
    assert card["payment"]["amount_display"] == "₹15,000.00"
    assert card["invoice"]["outstanding_display"] == "₹25,000.00"
    assert "receipt_path" not in card["payment"]


def test_a_refused_payment_produces_no_card():
    refused = {"status": "error", "error": "more than the outstanding"}
    assert result_card([_call("record_payment", refused)]) is None


def test_a_failed_call_produces_no_card():
    assert result_card([_call("create_invoice", error="boom")]) is None


def test_a_read_only_turn_produces_no_card():
    assert result_card([_call("get_overdue_invoices", {"status": "ok"})]) is None


def test_a_created_invoice_produces_an_invoice_card():
    client = make_client()
    created = create_invoice(client_id=client, project="Logo", amount_minor=500_000)
    card = result_card([_call("create_invoice", created)])
    assert card["type"] == "invoice"
    assert card["invoice"]["invoice_number"] == "FF-0001"
    assert "pdf_path" not in card["invoice"]


# --- documents open in the browser rather than downloading -------------------


def test_documents_are_served_inline_with_their_number(api):
    client = make_client()
    invoice = make_invoice(client)
    payment = pay(invoice["invoice_id"], 1_000_000)["payment"]

    pdf = api.get(f"/api/invoices/{invoice['invoice_id']}/pdf")
    receipt = api.get(f"/api/payments/{payment['payment_id']}/receipt")
    for response, number in ((pdf, invoice["invoice_number"]), (receipt, "RC-0001")):
        assert response.status_code == 200
        disposition = response.headers["content-disposition"]
        assert disposition.startswith("inline")
        assert number in disposition


# --- the browser can actually edit a client ---------------------------------


def test_patch_passes_the_cors_preflight(api):
    response = api.options(
        "/api/clients/1",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
        },
    )
    assert response.status_code == 200
    assert "PATCH" in response.headers["access-control-allow-methods"]
