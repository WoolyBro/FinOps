"""Phase 4.10: the five scenarios named for this phase, driven tool-by-tool.

These are not agent tests -- there is still no live model wired in, so nothing
here proves an LLM would choose these tools on its own. What they prove is that
the tool chain each scenario needs actually produces the right answer when
called in the order a competent agent would call it. That is the ground truth
Phase 5's live model gets checked against.
"""

from app.dates import add_days, today_iso
from app.tools.clients import create_client, find_client
from app.tools.invoices import create_invoice
from app.tools.payments import record_payment
from app.tools.reminders import create_payment_reminder
from app.tools.reports import get_client_balance, get_financial_summary, get_overdue_invoices, get_outstanding_invoices

PAST = add_days(today_iso(), -4)


def make_client(name):
    return create_client(name=name)["client"]["client_id"]


def make_invoice(client_id, **overrides):
    kwargs = dict(project="Website development", amount_minor=4_000_000)
    kwargs.update(overrides)
    return create_invoice(client_id=client_id, **kwargs)["invoice"]


# --- Scenario A: "Who owes me money?" --------------------------------------


def test_scenario_a_who_owes_me_money():
    rahul = make_client("Rahul Sharma")
    priya = make_client("Priya")
    make_invoice(rahul, due_date=add_days(today_iso(), 10))
    paid = make_invoice(priya)
    record_payment(invoice_id=paid["invoice_id"], amount_minor=4_000_000)

    result = get_outstanding_invoices()
    assert result["count"] == 1
    assert result["invoices"][0]["client_name"] == "Rahul Sharma"


# --- Scenario B: "Who is overdue?" -----------------------------------------


def test_scenario_b_who_is_overdue():
    rahul = make_client("Rahul Sharma")
    priya = make_client("Priya")
    make_invoice(rahul, issue_date=add_days(PAST, -20), due_date=PAST)
    make_invoice(priya, due_date=add_days(today_iso(), 10))

    result = get_overdue_invoices()
    assert result["count"] == 1
    assert result["invoices"][0]["client_name"] == "Rahul Sharma"
    assert result["invoices"][0]["days_overdue"] == 4


# --- Scenario C: "How much have I made this month?" ------------------------


def test_scenario_c_how_much_have_i_made_this_month():
    from app.dates import current_month_bounds

    start, _ = current_month_bounds()
    client = make_client("Rahul Sharma")
    invoice = make_invoice(client, amount_minor=15_000_000)
    record_payment(invoice_id=invoice["invoice_id"], amount_minor=6_000_000, payment_date=start)

    result = get_financial_summary()
    assert result["received_total"][0]["total_display"] == "₹60,000.00"


# --- Scenario D: "Prepare a reminder for Rahul." ----------------------------


def test_scenario_d_prepare_a_reminder_for_rahul():
    rahul = make_client("Rahul Sharma")
    invoice = make_invoice(rahul, issue_date=add_days(PAST, -20), due_date=PAST)

    found = find_client(name="Rahul")
    assert found["status"] == "found"

    overdue = get_overdue_invoices(client_id=found["client"]["client_id"])
    assert overdue["count"] == 1
    target_invoice_id = overdue["invoices"][0]["invoice_id"]
    assert target_invoice_id == invoice["invoice_id"]

    reminder = create_payment_reminder(invoice_id=target_invoice_id)
    assert reminder["status"] == "prepared"
    assert "Rahul Sharma" in reminder["reminder"]["message"]
    assert "FF-0001" in reminder["reminder"]["message"]
    assert "4 days overdue" in reminder["reminder"]["message"]


# --- Scenario E: "Rahul paid the remaining ₹25,000." ------------------------


def test_scenario_e_rahul_paid_the_remaining_balance():
    """The scenario the user called out: state actually stays connected."""
    rahul = make_client("Rahul Sharma")
    invoice = make_invoice(
        rahul,
        amount_minor=4_000_000,
        issue_date=add_days(PAST, -20),
        due_date=PAST,
    )
    record_payment(invoice_id=invoice["invoice_id"], amount_minor=1_500_000)

    before = get_overdue_invoices(client_id=rahul)
    assert before["count"] == 1
    assert before["invoices"][0]["outstanding_display"] == "₹25,000.00"

    result = record_payment(invoice_id=invoice["invoice_id"], amount_minor=2_500_000)
    assert result["status"] == "recorded"
    assert result["invoice"]["invoice_status"] == "PAID"
    assert result["invoice"]["outstanding_minor"] == 0

    # The invoice no longer shows up anywhere money is still owed.
    assert get_overdue_invoices(client_id=rahul)["count"] == 0
    assert get_outstanding_invoices(client_id=rahul)["count"] == 0

    balance = get_client_balance(client_id=rahul)
    assert balance["outstanding_total"][0]["total_minor"] == 0
    assert balance["overdue_total"] == []  # no overdue invoice at all, not even at zero
    assert balance["invoice_counts_by_status"]["PAID"] == 1

    # And a reminder can no longer be prepared for it.
    assert create_payment_reminder(invoice_id=invoice["invoice_id"])["status"] == "error"
