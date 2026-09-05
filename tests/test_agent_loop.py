"""The agent loop and its instrumentation, proven offline.

These run in the normal suite with no credentials. They do not prove a real
model makes good choices -- that is what `pytest -m live` is for. They prove
that when a model does make a choice, the tool actually runs, the result comes
back, the database changes, and the tracer records it faithfully.

Without this, a failing live test is ambiguous: bad model, or broken wiring?
"""

from __future__ import annotations

import pytest
from strands import Agent

from app.agent import TOOLS, system_prompt
from app.tools.clients import create_client, find_client
from app.tools.invoices import create_invoice, get_invoice
from app.tools.payments import list_payments, record_payment
from app.tools.reports import get_client_balance
from app.tracing import ToolTracer

from tests.scripted_model import ScriptedModel


def build_scripted_agent(script, tools=None):
    tracer = ToolTracer()
    agent = Agent(
        model=ScriptedModel(script),
        tools=list(tools) if tools is not None else TOOLS,
        system_prompt=system_prompt(),
        hooks=[tracer],
    )
    return agent, tracer


@pytest.fixture
def rahul_with_invoice():
    client = create_client(name="Rahul Sharma", email="rahul@example.com")["client"]
    invoice = create_invoice(
        client_id=client["client_id"],
        project="Website development",
        amount_minor=4_000_000,
        due_date="2026-09-15",
    )["invoice"]
    return client, invoice


# --- the loop itself --------------------------------------------------------


def test_a_tool_call_actually_executes(rahul_with_invoice):
    client, _ = rahul_with_invoice
    agent, tracer = build_scripted_agent(
        [
            [("find_client", {"name": "Rahul"})],
            "Found him.",
        ],
        tools=[find_client],
    )

    agent("Who is Rahul?")

    assert tracer.names == ["find_client"]
    assert tracer.first("find_client").status == "found"
    assert tracer.first("find_client").result["client"]["client_id"] == client["client_id"]


def test_tool_result_is_fed_back_to_the_model(rahul_with_invoice):
    """The second request must contain the first tool's result."""
    agent, tracer = build_scripted_agent(
        [
            [("find_client", {"name": "Rahul"})],
            "Rahul owes you money.",
        ],
        tools=[find_client],
    )
    agent("Who is Rahul?")

    model = agent.model
    assert len(model.requests) == 2, "the model was not called again with the result"
    second_turn = str(model.requests[1]["messages"])
    assert "Rahul Sharma" in second_turn


def test_multi_step_chain_passes_ids_between_tools(rahul_with_invoice):
    """find_client -> get_client_balance, the Phase 5.2 shape."""
    client, _ = rahul_with_invoice
    agent, tracer = build_scripted_agent(
        [
            [("find_client", {"name": "Rahul"})],
            [("get_client_balance", {"client_id": client["client_id"]})],
            "Rahul owes 40,000 rupees.",
        ],
        tools=[find_client, get_client_balance],
    )

    reply = agent("How much does Rahul owe me?")

    assert tracer.names == ["find_client", "get_client_balance"]
    balance = tracer.first("get_client_balance")
    assert balance.result["outstanding_total"][0]["total_display"] == "₹40,000.00"
    assert "40,000" in str(reply)


def test_a_mutation_through_the_loop_changes_the_database(rahul_with_invoice):
    _, invoice = rahul_with_invoice
    agent, tracer = build_scripted_agent(
        [
            [("record_payment", {
                "invoice_id": invoice["invoice_id"],
                "amount_minor": 1_500_000,
            })],
            "Recorded 15,000 rupees.",
        ],
        tools=[record_payment],
    )

    agent("Rahul paid 15,000.")

    assert list_payments()["count"] == 1
    refreshed = get_invoice(invoice_id=invoice["invoice_id"])["invoice"]
    assert refreshed["invoice_status"] == "PARTIALLY_PAID"
    assert refreshed["outstanding_minor"] == 2_500_000


def test_parallel_tool_calls_in_one_turn_are_all_traced(rahul_with_invoice):
    client, invoice = rahul_with_invoice
    agent, tracer = build_scripted_agent(
        [
            [
                ("find_client", {"name": "Rahul"}),
                ("get_client_balance", {"client_id": client["client_id"]}),
            ],
            "Done.",
        ],
        tools=[find_client, get_client_balance],
    )

    agent("Tell me about Rahul.")

    assert sorted(tracer.names) == ["find_client", "get_client_balance"]
    assert all(c.result is not None for c in tracer.calls), tracer.format()


# --- the tracer -------------------------------------------------------------


def test_tracer_records_arguments_the_model_chose(rahul_with_invoice):
    agent, tracer = build_scripted_agent(
        [
            [("find_client", {"name": "Rahul Sharma"})],
            "ok",
        ],
        tools=[find_client],
    )
    agent("Find Rahul Sharma.")

    assert tracer.first("find_client").arguments == {"name": "Rahul Sharma"}


def test_tracer_unwraps_the_tool_result_envelope(rahul_with_invoice):
    """Strands wraps returns as {'content': [{'text': '<json>'}]}."""
    agent, tracer = build_scripted_agent(
        [[("find_client", {"name": "Nobody"})], "Not found."],
        tools=[find_client],
    )
    agent("Find Nobody.")

    result = tracer.first("find_client").result
    assert isinstance(result, dict), f"envelope not unwrapped: {result!r}"
    assert result["status"] == "not_found"
    assert tracer.first("find_client").status == "not_found"


def test_tracer_records_a_failed_tool_without_claiming_success(rahul_with_invoice):
    _, invoice = rahul_with_invoice
    agent, tracer = build_scripted_agent(
        [
            [("record_payment", {
                "invoice_id": invoice["invoice_id"],
                "amount_minor": 99_000_000,  # more than outstanding
            })],
            "That did not work.",
        ],
        tools=[record_payment],
    )

    agent("Rahul paid 9,90,000.")

    call = tracer.first("record_payment")
    assert call.status == "error", tracer.format()
    assert list_payments()["count"] == 0


def test_tracer_helpers():
    agent, tracer = build_scripted_agent(
        [
            [("find_client", {"name": "A"}), ("find_client", {"name": "B"})],
            "ok",
        ],
        tools=[find_client],
    )
    agent("Find A and B.")

    assert tracer.called("find_client")
    assert not tracer.called("record_payment")
    assert len(tracer.all_of("find_client")) == 2
    assert tracer.first("record_payment") is None

    tracer.reset()
    assert tracer.calls == []
    assert tracer.format() == "(no tools were called)"


def test_tracer_format_is_readable(rahul_with_invoice):
    agent, tracer = build_scripted_agent(
        [[("find_client", {"name": "Rahul"})], "ok"],
        tools=[find_client],
    )
    agent("Find Rahul.")

    text = tracer.format()
    assert "1. find_client" in text
    assert "Rahul" in text
    assert "found" in text


def test_tracer_records_durations(rahul_with_invoice):
    agent, tracer = build_scripted_agent(
        [[("find_client", {"name": "Rahul"})], "ok"],
        tools=[find_client],
    )
    agent("Find Rahul.")
    assert tracer.first("find_client").duration_seconds is not None


# --- what the model is actually shown ---------------------------------------


def test_every_tool_is_offered_to_the_model(rahul_with_invoice):
    agent, _ = build_scripted_agent(["Nothing to do."])
    agent("Hello.")

    offered = {spec["name"] for spec in agent.model.requests[0]["tool_specs"]}
    assert offered == {t.tool_name for t in TOOLS}
    assert len(offered) == 21


def test_the_system_prompt_reaches_the_model(rahul_with_invoice):
    agent, _ = build_scripted_agent(["Hi."])
    agent("Hello.")

    prompt = agent.model.requests[0]["system_prompt"]
    assert "Never invent financial information" in prompt
    assert "parse_amount" in prompt


def test_a_subset_agent_only_offers_its_subset(rahul_with_invoice):
    agent, _ = build_scripted_agent(["Hi."], tools=[find_client, get_client_balance])
    agent("Hello.")

    offered = {spec["name"] for spec in agent.model.requests[0]["tool_specs"]}
    assert offered == {"find_client", "get_client_balance"}
