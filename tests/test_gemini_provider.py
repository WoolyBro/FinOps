"""Gemini as a provider: selected correctly, keyed correctly, and never called here.

Every test in this file runs offline. The last one builds the exact request
Strands would send for all 22 tools and lets the google-genai types validate
it locally -- a schema Gemini cannot accept fails here, for free, instead of on
the first live turn.
"""

from __future__ import annotations

import pytest

from app import model_provider
from app.agent import TOOLS, system_prompt
from app.model_provider import ModelNotConfigured, provider_status, resolve_provider
from app.preflight import preflight
from app.services.agent_service import explain_failure

FAKE_KEY = "AIza-test-key-not-real"


def with_aws(monkeypatch):
    monkeypatch.setattr(model_provider, "aws_credentials_available", lambda: True)


def no_aws(monkeypatch):
    monkeypatch.setattr(model_provider, "aws_credentials_available", lambda: False)


def no_ollama(monkeypatch):
    monkeypatch.setattr(model_provider, "ollama_available", lambda timeout=0.5: False)


# --- selection ----------------------------------------------------------------


def test_gemini_is_a_supported_provider():
    assert "gemini" in model_provider.PROVIDERS
    assert "anthropic" not in model_provider.PROVIDERS
    assert "openai" not in model_provider.PROVIDERS


def test_a_gemini_key_outranks_aws_credentials_in_auto_mode(monkeypatch):
    """AWS credentials on a machine say nothing about Bedrock model access."""
    with_aws(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    assert resolve_provider() == "gemini"


def test_without_a_key_auto_mode_is_unchanged(monkeypatch):
    with_aws(monkeypatch)
    assert resolve_provider() == "bedrock"


def test_google_api_key_is_accepted_too(monkeypatch):
    no_aws(monkeypatch)
    no_ollama(monkeypatch)
    monkeypatch.setenv("GOOGLE_API_KEY", FAKE_KEY)
    assert resolve_provider() == "gemini"


def test_a_blank_key_does_not_count(monkeypatch):
    no_aws(monkeypatch)
    no_ollama(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    with pytest.raises(ModelNotConfigured):
        resolve_provider()


# --- status: honest, and never carrying the key --------------------------------


def test_explicit_gemini_without_a_key_says_where_to_get_one(monkeypatch):
    monkeypatch.setenv("FF_MODEL_PROVIDER", "gemini")
    status = provider_status()
    assert status["available"] is False
    assert status["provider"] == "gemini"
    assert "aistudio.google.com/apikey" in status["detail"]


def test_status_with_a_key(monkeypatch):
    monkeypatch.setenv("FF_MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    status = provider_status()
    assert status == {
        "available": True,
        "provider": "gemini",
        "model_id": "gemini-3.5-flash-lite",
        "region": None,
        "detail": None,
    }


def test_the_key_never_appears_in_status(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    assert FAKE_KEY not in repr(provider_status())


def test_model_id_can_be_overridden(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("FF_MODEL_ID", "gemini-2.5-pro")
    assert provider_status()["model_id"] == "gemini-2.5-pro"


# --- building the model ---------------------------------------------------------


def test_builds_a_gemini_model_with_the_key(monkeypatch):
    from strands.models.gemini import GeminiModel

    monkeypatch.setenv("FF_MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    model = model_provider.build_model()
    assert isinstance(model, GeminiModel)
    assert model.get_config()["model_id"] == "gemini-3.5-flash-lite"
    assert model.client_args["api_key"] == FAKE_KEY


def test_building_without_a_key_fails_clearly(monkeypatch):
    monkeypatch.setenv("FF_MODEL_PROVIDER", "gemini")
    with pytest.raises(ModelNotConfigured, match="GEMINI_API_KEY"):
        model_provider.build_model()


def test_every_tool_schema_is_acceptable_to_gemini(monkeypatch):
    """Format the real request for all 22 tools, locally, with no network."""
    monkeypatch.setenv("FF_MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    model = model_provider.build_model()

    specs = [tool.tool_spec for tool in TOOLS]
    config = model._format_request_config(specs, system_prompt(), None)

    declared = {fn.name for tool in config.tools for fn in (tool.function_declarations or [])}
    assert declared == {tool.tool_name for tool in TOOLS}
    assert len(declared) == 22


# --- preflight and failures -------------------------------------------------------


def test_preflight_requires_the_key_for_a_gemini_run(monkeypatch):
    report = preflight(require_provider="gemini")
    check = next(c for c in report.checks if c.name == "gemini api key")
    assert check.passed is False
    assert "aistudio" in check.fix
    assert "aws credentials" not in {c.name for c in report.checks}


def test_preflight_passes_with_a_key(monkeypatch):
    monkeypatch.setenv("FF_MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    report = preflight(require_provider="gemini")
    assert report.ok, report.format()
    assert report.model_id == "gemini-3.5-flash-lite"


GEMINI = {"provider": "gemini", "model_id": "gemini-3.5-flash-lite"}


def test_a_rejected_key_is_named():
    detail = explain_failure(Exception("400 INVALID_ARGUMENT. API key not valid. API_KEY_INVALID"), GEMINI)
    assert "rejected the Gemini API key" in detail


def test_a_free_tier_limit_is_named():
    detail = explain_failure(Exception("429 RESOURCE_EXHAUSTED. Quota exceeded"), GEMINI)
    assert "free-tier limit" in detail


def test_a_retired_model_is_named_as_retired():
    """Google retires models for new keys; say that, not 'no such model'."""
    detail = explain_failure(
        Exception(
            "404 Not Found. This model models/gemini-2.5-flash is no longer "
            "available to new users. NOT_FOUND"
        ),
        {"provider": "gemini", "model_id": "gemini-2.5-flash"},
    )
    assert "has retired gemini-2.5-flash" in detail
    assert "FF_MODEL_ID" in detail


def test_an_unknown_gemini_error_does_not_leak_its_text():
    detail = explain_failure(RuntimeError("secret-project-id-123 at C:\\keys"), GEMINI)
    assert "secret-project-id-123" not in detail
