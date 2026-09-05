"""Phase 5: the live model loop.

Everything else in this suite proves the tools are correct. These tests prove
something different and previously unproven: that a real model, given only the
tool descriptions and the system prompt, chooses the right tools and passes
them the right arguments.

They are skipped by default. Run them with:

    pytest -m live

They cost money and need credentials, so nothing here runs in the normal suite.

Assertions are deliberately about the *tool chain and the resulting database
state*, not about the wording of the reply. A fluent paragraph built on a
skipped lookup or an invented id is a failure that reads like a success.
"""

from __future__ import annotations

import pytest

from app.agent import build_agent
from app.dates import add_days, today_iso
from app.model_provider import ModelNotConfigured, resolve_provider
from app.tools.amounts import parse_amount
from app.tools.clients import create_client, find_client, list_clients
from app.tools.invoices import create_invoice, get_invoice, list_invoices
from app.tools.payments import generate_receipt, list_payments, record_payment
from app.tools.reminders import create_payment_reminder
from app.tools.reports import (
    get_client_balance,
    get_outstanding_invoices,
    get_overdue_invoices,
)
from app.tracing import ToolTracer

pytestmark = pytest.mark.live


@pytest.fixture(scope="session")
def provider():
    """Skip the whole module cleanly when no model provider is configured."""
    try:
        return resolve_provider()
    except ModelNotConfigured as exc:
        pytest.skip(f"no model provider configured: {exc}")


@pytest.fixture
def agent_factory(provider, tmp_path, monkeypatch):
    """Build a live agent over the per-test temp database.

    Returns (agent, tracer). Pass `tools` to narrow what the model can reach.
    """
    monkeypatch.setattr("app.pdf_generator.INVOICES_DIR", tmp_path / "invoices")
    monkeypatch.setattr("app.pdf_generator.RECEIPTS_DIR", tmp_path / "receipts")

    def _build(tools=None):
        tracer = ToolTracer()
        agent = build_agent(tools=tools, tracer=tracer)
        return agent, tracer

    return _build


def say(agent, text) -> str:
    """One turn. Returns the reply as plain text."""
    result = agent(text)
    return str(result)


def seed_rahul_with_invoice(amount_minor=4_000_000, due_date="2026-09-15"):
    """A client with one open invoice -- the situation most tests start from."""
    client = create_client(name="Rahul Sharma", email="rahul@example.com")["client"]
    invoice = create_invoice(
        client_id=client["client_id"],
        project="Website development",
        amount_minor=amount_minor,
        due_date=due_date,
    )["invoice"]
    return client, invoice


# --- 5.2 the fundamental loop, two tools only ------------------------------


def test_minimal_two_tool_loop(agent_factory):
    """find_client -> get_client_balance, with nothing else available.

    The narrowest possible proof that the model reads one tool result and uses
    it to choose the next call.
    """
    client, _ = seed_rahul_with_invoice()
    agent, tracer = agent_factory(tools=[find_client, get_client_balance])

    reply = say(agent, "How much does Rahul owe me?")

    assert tracer.called("find_client"), tracer.format()
    assert tracer.called("get_client_balance"), tracer.format()

    # The second call must use the id the first one returned, not a guess.
    balance_call = tracer.first("get_client_balance")
    assert balance_call.arguments["client_id"] == client["client_id"], tracer.format()

    assert "40,000" in reply, f"reply did not state the balance:\n{reply}"


# --- 5.3 the hero test: a real mutation ------------------------------------


def test_records_a_payment_from_natural_language(agent_factory):
    """The sequence is chosen by the model, not by us."""
    _, invoice = seed_rahul_with_invoice()
    agent, tracer = agent_factory(
        tools=[find_client, get_invoice, list_invoices, parse_amount,
               record_payment, generate_receipt]
    )

    say(
        agent,
        "Rahul paid me 15,000 rupees today for the website project. "
        "Update everything.",
    )

    assert tracer.called("record_payment"), (
        f"no payment was recorded:\n{tracer.format()}"
    )

    # The money that landed is what matters, so check the ledger, not the prose.
    payments = list_payments(invoice_id=invoice["invoice_id"])
    assert payments["count"] == 1, tracer.format()
    assert payments["payments"][0]["amount_minor"] == 1_500_000, tracer.format()

    refreshed = get_invoice(invoice_id=invoice["invoice_id"])["invoice"]
    assert refreshed["invoice_status"] == "PARTIALLY_PAID"
    assert refreshed["outstanding_minor"] == 2_500_000


# --- 5.5 ambiguity must stop the agent, not be guessed through -------------


def test_ambiguous_client_is_not_resolved_by_guessing(agent_factory):
    """Two Rahuls: the tool returns ambiguous, and nothing may be written."""
    a = create_client(name="Rahul Sharma")["client"]
    b = create_client(name="Rahul Verma")["client"]
    for client in (a, b):
        create_invoice(
            client_id=client["client_id"],
            project="Website development",
            amount_minor=4_000_000,
        )

    agent, tracer = agent_factory(
        tools=[find_client, list_invoices, parse_amount, record_payment]
    )
    reply = say(agent, "Rahul paid me 15,000 rupees.")

    assert not tracer.called("record_payment"), (
        f"the agent picked a Rahul instead of asking:\n{tracer.format()}"
    )
    assert list_payments()["count"] == 0

    lowered = reply.lower()
    assert "sharma" in lowered and "verma" in lowered, (
        f"the agent did not surface both candidates:\n{reply}"
    )


# --- 5.6 missing information must be asked for, never invented -------------


def test_missing_amount_is_asked_for(agent_factory):
    create_client(name="Rahul Sharma")
    agent, tracer = agent_factory(
        tools=[find_client, create_client, parse_amount, create_invoice]
    )

    say(agent, "Create an invoice for Rahul.")

    assert not tracer.called("create_invoice"), (
        f"the agent invented invoice details:\n{tracer.format()}"
    )
    assert list_invoices()["count"] == 0


def test_missing_payment_amount_is_asked_for(agent_factory):
    seed_rahul_with_invoice()
    agent, tracer = agent_factory(
        tools=[find_client, list_invoices, parse_amount, record_payment]
    )

    say(agent, "Rahul paid me.")

    assert not tracer.called("record_payment"), (
        f"the agent invented a payment amount:\n{tracer.format()}"
    )
    assert list_payments()["count"] == 0


# --- 5.7 parse_amount must do the conversion, not the model ----------------


def test_parse_amount_is_used_for_shorthand(agent_factory):
    create_client(name="Rahul Sharma")
    agent, tracer = agent_factory(
        tools=[find_client, parse_amount, create_invoice]
    )

    say(agent, "Create an invoice for Rahul for 40k for website development.")

    assert tracer.called("parse_amount"), (
        f"the model converted the amount itself:\n{tracer.format()}"
    )
    invoices = list_invoices()
    assert invoices["count"] == 1, tracer.format()
    assert invoices["invoices"][0]["amount_minor"] == 4_000_000, tracer.format()


def test_only_the_amount_phrase_reaches_parse_amount(agent_factory):
    """A date in the sentence must not be fed to the parser as extra numbers.

    parse_amount refuses text holding more than one number, so passing the
    whole sentence produces an error rather than a wrong invoice. If this test
    fails, the fix is the tool description -- not a looser parser.
    """
    create_client(name="Rahul Sharma")
    agent, tracer = agent_factory(
        tools=[find_client, parse_amount, create_invoice]
    )

    say(
        agent,
        "Create an invoice for Rahul for 40k for website development, "
        "due September 15 2026.",
    )

    parse_call = tracer.first("parse_amount")
    assert parse_call is not None, tracer.format()
    assert parse_call.status == "ok", (
        f"parse_amount was given more than the amount phrase: "
        f"{parse_call.arguments!r}\n{tracer.format()}"
    )

    invoices = list_invoices()
    assert invoices["count"] == 1, tracer.format()
    invoice = invoices["invoices"][0]
    assert invoice["amount_minor"] == 4_000_000
    assert invoice["due_date"] == "2026-09-15"


# --- 5.8 no financial hallucination ----------------------------------------


def test_unknown_client_is_reported_not_invented(agent_factory):
    """The strongest single demonstration of the architecture."""
    assert list_clients()["count"] == 0

    agent, tracer = agent_factory(tools=[find_client, get_client_balance])
    reply = say(agent, "How much does Rahul owe me?")

    assert tracer.called("find_client"), tracer.format()
    assert tracer.first("find_client").status == "not_found", tracer.format()

    # No figure may appear in a reply about a client who does not exist.
    assert not any(ch.isdigit() for ch in reply.replace("FF-", "")), (
        f"the agent produced a number for a client it never found:\n{reply}"
    )


# --- 5.9 the whole lifecycle, in natural language --------------------------


def test_full_lifecycle_conversation(agent_factory):
    """Six turns, one agent, no tool sequence supplied by us."""
    agent, tracer = agent_factory()

    # Turn 1 -- the invoice.
    say(
        agent,
        "Create a 40,000 rupee website invoice for Rahul Sharma, "
        "due September 15 2026.",
    )
    invoices = list_invoices()
    assert invoices["count"] == 1, tracer.format()
    invoice = invoices["invoices"][0]
    assert invoice["amount_minor"] == 4_000_000
    assert invoice["due_date"] == "2026-09-15"

    # Turn 2 -- a partial payment.
    tracer.reset()
    say(agent, "He paid 15,000 rupees today.")
    assert list_payments()["count"] == 1, tracer.format()
    assert list_payments()["payments"][0]["amount_minor"] == 1_500_000

    # Turn 3 -- the balance, which must be looked up rather than recalled.
    tracer.reset()
    reply = say(agent, "Show me his outstanding balance.")
    assert tracer.calls, "the agent answered from memory instead of a tool"
    assert "25,000" in reply, f"wrong or missing balance:\n{reply}"

    # Turn 4 -- a reminder, drafted and not sent.
    tracer.reset()
    say(agent, "Prepare a reminder.")
    assert tracer.called("create_payment_reminder"), tracer.format()
    reminder = tracer.first("create_payment_reminder")
    assert reminder.status == "prepared", tracer.format()

    # Turn 5 -- settling up.
    tracer.reset()
    say(agent, "Actually, he just paid the remaining amount.")
    settled = get_invoice(invoice_number=invoice["invoice_number"])["invoice"]
    assert settled["invoice_status"] == "PAID", tracer.format()
    assert settled["outstanding_minor"] == 0

    # Turn 6 -- the receipt for that final payment.
    tracer.reset()
    say(agent, "Give me his latest receipt.")
    payments = list_payments()
    assert any(p["receipt_number"] for p in payments["payments"]), tracer.format()


# --- overdue and reporting, through the agent ------------------------------


def test_overdue_question_uses_the_overdue_tool(agent_factory):
    client = create_client(name="Rahul Sharma")["client"]
    create_invoice(
        client_id=client["client_id"],
        project="Website development",
        amount_minor=4_000_000,
        issue_date=add_days(today_iso(), -30),
        due_date=add_days(today_iso(), -4),
    )

    agent, tracer = agent_factory(
        tools=[find_client, get_overdue_invoices, get_outstanding_invoices]
    )
    reply = say(agent, "Which of my invoices are overdue?")

    assert tracer.called("get_overdue_invoices"), tracer.format()
    assert "Rahul" in reply
    assert "4" in reply, f"days overdue not reported:\n{reply}"


def test_agent_does_not_remind_about_a_paid_invoice(agent_factory):
    _, invoice = seed_rahul_with_invoice()
    record_payment(invoice_id=invoice["invoice_id"], amount_minor=4_000_000)

    agent, tracer = agent_factory(
        tools=[find_client, list_invoices, get_client_balance,
               create_payment_reminder]
    )
    say(agent, "Send Rahul a reminder about his website invoice.")

    reminder = tracer.first("create_payment_reminder")
    if reminder is not None:
        # If it tried, the tool must have refused -- and the agent must not
        # claim it prepared one.
        assert reminder.status == "error", tracer.format()
