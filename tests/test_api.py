"""Phase 6: the HTTP layer.

These run against the same temp database as every other test, through
FastAPI's TestClient. No model is involved: the chat endpoint is exercised with
a stubbed agent service, because whether a real model answers well is a live
test, not an API test.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_agent_service
from app.api.main import create_app
from app.dates import add_days, today_iso
from app.services.agent_service import AgentUnavailable
from app.tools.clients import create_client
from app.tools.invoices import create_invoice
from app.tools.payments import record_payment


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pdf_generator.INVOICES_DIR", tmp_path / "invoices")
    monkeypatch.setattr("app.pdf_generator.RECEIPTS_DIR", tmp_path / "receipts")
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seeded():
    """A client, an overdue invoice, and a partial payment against it."""
    rahul = create_client(name="Rahul Sharma", email="rahul@example.com")["client"]
    invoice = create_invoice(
        client_id=rahul["client_id"],
        project="Website development",
        amount_minor=4_000_000,
        issue_date=add_days(today_iso(), -30),
        due_date=add_days(today_iso(), -4),
    )["invoice"]
    payment = record_payment(
        invoice_id=invoice["invoice_id"], amount_minor=1_500_000
    )["payment"]
    return {"client": rahul, "invoice": invoice, "payment": payment}


# --- meta -------------------------------------------------------------------


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_documents_every_endpoint(client):
    paths = client.get("/openapi.json").json()["paths"]
    for required in (
        "/api/chat",
        "/api/invoices",
        "/api/invoices/{invoice_id}",
        "/api/payments",
        "/api/clients",
        "/api/reports/summary",
        "/api/reports/overdue",
        "/api/reports/outstanding",
    ):
        assert required in paths, f"{required} is not exposed"


# --- clients ----------------------------------------------------------------


def test_client_retrieval(client, seeded):
    response = client.get("/api/clients")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["clients"][0]["name"] == "Rahul Sharma"


def test_client_detail_includes_balance_and_history(client, seeded):
    client_id = seeded["client"]["client_id"]
    body = client.get(f"/api/clients/{client_id}").json()

    assert body["balance"]["client_name"] == "Rahul Sharma"
    assert body["balance"]["outstanding_total"][0]["total_minor"] == 2_500_000
    assert len(body["invoices"]) == 1
    assert len(body["payments"]) == 1


def test_unknown_client_is_a_clean_404(client):
    response = client.get("/api/clients/9999")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "not_found"
    assert "9999" in body["detail"]


# --- invoices ---------------------------------------------------------------


def test_invoice_retrieval(client, seeded):
    body = client.get("/api/invoices").json()
    assert body["count"] == 1
    invoice = body["invoices"][0]
    assert invoice["invoice_number"] == "FF-0001"
    assert invoice["outstanding_minor"] == 2_500_000
    assert invoice["invoice_status"] == "PARTIALLY_PAID"
    assert invoice["is_overdue"] is True


def test_invoice_detail_includes_its_payments(client, seeded):
    invoice_id = seeded["invoice"]["invoice_id"]
    body = client.get(f"/api/invoices/{invoice_id}").json()
    assert body["invoice"]["invoice_number"] == "FF-0001"
    assert len(body["payments"]) == 1
    assert body["payments"][0]["amount_minor"] == 1_500_000


def test_invoices_filter_by_status(client, seeded):
    assert client.get("/api/invoices?status=PARTIALLY_PAID").json()["count"] == 1
    assert client.get("/api/invoices?status=PAID").json()["count"] == 0


def test_invoices_reject_an_unknown_status(client, seeded):
    response = client.get("/api/invoices?status=OVERDUE")
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_unknown_invoice_is_a_clean_404(client):
    response = client.get("/api/invoices/4242")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_invoice_pdf_is_served(client, seeded):
    invoice_id = seeded["invoice"]["invoice_id"]
    response = client.get(f"/api/invoices/{invoice_id}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_invoice_pdf_for_a_missing_invoice_is_404(client):
    assert client.get("/api/invoices/4242/pdf").status_code == 404


# --- payments ---------------------------------------------------------------


def test_payment_retrieval(client, seeded):
    body = client.get("/api/payments").json()
    assert body["count"] == 1
    payment = body["payments"][0]
    assert payment["amount_minor"] == 1_500_000
    assert payment["outstanding_after_minor"] == 2_500_000


def test_payments_filter_by_invoice(client, seeded):
    invoice_id = seeded["invoice"]["invoice_id"]
    assert client.get(f"/api/payments?invoice_id={invoice_id}").json()["count"] == 1
    assert client.get("/api/payments?invoice_id=9999").json()["count"] == 0


def test_unknown_payment_is_a_clean_404(client):
    response = client.get("/api/payments/4242")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_receipt_is_served_and_reuses_one_number(client, seeded):
    payment_id = seeded["payment"]["payment_id"]

    first = client.get(f"/api/payments/{payment_id}/receipt")
    assert first.status_code == 200
    assert first.content.startswith(b"%PDF")

    # Asking again must not issue a second receipt number.
    second = client.get(f"/api/payments/{payment_id}/receipt")
    assert second.status_code == 200
    assert client.get(f"/api/payments/{payment_id}").json()["payment"][
        "receipt_number"
    ] == "RC-0001"


def test_receipt_for_a_missing_payment_is_404(client):
    assert client.get("/api/payments/4242/receipt").status_code == 404


# --- reports ----------------------------------------------------------------


def test_summary(client, seeded):
    body = client.get("/api/reports/summary").json()
    assert body["status"] == "ok"
    assert body["received_total"][0]["total_minor"] == 1_500_000
    assert body["outstanding_total"][0]["total_minor"] == 2_500_000
    assert body["overdue_total"][0]["total_minor"] == 2_500_000


def test_summary_accepts_a_period(client, seeded):
    body = client.get(
        "/api/reports/summary?start_date=2020-01-01&end_date=2020-01-31"
    ).json()
    assert body["period_start"] == "2020-01-01"
    assert body["received_total"] == []


def test_summary_rejects_a_bad_period(client, seeded):
    response = client.get(
        "/api/reports/summary?start_date=2026-09-10&end_date=2026-09-01"
    )
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_summary_rejects_an_unparseable_date(client, seeded):
    response = client.get("/api/reports/summary?start_date=not-a-date")
    assert response.status_code == 422


def test_overdue_invoices(client, seeded):
    body = client.get("/api/reports/overdue").json()
    assert body["count"] == 1
    assert body["invoices"][0]["days_overdue"] == 4
    assert body["overdue_total"][0]["total_display"] == "₹25,000.00"


def test_outstanding_invoices(client, seeded):
    body = client.get("/api/reports/outstanding").json()
    assert body["count"] == 1
    assert body["outstanding_total"][0]["total_minor"] == 2_500_000


def test_reports_filter_by_client(client, seeded):
    other = create_client(name="Priya")["client"]
    assert client.get(f"/api/reports/overdue?client_id={other['client_id']}").json()[
        "count"
    ] == 0


# --- encoding ---------------------------------------------------------------


def test_the_rupee_sign_survives_as_utf8(client, seeded):
    """Not inherited from a framework default -- asserted at the HTTP layer."""
    response = client.get("/api/invoices")

    assert "charset=utf-8" in response.headers["content-type"].lower()
    assert "₹".encode("utf-8") in response.content
    assert "₹40,000.00" in response.json()["invoices"][0]["amount_display"]


def test_indian_digit_grouping_reaches_the_api(client):
    rahul = create_client(name="Rahul Sharma")["client"]
    create_invoice(
        client_id=rahul["client_id"],
        project="Brand system",
        amount_minor=15_000_000,
    )
    body = client.get("/api/invoices").json()
    assert body["invoices"][0]["amount_display"] == "₹1,50,000.00"


# --- malformed requests -----------------------------------------------------


def test_non_integer_id_is_a_clean_422(client):
    response = client.get("/api/invoices/not-a-number")
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_request"
    assert body["problems"]


def test_out_of_range_limit_is_rejected(client):
    assert client.get("/api/invoices?limit=0").status_code == 422
    assert client.get("/api/invoices?limit=9999").status_code == 422


def test_unknown_route_is_a_clean_404(client):
    response = client.get("/api/nonexistent")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_wrong_method_is_reported_cleanly(client):
    # POST /api/invoices creates an invoice, so use a method nothing supports.
    response = client.put("/api/invoices")
    assert response.status_code == 405
    assert response.json()["error"] == "method_not_allowed"


# --- CORS -------------------------------------------------------------------


def test_cors_allows_the_frontend_origin(client):
    response = client.get(
        "/api/health", headers={"Origin": "http://localhost:3000"}
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_preflight(client):
    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert "POST" in response.headers["access-control-allow-methods"]


# --- the chat endpoint ------------------------------------------------------


class StubAgentService:
    """Stands in for the real service. No model, no Strands, no spend."""

    def __init__(self, available=True):
        self.available = available
        self.calls = []

    def status(self):
        if self.available:
            return {
                "available": True,
                "provider": "bedrock",
                "model_id": "global.anthropic.claude-sonnet-4-6",
                "detail": None,
                "active_sessions": 0,
            }
        return {
            "available": False,
            "provider": None,
            "model_id": None,
            "detail": "No model provider is available.",
            "active_sessions": 0,
        }

    def chat(self, message, session_id=None):
        if not self.available:
            raise AgentUnavailable("No model provider is available.")
        if not message.strip():
            raise ValueError("message cannot be empty")
        self.calls.append((message, session_id))
        return {
            "session_id": session_id or "stub-session",
            "reply": "Recorded ₹15,000.00 against FF-0001.",
            "tool_calls": [
                {
                    "tool": "record_payment",
                    "arguments": {"invoice_id": 1, "amount_minor": 1_500_000},
                    "status": "recorded",
                    "error": None,
                    "duration_seconds": 0.01,
                }
            ],
            "turn": 1,
            "elapsed_seconds": 0.5,
        }

    def reset(self, session_id):
        return session_id == "stub-session"


@pytest.fixture
def stub_service(app):
    stub = StubAgentService()
    app.dependency_overrides[get_agent_service] = lambda: stub
    yield stub
    app.dependency_overrides.clear()


def test_chat_returns_the_reply_and_the_tool_calls(client, stub_service):
    response = client.post("/api/chat", json={"message": "Rahul paid 15k."})
    assert response.status_code == 200

    body = response.json()
    assert body["reply"].startswith("Recorded")
    assert body["tool_calls"][0]["tool"] == "record_payment"
    assert body["tool_calls"][0]["arguments"]["amount_minor"] == 1_500_000
    assert body["session_id"] == "stub-session"


def test_chat_passes_the_session_through(client, stub_service):
    client.post(
        "/api/chat", json={"message": "And the rest?", "session_id": "abc123"}
    )
    assert stub_service.calls[-1] == ("And the rest?", "abc123")


def test_chat_rejects_an_empty_message(client, stub_service):
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_chat_rejects_a_missing_message(client, stub_service):
    response = client.post("/api/chat", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_request"
    assert any("message" in p["field"] for p in body["problems"])


def test_chat_rejects_malformed_json(client, stub_service):
    response = client.post(
        "/api/chat",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"


def test_chat_reply_keeps_its_unicode(client, stub_service):
    response = client.post("/api/chat", json={"message": "status?"})
    assert "₹15,000.00" in response.json()["reply"]
    assert "₹".encode("utf-8") in response.content


def test_session_can_be_reset(client, stub_service):
    assert client.delete("/api/chat/stub-session").status_code == 204
    assert client.delete("/api/chat/unknown-session").status_code == 404


# --- honesty when no model is configured ------------------------------------


def test_agent_status_reports_unavailability(client, app):
    stub = StubAgentService(available=False)
    app.dependency_overrides[get_agent_service] = lambda: stub

    body = client.get("/api/agent/status").json()
    assert body["available"] is False
    assert body["provider"] is None
    assert "No model provider" in body["detail"]

    app.dependency_overrides.clear()


def test_chat_refuses_rather_than_faking_a_reply(client, app):
    """A 503 with the reason, never a plausible sentence no model produced."""
    stub = StubAgentService(available=False)
    app.dependency_overrides[get_agent_service] = lambda: stub

    response = client.post("/api/chat", json={"message": "Rahul paid 15k."})
    assert response.status_code == 503

    body = response.json()
    assert body["error"] == "agent_unavailable"
    assert "No model provider" in body["detail"]
    assert "reply" not in body

    app.dependency_overrides.clear()


def test_the_real_service_is_unavailable_without_credentials(client):
    """With no AWS and no Ollama, the endpoint must say so."""
    body = client.get("/api/agent/status").json()
    assert isinstance(body["available"], bool)
    if not body["available"]:
        assert body["detail"]
        assert client.post(
            "/api/chat", json={"message": "hello"}
        ).status_code == 503


# --- the data layer keeps working while the agent is down -------------------


def test_records_are_readable_without_a_model(client, seeded):
    """The dashboard must not depend on Bedrock being configured."""
    for path in (
        "/api/clients",
        "/api/invoices",
        "/api/payments",
        "/api/reports/summary",
        "/api/reports/overdue",
        "/api/reports/outstanding",
    ):
        assert client.get(path).status_code == 200, path
