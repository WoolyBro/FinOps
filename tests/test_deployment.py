"""What a hosted demo depends on: one URL, a ledger that is never empty, a fast agent.

A judge opens a link. The API must serve the dashboard itself, a freshly
restarted instance must come back with the sample ledger, and the model must
not spend a minute deliberating before every tool call.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import model_provider
from app.api.main import create_app
from app.seed import seed_if_empty


# --- one URL ---------------------------------------------------------------------


@pytest.fixture
def built_dashboard(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>FreelanceFlow</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    monkeypatch.setenv("FF_STATIC_DIR", str(dist))
    return dist


def test_the_api_serves_the_built_dashboard(built_dashboard):
    with TestClient(create_app()) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "FreelanceFlow" in page.text
        assert client.get("/assets/app.js").status_code == 200


def test_the_api_still_wins_over_the_dashboard(built_dashboard):
    """The static mount is last: /api and /docs are never shadowed by it."""
    with TestClient(create_app()) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/openapi.json").status_code == 200
        missing = client.get("/api/no-such-endpoint")
        assert missing.status_code == 404
        assert missing.json()["error"] == "not_found"


def test_without_a_build_nothing_is_mounted(tmp_path, monkeypatch):
    monkeypatch.setenv("FF_STATIC_DIR", str(tmp_path / "not-built"))
    with TestClient(create_app()) as client:
        assert client.get("/").status_code == 404
        assert client.get("/api/health").status_code == 200


# --- a ledger that is never empty ---------------------------------------------------------


def test_startup_seeds_an_empty_ledger_when_asked(monkeypatch):
    monkeypatch.setenv("FF_SEED_DEMO", "true")
    with TestClient(create_app()) as client:
        clients = client.get("/api/clients").json()
        assert clients["count"] == 6
        rahul = client.get("/api/invoices").json()["invoices"]
        unpaid = [i for i in rahul if i["invoice_number"] == "FF-0005"][0]
        # The walkthrough depends on this invoice being untouched.
        assert unpaid["client_name"] == "Rahul Sharma"
        assert unpaid["outstanding_display"] == "₹40,000.00"


def test_startup_does_not_seed_unless_asked():
    with TestClient(create_app()) as client:
        assert client.get("/api/clients").json()["count"] == 0


def test_a_ledger_with_data_is_never_reseeded():
    assert seed_if_empty() == {"clients": 6, "invoices": 10}
    assert seed_if_empty() is None


# --- a fast agent ---------------------------------------------------------------------------


def test_gemini_thinks_briefly_by_default(monkeypatch):
    monkeypatch.delenv("FF_GEMINI_THINKING", raising=False)
    assert model_provider.gemini_params() == {
        "temperature": 0.2,
        "thinking_config": {"thinking_level": "LOW"},
    }


@pytest.mark.parametrize("level", ["minimal", "medium", "high"])
def test_the_thinking_level_is_configurable(monkeypatch, level):
    monkeypatch.setenv("FF_GEMINI_THINKING", level)
    assert model_provider.gemini_params()["thinking_config"] == {"thinking_level": level.upper()}


def test_thinking_can_be_left_to_the_model(monkeypatch):
    """For a model without a thinking setting, send none rather than fail."""
    monkeypatch.setenv("FF_GEMINI_THINKING", "off")
    assert "thinking_config" not in model_provider.gemini_params()


def test_the_thinking_setting_reaches_the_request(monkeypatch):
    monkeypatch.setenv("FF_MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test-key-not-real")
    model = model_provider.build_model()
    config = model._format_request_config(None, "system", model.config.get("params"))
    assert config.thinking_config.thinking_level.name == "LOW"
