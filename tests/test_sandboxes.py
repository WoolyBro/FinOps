"""Per-browser demo sandboxes, and the reset button behind them.

What a judge relies on: their changes survive a refresh, nobody else's
changes appear in their copy, and one click restores the sample ledger --
without touching any other judge's copy or the shared ledgers.
"""

from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

from app import workspaces
from app.api.main import create_app
from app.services import agent_service as agent_service_module
from app.services.agent_service import AgentService

A = "sbx-" + "a" * 32
B = "sbx-" + "b" * 32


@pytest.fixture(autouse=True)
def workspace_root(tmp_path, monkeypatch):
    root = tmp_path / "workspaces"
    monkeypatch.setattr(workspaces, "WORKSPACES_ROOT", root)
    monkeypatch.setattr(workspaces, "_initialised", set())
    monkeypatch.setattr(workspaces, "_last_touched", {})
    return root


@pytest.fixture
def api():
    with TestClient(create_app()) as client:
        yield client


def ws(sandbox: str) -> dict:
    return {"X-FF-Workspace": sandbox}


def ff0005(api, sandbox: str) -> dict:
    invoices = api.get("/api/invoices", headers=ws(sandbox)).json()["invoices"]
    return next(i for i in invoices if i["invoice_number"] == "FF-0005")


def pay_rahul(api, sandbox: str, rupees: int = 15_000):
    invoice = ff0005(api, sandbox)
    return api.post(
        "/api/payments",
        json={"invoice_id": invoice["invoice_id"], "amount_minor": rupees * 100},
        headers=ws(sandbox),
    )


# --- a fresh copy per browser ------------------------------------------------------


def test_a_new_browser_gets_the_sample_ledger(api):
    assert api.get("/api/clients", headers=ws(A)).json()["count"] == 6
    invoice = ff0005(api, A)
    assert invoice["client_name"] == "Rahul Sharma"
    assert invoice["outstanding_display"] == "₹40,000.00"
    assert invoice["invoice_status"] == "UNPAID"


def test_changes_persist_across_requests(api):
    """A refresh must not undo a payment -- that would look broken."""
    assert pay_rahul(api, A).status_code == 201
    assert ff0005(api, A)["outstanding_display"] == "₹25,000.00"
    assert ff0005(api, A)["outstanding_display"] == "₹25,000.00"


def test_browsers_never_see_each_others_changes(api):
    pay_rahul(api, A)
    assert ff0005(api, A)["outstanding_display"] == "₹25,000.00"
    assert ff0005(api, B)["outstanding_display"] == "₹40,000.00"


def test_a_malformed_sandbox_id_is_refused(api):
    response = api.get("/api/clients", headers=ws("sbx-../../etc"))
    assert response.status_code == 400
    assert response.json()["error"] == "unknown_workspace"


# --- the reset button ------------------------------------------------------------------


def test_reset_restores_the_sample_ledger(api):
    pay_rahul(api, A)
    meera = next(c for c in api.get("/api/clients", headers=ws(A)).json()["clients"]
                 if c["name"] == "Meera Iyer")
    created = api.post(
        "/api/invoices",
        json={"client_id": meera["client_id"], "project": "Brand guidelines", "amount_minor": 8_500_000},
        headers=ws(A),
    ).json()["invoice"]
    assert created["invoice_number"] == "FF-0011"

    body = api.post("/api/sandbox/reset", headers=ws(A)).json()
    assert body["status"] == "reset"
    assert (body["client_count"], body["invoice_count"], body["payment_count"]) == (6, 10, 4)

    assert ff0005(api, A)["outstanding_display"] == "₹40,000.00"
    again = api.post(
        "/api/invoices",
        json={"client_id": meera["client_id"], "project": "Brand guidelines", "amount_minor": 8_500_000},
        headers=ws(A),
    ).json()["invoice"]
    # Numbering starts over too: the counter is part of the restored ledger.
    assert again["invoice_number"] == "FF-0011"


def test_reset_touches_only_the_browser_that_asked(api):
    pay_rahul(api, A)
    pay_rahul(api, B)
    api.post("/api/sandbox/reset", headers=ws(A))
    assert ff0005(api, A)["outstanding_display"] == "₹40,000.00"
    assert ff0005(api, B)["outstanding_display"] == "₹25,000.00"


def test_reset_removes_documents_generated_since(api, workspace_root):
    invoice = ff0005(api, A)
    assert api.get(f"/api/invoices/{invoice['invoice_id']}/pdf", headers=ws(A)).status_code == 200
    assert list((workspace_root / A / "invoices").glob("*.pdf"))

    api.post("/api/sandbox/reset", headers=ws(A))
    assert not list((workspace_root / A / "invoices").glob("*.pdf"))


def test_reset_is_refused_without_a_sandbox(api):
    response = api.post("/api/sandbox/reset")
    assert response.status_code == 400
    assert response.json()["error"] == "not_a_sandbox"


def test_the_shared_ledgers_can_never_be_reset(api):
    response = api.post("/api/sandbox/reset", headers=ws("demo"))
    assert response.status_code == 400
    assert response.json()["error"] == "not_a_sandbox"


def test_reset_forgets_conversations_about_that_sandbox_only(monkeypatch):
    monkeypatch.setattr(agent_service_module, "build_agent", lambda tracer, **_: object())
    service = AgentService()
    with workspaces.using(A):
        in_a = service.session(None)
    with workspaces.using(B):
        in_b = service.session(None)

    assert service.reset_workspace(A) == 1
    with workspaces.using(A):
        assert service.session(in_a.session_id) is not in_a
    with workspaces.using(B):
        assert service.session(in_b.session_id) is in_b


# --- housekeeping ----------------------------------------------------------------------


def test_expired_sandboxes_are_removed(api, workspace_root, monkeypatch):
    monkeypatch.setenv("FF_SANDBOX_TTL_HOURS", "1")
    api.get("/api/clients", headers=ws(A))
    old = time.time() - 2 * 3600
    os.utime(workspace_root / A / "freelanceflow.db", (old, old))

    api.get("/api/clients", headers=ws(B))  # creating B prunes the stale A
    assert not (workspace_root / A).exists()
    assert (workspace_root / B).exists()


def test_the_number_of_sandboxes_is_capped(api, workspace_root, monkeypatch):
    monkeypatch.setenv("FF_SANDBOX_MAX", "2")
    ids = [f"sbx-{str(n) * 32}" for n in range(1, 4)]
    for n, sandbox in enumerate(ids):
        api.get("/api/clients", headers=ws(sandbox))
        stamp = time.time() - (10 - n) * 60
        os.utime(workspace_root / sandbox / "freelanceflow.db", (stamp, stamp))

    remaining = sorted(p.name for p in workspace_root.glob("sbx-*"))
    assert remaining == sorted(ids[1:])  # the least recently used went


def test_an_expired_sandbox_id_comes_back_as_a_fresh_copy(api, workspace_root):
    pay_rahul(api, A)
    import shutil

    shutil.rmtree(workspace_root / A)
    assert ff0005(api, A)["outstanding_display"] == "₹40,000.00"


def test_the_template_is_rebuilt_on_a_new_day(workspace_root, monkeypatch):
    monkeypatch.setattr(workspaces, "today_iso", lambda: "2026-09-01")
    workspaces._template_db()
    assert (workspace_root / "_template" / "seeded_on").read_text() == "2026-09-01"

    monkeypatch.setattr(workspaces, "today_iso", lambda: "2026-09-02")
    workspaces._template_db()
    assert (workspace_root / "_template" / "seeded_on").read_text() == "2026-09-02"
