"""The write endpoints: the app is operable without a model.

The point of these is that the dashboard is a real application, not a viewer
that only works when Bedrock is reachable. And because every write goes through
the same tools the agent uses, the guarantees are identical -- these tests
assert that the refusals arrive intact rather than being softened on the way
out.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.dates import add_days, today_iso


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pdf_generator.INVOICES_DIR", tmp_path / "invoices")
    monkeypatch.setattr("app.pdf_generator.RECEIPTS_DIR", tmp_path / "receipts")
    with TestClient(create_app()) as test_client:
        yield test_client


def make_client(client, name="Rahul Sharma", **extra):
    return client.post("/api/clients", json={"name": name, **extra}).json()["client"]


def make_invoice(client, client_id, **overrides):
    body = {
        "client_id": client_id,
        "project": "Website development",
        "amount_minor": 4_000_000,
    }
    body.update(overrides)
    return client.post("/api/invoices", json=body)


# --- amounts ---------------------------------------------------------------


@pytest.mark.parametrize(
    "text,minor,display",
    [
        ("40k", 4_000_000, "₹40,000.00"),
        ("1.5 lakh", 15_000_000, "₹1,50,000.00"),
        ("40000", 4_000_000, "₹40,000.00"),
    ],
)
def test_the_browser_never_does_money_arithmetic(client, text, minor, display):
    """The form sends what was typed; the server converts it."""
    body = client.post("/api/amounts/parse", json={"text": text}).json()
    assert body["amount_minor"] == minor
    assert body["amount_display"] == display


def test_an_unparseable_amount_is_refused_with_its_reason(client):
    response = client.post("/api/amounts/parse", json={"text": "some money"})
    assert response.status_code == 409
    assert response.json()["error"] == "invalid_amount"


def test_an_ambiguous_amount_is_refused(client):
    response = client.post("/api/amounts/parse", json={"text": "40000 and 15000"})
    assert response.status_code == 409
    assert "more than one amount" in response.json()["detail"]


# --- clients ---------------------------------------------------------------


def test_create_a_client(client):
    response = client.post(
        "/api/clients", json={"name": "Rahul Sharma", "email": "r@example.com"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "created"
    assert body["client"]["name"] == "Rahul Sharma"

    assert client.get("/api/clients").json()["count"] == 1


def test_a_duplicate_client_is_not_created_twice(client):
    first = make_client(client)
    response = client.post("/api/clients", json={"name": "  rahul   sharma "})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "already_exists"
    assert body["client"]["client_id"] == first["client_id"]
    assert client.get("/api/clients").json()["count"] == 1


def test_an_empty_client_name_is_rejected(client):
    assert client.post("/api/clients", json={"name": "   "}).status_code == 409
    assert client.post("/api/clients", json={}).status_code == 422


def test_update_a_client_field(client):
    created = make_client(client)
    response = client.patch(
        f"/api/clients/{created['client_id']}",
        json={"field": "email", "value": "new@example.com"},
    )
    assert response.status_code == 200
    assert response.json()["client"]["email"] == "new@example.com"


def test_updating_an_unknown_field_is_refused(client):
    created = make_client(client)
    response = client.patch(
        f"/api/clients/{created['client_id']}",
        json={"field": "amount_owed", "value": "0"},
    )
    assert response.status_code == 409


# --- invoices --------------------------------------------------------------


def test_create_an_invoice(client):
    created = make_client(client)
    response = make_invoice(client, created["client_id"], due_date="2026-12-15")

    assert response.status_code == 201
    invoice = response.json()["invoice"]
    assert invoice["invoice_number"] == "FF-0001"
    assert invoice["invoice_status"] == "UNPAID"
    assert invoice["outstanding_display"] == "₹40,000.00"


def test_invoice_numbers_are_assigned_by_the_database(client):
    created = make_client(client)
    first = make_invoice(client, created["client_id"], project="A").json()
    second = make_invoice(client, created["client_id"], project="B").json()
    assert first["invoice"]["invoice_number"] == "FF-0001"
    assert second["invoice"]["invoice_number"] == "FF-0002"


def test_a_duplicate_invoice_is_refused_until_confirmed(client):
    created = make_client(client)
    make_invoice(client, created["client_id"])

    blocked = make_invoice(client, created["client_id"])
    assert blocked.status_code == 409
    assert blocked.json()["error"] == "duplicate_suspected"
    assert client.get("/api/invoices").json()["count"] == 1

    confirmed = make_invoice(client, created["client_id"], allow_duplicate=True)
    assert confirmed.status_code == 201
    assert client.get("/api/invoices").json()["count"] == 2


def test_an_invoice_for_an_unknown_client_is_refused(client):
    assert make_invoice(client, 9999).status_code == 409


def test_a_due_date_before_the_issue_date_is_refused(client):
    created = make_client(client)
    response = make_invoice(
        client, created["client_id"], issue_date="2026-09-05", due_date="2026-09-01"
    )
    assert response.status_code == 409
    assert "before the issue date" in response.json()["detail"]


def test_a_zero_amount_is_rejected_by_validation(client):
    created = make_client(client)
    assert make_invoice(client, created["client_id"], amount_minor=0).status_code == 422


# --- payments --------------------------------------------------------------


def test_record_a_payment_and_get_the_new_balance(client):
    created = make_client(client)
    invoice = make_invoice(client, created["client_id"]).json()["invoice"]

    response = client.post(
        "/api/payments",
        json={
            "invoice_id": invoice["invoice_id"],
            "amount_minor": 1_500_000,
            "method": "UPI",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["payment"]["amount_display"] == "₹15,000.00"
    assert body["invoice"]["invoice_status"] == "PARTIALLY_PAID"
    assert body["invoice"]["outstanding_display"] == "₹25,000.00"


def test_paying_the_balance_marks_the_invoice_paid(client):
    created = make_client(client)
    invoice = make_invoice(client, created["client_id"]).json()["invoice"]

    body = client.post(
        "/api/payments",
        json={"invoice_id": invoice["invoice_id"], "amount_minor": 4_000_000},
    ).json()
    assert body["invoice"]["invoice_status"] == "PAID"
    assert body["invoice"]["outstanding_minor"] == 0


def test_an_overpayment_is_refused_with_the_real_figure(client):
    created = make_client(client)
    invoice = make_invoice(client, created["client_id"]).json()["invoice"]

    response = client.post(
        "/api/payments",
        json={"invoice_id": invoice["invoice_id"], "amount_minor": 5_000_000},
    )
    assert response.status_code == 409
    assert "₹40,000.00" in response.json()["detail"]
    assert client.get("/api/payments").json()["count"] == 0


def test_a_payment_against_an_unknown_invoice_is_refused(client):
    response = client.post(
        "/api/payments", json={"invoice_id": 9999, "amount_minor": 100}
    )
    assert response.status_code == 409


def test_a_duplicate_payment_is_refused_until_confirmed(client):
    created = make_client(client)
    invoice = make_invoice(client, created["client_id"]).json()["invoice"]
    payload = {
        "invoice_id": invoice["invoice_id"],
        "amount_minor": 1_000_000,
        "payment_date": "2026-09-05",
    }

    assert client.post("/api/payments", json=payload).status_code == 201
    blocked = client.post("/api/payments", json=payload)
    assert blocked.status_code == 409
    assert blocked.json()["error"] == "duplicate_suspected"

    confirmed = client.post("/api/payments", json={**payload, "allow_duplicate": True})
    assert confirmed.status_code == 201


# --- reminders -------------------------------------------------------------


def test_draft_and_approve_a_reminder(client):
    created = make_client(client)
    invoice = make_invoice(
        client,
        created["client_id"],
        issue_date=add_days(today_iso(), -30),
        due_date=add_days(today_iso(), -5),
    ).json()["invoice"]

    drafted = client.post("/api/reminders", json={"invoice_id": invoice["invoice_id"]})
    assert drafted.status_code == 201
    reminder = drafted.json()["reminder"]
    assert reminder["reminder_status"] == "DRAFT"
    assert "FF-0001" in reminder["message"]
    assert "5 days overdue" in reminder["message"]

    approved = client.post(f"/api/reminders/{reminder['reminder_id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["reminder"]["reminder_status"] == "APPROVED"


def test_a_reminder_for_a_paid_invoice_is_refused(client):
    created = make_client(client)
    invoice = make_invoice(client, created["client_id"]).json()["invoice"]
    client.post(
        "/api/payments",
        json={"invoice_id": invoice["invoice_id"], "amount_minor": 4_000_000},
    )

    response = client.post("/api/reminders", json={"invoice_id": invoice["invoice_id"]})
    assert response.status_code == 409
    assert "fully paid" in response.json()["detail"]


# --- the whole lifecycle, through HTTP only --------------------------------


def test_the_full_lifecycle_without_any_model(client):
    """Invoice -> partial payment -> receipt -> settle, all through the API.

    This is the proof that the application works with Bedrock unreachable.
    """
    created = client.post(
        "/api/clients", json={"name": "Rahul Sharma", "email": "r@example.com"}
    ).json()["client"]

    amount = client.post("/api/amounts/parse", json={"text": "40k"}).json()
    invoice = client.post(
        "/api/invoices",
        json={
            "client_id": created["client_id"],
            "project": "Website development",
            "amount_minor": amount["amount_minor"],
            "due_date": "2026-12-15",
        },
    ).json()["invoice"]

    first = client.post(
        "/api/payments",
        json={"invoice_id": invoice["invoice_id"], "amount_minor": 1_500_000},
    ).json()
    assert first["invoice"]["outstanding_display"] == "₹25,000.00"

    receipt = client.get(f"/api/payments/{first['payment']['payment_id']}/receipt")
    assert receipt.status_code == 200
    assert receipt.content.startswith(b"%PDF")

    final = client.post(
        "/api/payments",
        json={"invoice_id": invoice["invoice_id"], "amount_minor": 2_500_000},
    ).json()
    assert final["invoice"]["invoice_status"] == "PAID"

    summary = client.get("/api/reports/summary").json()
    assert summary["received_total"][0]["total_minor"] == 4_000_000
    assert summary["outstanding_total"] == []

    pdf = client.get(f"/api/invoices/{invoice['invoice_id']}/pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_writes_never_return_a_server_path(client):
    created = make_client(client)
    response = make_invoice(client, created["client_id"])
    assert "pdf_path" not in response.text
    assert "C:\\" not in response.text
