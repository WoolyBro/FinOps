"""When the model fails mid-turn, say why -- and show what already happened.

A turn can call record_payment successfully and then die on the next model
call. Reporting that as a bare 500 hides a real write; reporting the raw
provider error can leak account ids. These tests pin the middle path: an
actionable reason, the completed operations, and nothing internal.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_agent_service
from app.api.main import create_app
from app.services import agent_service as module
from app.services.agent_service import AgentFailed, AgentService, explain_failure
from app.tracing import ToolCall


class ExplodingAgent:
    """Records one tool call, then fails the way a model provider would."""

    def __init__(self, tracer, exc):
        self.tracer = tracer
        self.exc = exc

    def __call__(self, message):
        self.tracer.calls.append(
            ToolCall(
                name="record_payment",
                arguments={"invoice_id": 5, "amount_minor": 1_500_000},
                result={"status": "recorded"},
                duration_seconds=0.2,
            )
        )
        raise self.exc


def service_that_fails(monkeypatch, exc, provider="bedrock"):
    status = {"available": True, "provider": provider, "model_id": "apac.amazon.nova-pro-v1:0",
              "region": "ap-south-1", "detail": None}
    monkeypatch.setattr(module, "provider_status", lambda: status)
    monkeypatch.setattr(module, "build_agent", lambda tracer, **_: ExplodingAgent(tracer, exc))
    return AgentService()


def test_completed_operations_survive_a_failed_turn(monkeypatch):
    service = service_that_fails(monkeypatch, RuntimeError("model went away"))
    with pytest.raises(AgentFailed) as failure:
        service.chat("Rahul paid me 15k")
    assert [c["tool"] for c in failure.value.tool_calls] == ["record_payment"]
    assert failure.value.tool_calls[0]["status"] == "recorded"


def test_access_denied_gets_the_model_access_diagnosis():
    detail = explain_failure(
        Exception("AccessDeniedException: not authorized"),
        {"provider": "bedrock", "model_id": "apac.amazon.nova-pro-v1:0", "region": "ap-south-1"},
    )
    assert "model access" in detail
    assert "ap-south-1" in detail
    assert "\n" not in detail


def test_an_unrecognised_error_does_not_leak_its_text():
    secret = "arn:aws:iam::123456789012:role/Secret at C:\\Users\\me\\key.pem"
    detail = explain_failure(
        RuntimeError(secret),
        {"provider": "bedrock", "model_id": "m", "region": "r"},
    )
    assert "123456789012" not in detail
    assert "key.pem" not in detail
    assert "RuntimeError" in detail


def test_an_unreachable_ollama_says_how_to_start_it():
    detail = explain_failure(
        ConnectionError("[WinError 10061] Connection refused"),
        {"provider": "ollama", "model_id": "llama3.1"},
    )
    assert "ollama serve" in detail
    assert "llama3.1" in detail


def test_the_api_returns_502_with_the_trace(monkeypatch, tmp_path):
    service = service_that_fails(monkeypatch, Exception("AccessDeniedException"))
    app = create_app()
    app.dependency_overrides[get_agent_service] = lambda: service
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"message": "Rahul paid me 15k"})
    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "agent_failed"
    assert "model access" in body["detail"]
    assert body["result"]["tool_calls"][0]["tool"] == "record_payment"


# --- replies never carry server paths ----------------------------------------------


class ChattyAgent:
    """Succeeds, but repeats the file paths it read in a tool result."""

    def __init__(self, tracer):
        self.tracer = tracer

    def __call__(self, message):
        return (
            r"Recorded. Invoice PDF updated at `C:\Users\someone\data\invoices\FF-0005.pdf` "
            "and receipt at /home/someone/app/data/receipts/RC-0001.pdf."
        )


def test_a_reply_that_repeats_a_server_path_is_redacted(monkeypatch):
    status = {"available": True, "provider": "gemini", "model_id": "gemini-3.5-flash-lite",
              "region": None, "detail": None}
    monkeypatch.setattr(module, "provider_status", lambda: status)
    monkeypatch.setattr(module, "build_agent", lambda tracer, **_: ChattyAgent(tracer))

    reply = AgentService().chat("Rahul paid me 15k")["reply"]
    assert "someone" not in reply
    assert "C:\\" not in reply
    assert "/home/" not in reply
    assert reply.startswith("Recorded.")


def test_the_prompt_no_longer_asks_for_file_locations():
    from app.agent import system_prompt

    prompt = system_prompt()
    assert "where it was saved" not in prompt
    assert "Never mention a\n   file path" in prompt


# --- the payment card shows the receipt issued in the same turn ---------------------


def _recorded(payment_id=7):
    return ToolCall(
        name="record_payment",
        arguments={"invoice_id": 5, "amount_minor": 1_500_000},
        result={
            "status": "recorded",
            "payment": {"payment_id": payment_id, "receipt_number": None,
                        "invoice_amount_display": "₹40,000.00",
                        "paid_to_date_display": "₹15,000.00",
                        "outstanding_after_display": "₹25,000.00"},
            "invoice": {"invoice_id": 5, "invoice_number": "FF-0005"},
        },
    )


def test_a_receipt_issued_later_in_the_turn_appears_on_the_card():
    from app.services.agent_service import result_card

    receipt = ToolCall(
        name="generate_receipt",
        arguments={"payment_id": 7},
        result={"status": "created", "receipt_number": "RC-0001", "receipt_path": "/tmp/x.pdf"},
    )
    card = result_card([_recorded(), receipt])
    assert card["type"] == "payment"
    assert card["payment"]["receipt_number"] == "RC-0001"
    assert card["payment"]["invoice_amount_display"] == "₹40,000.00"
    assert card["payment"]["outstanding_after_display"] == "₹25,000.00"


def test_a_receipt_for_a_different_payment_is_not_borrowed():
    from app.services.agent_service import result_card

    other = ToolCall(
        name="generate_receipt",
        arguments={"payment_id": 99},
        result={"status": "created", "receipt_number": "RC-0042"},
    )
    card = result_card([_recorded(), other])
    assert card["payment"]["receipt_number"] is None


def test_a_failed_receipt_is_not_shown():
    from app.services.agent_service import result_card

    failed = ToolCall(
        name="generate_receipt",
        arguments={"payment_id": 7},
        result={"status": "error", "receipt_number": "RC-0001"},
    )
    assert result_card([_recorded(), failed])["payment"]["receipt_number"] is None
