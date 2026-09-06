"""Security properties, asserted rather than assumed.

Each test here corresponds to a real finding from the audit, so a regression
fails the suite rather than quietly reopening the hole.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import InsecureCorsConfiguration, cors_origins, create_app
from app.security import (
    UnsafePath,
    is_within,
    redact_paths,
    resolve_document,
    safe_detail,
    scrub,
)
from app.tools.clients import create_client
from app.tools.invoices import create_invoice
from app.tools.payments import record_payment


# --- path containment -------------------------------------------------------


def test_a_path_outside_the_document_directory_is_refused(tmp_path):
    allowed = tmp_path / "invoices"
    allowed.mkdir()
    outside = tmp_path / "secrets.txt"
    outside.write_text("not yours")

    with pytest.raises(UnsafePath):
        resolve_document(outside, [allowed])


def test_traversal_out_of_the_document_directory_is_refused(tmp_path):
    allowed = tmp_path / "invoices"
    allowed.mkdir()
    (tmp_path / "secrets.txt").write_text("not yours")

    with pytest.raises(UnsafePath):
        resolve_document(allowed / ".." / "secrets.txt", [allowed])


def test_a_file_inside_the_directory_is_served(tmp_path):
    allowed = tmp_path / "invoices"
    allowed.mkdir()
    document = allowed / "FF-0001.pdf"
    document.write_bytes(b"%PDF-1.4")

    assert resolve_document(document, [allowed]) == document.resolve()


def test_a_directory_is_not_a_document(tmp_path):
    allowed = tmp_path / "invoices"
    allowed.mkdir()
    with pytest.raises(UnsafePath):
        resolve_document(allowed, [allowed])


def test_is_within_rejects_a_sibling_with_a_shared_prefix(tmp_path):
    """`/data/invoices-old` is not inside `/data/invoices`."""
    (tmp_path / "invoices").mkdir()
    (tmp_path / "invoices-old").mkdir()
    assert not is_within(tmp_path / "invoices-old" / "x.pdf", tmp_path / "invoices")


# --- server paths never reach a client --------------------------------------


def test_scrub_replaces_path_fields_with_availability():
    cleaned = scrub({"invoice_number": "FF-0001", "pdf_path": "C:\\srv\\FF-0001.pdf"})
    assert cleaned == {"invoice_number": "FF-0001", "pdf_available": True}
    assert "pdf_path" not in cleaned


def test_scrub_reports_a_missing_document_as_unavailable():
    assert scrub({"receipt_path": None}) == {"receipt_available": False}


def test_scrub_recurses_through_lists_and_nested_dicts():
    cleaned = scrub({"invoices": [{"pdf_path": "/srv/a.pdf"}, {"pdf_path": None}]})
    assert cleaned["invoices"] == [{"pdf_available": True}, {"pdf_available": False}]


@pytest.mark.parametrize(
    "text",
    [
        "failed to open C:\\Users\\Ayush Mondal\\Desktop\\data\\ff.db",
        "permission denied: /home/ayush/freelanceflow/data/ff.db",
        "cannot write /var/lib/freelanceflow/invoices/FF-0001.pdf",
    ],
)
def test_absolute_paths_are_redacted_from_free_text(text):
    redacted = redact_paths(text)
    assert "<path>" in redacted
    for fragment in ("Users", "home/ayush", "/var/lib"):
        assert fragment not in redacted


def test_safe_detail_drops_a_message_that_is_mostly_a_path():
    detail = safe_detail(
        OSError("C:\\Users\\Ayush Mondal\\data\\ff.db"), "The database is unavailable."
    )
    assert detail == "The database is unavailable."


def test_safe_detail_keeps_a_message_with_nothing_sensitive():
    assert safe_detail(ValueError("due date is before issue date"), "fallback") == (
        "due date is before issue date"
    )


# --- the API, end to end ----------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.pdf_generator.INVOICES_DIR", tmp_path / "invoices")
    monkeypatch.setattr("app.pdf_generator.RECEIPTS_DIR", tmp_path / "receipts")
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def seeded():
    rahul = create_client(name="Rahul Sharma")["client"]
    invoice = create_invoice(
        client_id=rahul["client_id"],
        project="Website development",
        amount_minor=4_000_000,
    )["invoice"]
    payment = record_payment(
        invoice_id=invoice["invoice_id"], amount_minor=1_500_000
    )["payment"]
    return {"invoice": invoice, "payment": payment}


@pytest.mark.parametrize(
    "path",
    [
        "/api/invoices",
        "/api/payments",
        "/api/clients",
        "/api/reports/overdue",
        "/api/reports/outstanding",
    ],
)
def test_no_endpoint_returns_a_server_filesystem_path(client, seeded, path):
    """The operator's directory layout -- and their name -- is not public."""
    body = client.get(path).text
    assert "pdf_path" not in body
    assert "receipt_path" not in body
    assert "C:\\\\" not in body and "C:\\" not in body
    assert "/home/" not in body


def test_invoice_detail_reports_availability_not_location(client, seeded):
    invoice = client.get(f"/api/invoices/{seeded['invoice']['invoice_id']}").json()
    assert "pdf_path" not in invoice["invoice"]
    assert invoice["invoice"]["pdf_available"] is False


def test_the_document_itself_is_still_served(client, seeded):
    """Hiding the path must not break downloading the file."""
    response = client.get(f"/api/invoices/{seeded['invoice']['invoice_id']}/pdf")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")


def test_a_tampered_stored_path_is_not_served(client, seeded, tmp_path):
    """If the pdf_path column ever holds something outside our directories."""
    from app.database import get_db

    secret = tmp_path / "id_rsa"
    secret.write_text("PRIVATE KEY")

    with get_db() as conn:
        conn.execute(
            "UPDATE invoices SET pdf_path = ? WHERE id = ?",
            (str(secret), seeded["invoice"]["invoice_id"]),
        )

    response = client.get(f"/api/invoices/{seeded['invoice']['invoice_id']}/pdf")
    assert response.status_code == 200
    # It regenerated a real invoice rather than serving the file it was pointed at.
    assert response.content.startswith(b"%PDF")
    assert b"PRIVATE KEY" not in response.content


# --- CORS -------------------------------------------------------------------


def test_a_wildcard_origin_is_refused(monkeypatch):
    """`*` with credentials would let any site read a user's billing data."""
    monkeypatch.setenv("FF_CORS_ORIGINS", "*")
    with pytest.raises(InsecureCorsConfiguration):
        cors_origins()


def test_a_wildcard_hidden_in_a_list_is_refused(monkeypatch):
    monkeypatch.setenv("FF_CORS_ORIGINS", "https://app.example.com,*")
    with pytest.raises(InsecureCorsConfiguration):
        cors_origins()


def test_explicit_origins_are_accepted(monkeypatch):
    monkeypatch.setenv(
        "FF_CORS_ORIGINS", "https://app.example.com, https://admin.example.com"
    )
    assert cors_origins() == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


# --- SQL --------------------------------------------------------------------


def test_no_sql_statement_is_built_by_string_formatting():
    """Parameterised everywhere; no statement assembled from a variable."""
    from app.tools import clients

    source = Path(clients.__file__).read_text(encoding="utf-8")
    assert 'execute(f"' not in source
    assert "SET {field}" not in source


def test_update_client_still_rejects_an_unknown_field():
    created = create_client(name="Priya")["client"]
    from app.tools.clients import update_client

    result = update_client(
        client_id=created["client_id"], field="id = 1; DROP TABLE clients--", value="x"
    )
    assert result["status"] == "error"


# --- the session store is bounded -------------------------------------------


def _fake_session(service, session_id, last_used):
    from app.services.agent_service import Session

    service._sessions[session_id] = Session(
        session_id=session_id,
        agent=object(),
        tracer=None,
        created_at="",
        last_used=last_used,
    )


def test_expired_sessions_are_evicted():
    from app.services.agent_service import SESSION_TTL, AgentService

    service = AgentService()
    now = datetime.now(timezone.utc)
    _fake_session(service, "a" * 32, now - SESSION_TTL - timedelta(minutes=1))
    _fake_session(service, "b" * 32, now)

    service._evict()

    assert "a" * 32 not in service._sessions
    assert "b" * 32 in service._sessions


def test_the_session_store_is_capped():
    """An unbounded store is a memory leak with a network-facing trigger."""
    from app.services.agent_service import MAX_SESSIONS, AgentService

    service = AgentService()
    now = datetime.now(timezone.utc)
    for index in range(MAX_SESSIONS + 10):
        _fake_session(service, f"{index:032x}", now + timedelta(seconds=index))

    service._evict()
    assert len(service._sessions) < MAX_SESSIONS


def test_a_client_supplied_session_id_cannot_name_a_new_session():
    """Ids are issued by the server, never chosen by the caller."""
    from app.services.agent_service import AgentService

    service = AgentService()
    captured = {}

    def fake_new_session():
        from app.services.agent_service import Session

        session = Session(
            session_id="deadbeef" * 4,
            agent=object(),
            tracer=None,
            created_at="",
            last_used=datetime.now(timezone.utc),
        )
        captured["issued"] = session.session_id
        return session

    service._new_session = fake_new_session
    session = service.session("../../etc/passwd")

    assert session.session_id == captured["issued"]
    assert session.session_id != "../../etc/passwd"


def test_an_unknown_but_well_formed_id_does_not_resurrect_a_session():
    from app.services.agent_service import AgentService

    service = AgentService()

    def fake_new_session():
        from app.services.agent_service import Session

        return Session(
            session_id="f" * 32,
            agent=object(),
            tracer=None,
            created_at="",
            last_used=datetime.now(timezone.utc),
        )

    service._new_session = fake_new_session
    session = service.session("a" * 32)
    assert session.session_id == "f" * 32


# --- nothing sensitive is committed -----------------------------------------


def test_the_repository_tracks_no_secrets():
    import subprocess

    root = Path(__file__).resolve().parent.parent
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.splitlines()

    for name in tracked:
        lowered = name.lower()
        assert not lowered.endswith(".pem")
        assert not lowered.endswith(".key")
        assert ".aws/" not in lowered
        # .env.example is a template with no values, and is meant to be tracked.
        assert not (lowered.endswith(".env") or "/.env" in lowered)


def test_the_agentcore_error_response_carries_no_paths(monkeypatch):
    from app import agentcore_app

    monkeypatch.setattr(
        agentcore_app,
        "readiness",
        lambda: {
            "ready": False,
            "model": {"available": False, "detail": None},
            "region": {"detail": None},
            "database": {
                "ok": False,
                "detail": "unable to open C:\\Users\\Ayush Mondal\\data\\ff.db",
            },
            "warnings": [],
        },
    )

    serialised = json.dumps(agentcore_app.invoke({"prompt": "hello"}))
    assert "Ayush Mondal" not in serialised
    assert "C:\\" not in serialised
    assert "<path>" in serialised
