"""Two ledgers behind one API, and nothing leaking between them.

The property that matters: whatever a request -- or the agent acting for it --
writes lands in the workspace that request named, and only there. The agent
test is the important one, because Strands runs tools on its own worker thread
and a context variable that failed to follow would silently write into the
default database instead.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from strands import Agent

from app import workspaces
from app.agent import TOOLS, system_prompt
from app.api.main import create_app
from app.services import agent_service as agent_service_module
from app.services.agent_service import AgentService
from app.tools.clients import list_clients
from app.tracing import ToolTracer
from tests.scripted_model import ScriptedModel


@pytest.fixture(autouse=True)
def workspace_root(tmp_path, monkeypatch):
    root = tmp_path / "workspaces"
    monkeypatch.setattr(workspaces, "WORKSPACES_ROOT", root)
    monkeypatch.setattr(workspaces, "_initialised", set())
    return root


@pytest.fixture
def api():
    with TestClient(create_app()) as client:
        yield client


def in_ws(name: str) -> dict:
    return {"X-FF-Workspace": name}


def client_names(api, workspace: str | None) -> set[str]:
    headers = in_ws(workspace) if workspace else {}
    body = api.get("/api/clients", headers=headers).json()
    return {c["name"] for c in body["clients"]}


# --- isolation through the API ---------------------------------------------------


def test_a_write_lands_only_in_the_workspace_that_asked(api):
    created = api.post("/api/clients", json={"name": "Meera Iyer"}, headers=in_ws("fresh"))
    assert created.status_code == 201

    assert client_names(api, "fresh") == {"Meera Iyer"}
    assert client_names(api, "demo") == set()
    assert client_names(api, None) == set()  # the default database is untouched


def test_each_workspace_is_its_own_file(api, workspace_root):
    api.post("/api/clients", json={"name": "Meera Iyer"}, headers=in_ws("fresh"))
    assert (workspace_root / "fresh" / "freelanceflow.db").exists()
    assert (workspace_root / "demo" / "freelanceflow.db").exists() is False


def test_invoice_numbers_start_over_in_a_new_workspace(api):
    """Each ledger has its own gapless numbering, not a shared counter."""
    for ws in ("demo", "fresh"):
        client = api.post("/api/clients", json={"name": "Rahul Sharma"}, headers=in_ws(ws))
        client_id = client.json()["client"]["client_id"]
        invoice = api.post(
            "/api/invoices",
            json={"client_id": client_id, "project": "Website", "amount_minor": 4_000_000},
            headers=in_ws(ws),
        )
        assert invoice.json()["invoice"]["invoice_number"] == "FF-0001"


def test_an_unknown_workspace_is_refused_not_defaulted(api):
    response = api.get("/api/clients", headers=in_ws("someone-elses"))
    assert response.status_code == 400
    assert response.json()["error"] == "unknown_workspace"


def test_the_query_parameter_works_for_plain_links(api):
    """A PDF href cannot carry a header, so ?workspace= must select too."""
    api.post("/api/clients", json={"name": "Meera Iyer"}, headers=in_ws("fresh"))
    body = api.get("/api/clients?workspace=fresh").json()
    assert {c["name"] for c in body["clients"]} == {"Meera Iyer"}


def test_documents_are_written_and_served_per_workspace(api, workspace_root):
    client = api.post("/api/clients", json={"name": "Rahul"}, headers=in_ws("fresh"))
    invoice = api.post(
        "/api/invoices",
        json={
            "client_id": client.json()["client"]["client_id"],
            "project": "Website",
            "amount_minor": 4_000_000,
        },
        headers=in_ws("fresh"),
    ).json()["invoice"]

    pdf = api.get(f"/api/invoices/{invoice['invoice_id']}/pdf?workspace=fresh")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert list((workspace_root / "fresh" / "invoices").glob("*.pdf"))

    # The same id in the other ledger is a different (here: missing) invoice.
    assert api.get(f"/api/invoices/{invoice['invoice_id']}/pdf?workspace=demo").status_code == 404


# --- the chooser ----------------------------------------------------------------------


def test_the_chooser_reports_what_each_ledger_holds(api):
    api.post("/api/clients", json={"name": "Meera Iyer"}, headers=in_ws("fresh"))
    body = api.get("/api/workspaces").json()
    by_id = {w["id"]: w for w in body["workspaces"]}

    assert set(by_id) == {"demo", "fresh"}
    assert by_id["fresh"]["client_count"] == 1
    assert by_id["demo"]["client_count"] == 0
    assert by_id["demo"]["name"] == "Existing dashboard"
    assert by_id["fresh"]["name"] == "New dashboard"


# --- the agent --------------------------------------------------------------------------


def test_the_agents_tool_calls_land_in_the_requests_workspace():
    """Strands runs tools off-thread; the workspace must follow them there."""
    agent = Agent(
        model=ScriptedModel([[("create_client", {"name": "Meera Iyer"})], "Added Meera."]),
        tools=TOOLS,
        system_prompt=system_prompt(),
        hooks=[ToolTracer()],
    )

    with workspaces.using("fresh"):
        agent("Add a client called Meera Iyer")
        assert [c["name"] for c in list_clients()["clients"]] == ["Meera Iyer"]

    with workspaces.using("demo"):
        assert list_clients()["clients"] == []
    assert list_clients()["clients"] == []


def test_a_conversation_never_continues_in_another_workspace(monkeypatch):
    monkeypatch.setattr(agent_service_module, "build_agent", lambda tracer, **_: object())
    service = AgentService()

    with workspaces.using("fresh"):
        first = service.session(None)
        assert service.session(first.session_id) is first  # same ledger: continues

    with workspaces.using("demo"):
        other = service.session(first.session_id)
        assert other is not first
        assert other.workspace == "demo"
