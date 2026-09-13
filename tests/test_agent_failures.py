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
