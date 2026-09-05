"""Phase 8: the checks that run before any live model call.

All credential-free. The property that matters most here is the refusal: a run
that asks for Bedrock must never quietly execute against Ollama, because a pass
from the wrong provider proves nothing about the one being validated.
"""

from __future__ import annotations

import pytest

from app import model_provider, preflight as preflight_module
from app.preflight import diagnose_failure, preflight


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in (
        "FF_MODEL_PROVIDER",
        "FF_MODEL_ID",
        "ANTHROPIC_API_KEY",
        "OLLAMA_HOST",
        "FF_AWS_REGION",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
    ):
        monkeypatch.delenv(var, raising=False)


def no_aws(monkeypatch):
    monkeypatch.setattr(
        preflight_module, "aws_credentials_detail", lambda: (False, "none found")
    )
    monkeypatch.setattr(model_provider, "aws_credentials_available", lambda: False)


def with_aws(monkeypatch):
    monkeypatch.setattr(
        preflight_module, "aws_credentials_detail", lambda: (True, "resolved via env")
    )
    monkeypatch.setattr(model_provider, "aws_credentials_available", lambda: True)


def with_ollama(monkeypatch):
    monkeypatch.setattr(model_provider, "ollama_available", lambda timeout=0.5: True)


# --- the refusal rule -------------------------------------------------------


def test_bedrock_run_refuses_to_fall_back_to_ollama(monkeypatch):
    """The property this whole phase depends on."""
    no_aws(monkeypatch)
    with_ollama(monkeypatch)

    report = preflight(require_provider="bedrock")

    assert report.ok is False
    provider_check = next(c for c in report.checks if c.name == "provider resolves")
    assert provider_check.passed is False
    assert "requires 'bedrock'" in provider_check.detail


def test_an_explicit_ollama_run_is_allowed(monkeypatch):
    """Developing without AWS is fine -- it just must not be mistaken for AWS."""
    no_aws(monkeypatch)
    monkeypatch.setenv("FF_MODEL_PROVIDER", "ollama")

    report = preflight(require_provider="ollama")
    assert report.ok is True
    assert report.provider == "ollama"


def test_ollama_runs_do_not_demand_aws_credentials(monkeypatch):
    no_aws(monkeypatch)
    monkeypatch.setenv("FF_MODEL_PROVIDER", "ollama")

    names = {c.name for c in preflight(require_provider="ollama").checks}
    assert "aws credentials" not in names
    assert "aws region" not in names


# --- the individual prerequisites ------------------------------------------


def test_missing_credentials_are_named_precisely(monkeypatch):
    no_aws(monkeypatch)
    report = preflight(require_provider="bedrock")

    check = next(c for c in report.checks if c.name == "aws credentials")
    assert check.passed is False
    assert "aws configure" in check.fix
    # The fix must never suggest putting credentials in the repository.
    assert "Never put credentials in .env" in check.fix


def test_missing_region_is_named_precisely(monkeypatch):
    with_aws(monkeypatch)
    report = preflight(require_provider="bedrock")

    check = next(c for c in report.checks if c.name == "aws region")
    assert check.passed is False
    assert "FF_AWS_REGION" in check.fix


def test_everything_present_passes(monkeypatch):
    with_aws(monkeypatch)
    monkeypatch.setenv("FF_AWS_REGION", "ap-south-1")

    report = preflight(require_provider="bedrock")
    assert report.ok is True, report.format()
    assert report.provider == "bedrock"
    assert report.region == "ap-south-1"
    assert report.model_id == model_provider.BEDROCK_MODEL_ID


def test_an_anthropic_key_never_makes_a_run_pass(monkeypatch):
    no_aws(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-ignored")

    report = preflight(require_provider="bedrock")
    assert report.ok is False

    check = next(c for c in report.checks if c.name == "anthropic api not used")
    assert check.passed is True
    assert "never read" in check.detail


def test_model_access_is_reported_as_unconfirmed(monkeypatch):
    """Confirming it would cost either credits or an extra IAM permission."""
    with_aws(monkeypatch)
    monkeypatch.setenv("FF_AWS_REGION", "ap-south-1")

    check = next(
        c for c in preflight(require_provider="bedrock").checks
        if c.name == "model access"
    )
    assert "cannot be confirmed without a call" in check.detail


def test_report_formats_failures_with_their_fixes(monkeypatch):
    no_aws(monkeypatch)
    text = preflight(require_provider="bedrock").format()
    assert "[FAIL]" in text
    assert "aws configure" in text


# --- turning AWS errors into something actionable ---------------------------


class FakeAccessDenied(Exception):
    pass


def test_access_denied_points_at_model_access():
    message = diagnose_failure(
        FakeAccessDenied("AccessDeniedException: not authorized"),
        "global.anthropic.claude-sonnet-4-6",
        "ap-south-1",
    )
    assert "Model access" in message
    assert "per region" in message
    assert "ap-south-1" in message


def test_validation_error_points_at_the_model_id():
    message = diagnose_failure(
        Exception("ValidationException: invalid model identifier"),
        "global.anthropic.claude-sonnet-4-6",
        "eu-west-1",
    )
    assert "does not exist in" in message
    assert "FF_MODEL_ID" in message


def test_expired_credentials_are_distinguished_from_missing_access():
    message = diagnose_failure(
        Exception("ExpiredToken: the security token included has expired"),
        "m",
        "ap-south-1",
    )
    assert "not valid" in message
    assert "SSO" in message


def test_throttling_is_not_reported_as_a_permissions_problem():
    message = diagnose_failure(Exception("ThrottlingException"), "m", "ap-south-1")
    assert "throttled" in message
    assert "Model access" not in message


def test_an_unrecognised_error_is_passed_through_intact():
    message = diagnose_failure(ValueError("something else entirely"), "m", "r")
    assert "ValueError" in message
    assert "something else entirely" in message


# --- the live check refuses without spending -------------------------------


def test_live_check_exits_two_without_calling_a_model(monkeypatch, capsys):
    """Exit 2 and no model call, so a missing prerequisite costs nothing."""
    from app import live_check

    no_aws(monkeypatch)

    def explode(*args, **kwargs):
        raise AssertionError("a model must not be constructed during preflight")

    monkeypatch.setattr("app.agent.build_agent", explode)

    assert live_check.main(["--scenario", "balance"]) == 2
    assert "Refusing to run" in capsys.readouterr().err


def test_live_check_preflight_flag_stops_before_the_model(monkeypatch, capsys):
    from app import live_check

    with_aws(monkeypatch)
    monkeypatch.setenv("FF_AWS_REGION", "ap-south-1")

    def explode(*args, **kwargs):
        raise AssertionError("--preflight must not call a model")

    monkeypatch.setattr("app.agent.build_agent", explode)

    assert live_check.main(["--preflight"]) == 0
    assert "No model was called" in capsys.readouterr().out
