"""Phase 7: the AgentCore Runtime entry point.

These run without AWS credentials and without spending anything. What they
check is that the container satisfies the AgentCore HTTP service contract and
refuses honestly when it cannot serve -- not that Bedrock works, which is a
live test.

Contract assertions here were taken from the AWS documentation, not from
memory: host 0.0.0.0, port 8080, POST /invocations, GET /ping returning
{"status": "Healthy"}, ARM64 container, and the
X-Amzn-Bedrock-AgentCore-Runtime-Session-Id header for microVM stickiness.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from app import agentcore_app
from app.aws_config import (
    AGENTCORE_REGIONS,
    RegionNotConfigured,
    region_status,
    require_region,
    resolve_region,
)
from app.observability import JsonFormatter, tool_call_summary


@pytest.fixture(autouse=True)
def clean_region(monkeypatch):
    for var in ("FF_AWS_REGION", "AWS_REGION", "AWS_DEFAULT_REGION"):
        monkeypatch.delenv(var, raising=False)


# --- region configuration ---------------------------------------------------


def test_no_region_is_not_guessed(monkeypatch):
    """The old code defaulted to us-east-1. Guessing hides a real mistake."""
    assert resolve_region() is None
    with pytest.raises(RegionNotConfigured) as exc:
        require_region()
    assert "FF_AWS_REGION" in str(exc.value)


def test_ff_aws_region_takes_precedence(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("FF_AWS_REGION", "ap-south-1")
    assert require_region() == "ap-south-1"


def test_falls_back_through_the_conventional_variables(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    assert require_region() == "eu-west-1"
    monkeypatch.setenv("AWS_REGION", "us-east-2")
    assert require_region() == "us-east-2"


def test_malformed_region_is_rejected(monkeypatch):
    monkeypatch.setenv("FF_AWS_REGION", "not-a-region")
    with pytest.raises(RegionNotConfigured):
        require_region()


def test_region_status_reports_rather_than_raises():
    status = region_status()
    assert status["configured"] is False
    assert "FF_AWS_REGION" in status["detail"]


def test_region_status_names_its_source(monkeypatch):
    monkeypatch.setenv("FF_AWS_REGION", "ap-south-1")
    status = region_status()
    assert status["configured"] is True
    assert status["source"] == "FF_AWS_REGION"
    assert status["agentcore_supported"] is True
    assert status["detail"] is None


def test_unknown_region_warns_but_does_not_refuse(monkeypatch):
    """AWS adds regions faster than a hard-coded list tracks them."""
    monkeypatch.setenv("FF_AWS_REGION", "eu-north-1")
    status = region_status()
    assert status["configured"] is True
    assert status["agentcore_supported"] is False
    assert "out of date" in status["detail"]


def test_mumbai_is_a_supported_region():
    """The product bills in rupees; ap-south-1 keeps inference in-region."""
    assert "ap-south-1" in AGENTCORE_REGIONS


# --- the AgentCore contract -------------------------------------------------


def test_ping_returns_healthy():
    from bedrock_agentcore.runtime import PingStatus

    assert agentcore_app.ping() == PingStatus.HEALTHY


def test_ping_stays_healthy_when_the_model_is_unconfigured():
    """A config problem must not fail the health check.

    An unhealthy container gets recycled, which would turn a missing region
    into a crash loop that hides the real cause.
    """
    from bedrock_agentcore.runtime import PingStatus

    assert agentcore_app.readiness()["ready"] is False
    assert agentcore_app.ping() == PingStatus.HEALTHY


def test_entrypoint_is_registered():
    assert "main" in agentcore_app.app.handlers


def test_empty_prompt_is_rejected():
    for payload in ({}, {"prompt": ""}, {"prompt": "   "}, {"prompt": 42}):
        result = agentcore_app.invoke(payload)
        assert result["error"] == "invalid_request"
        assert "response" not in result


def test_unconfigured_runtime_refuses_rather_than_answering(monkeypatch):
    monkeypatch.setattr(
        agentcore_app,
        "readiness",
        lambda: {
            "ready": False,
            "model": {"available": False, "detail": "no model"},
            "region": {"detail": None},
            "database": {"detail": None},
            "warnings": [],
        },
    )
    result = agentcore_app.invoke({"prompt": "How much does Rahul owe me?"})
    assert result["error"] == "not_ready"
    assert "response" not in result


def test_a_successful_turn_returns_the_contract_shape(monkeypatch):
    """The runtime returns the reply and the tool trace, never a bare string."""

    class StubService:
        def chat(self, message, session_id=None):
            return {
                "session_id": session_id or "generated",
                "reply": "Rahul owes ₹25,000.00 on FF-0001.",
                "tool_calls": [
                    {
                        "tool": "get_client_balance",
                        "arguments": {"client_id": 1},
                        "status": "ok",
                        "error": None,
                        "duration_seconds": 0.02,
                    }
                ],
                "turn": 1,
                "elapsed_seconds": 1.5,
            }

    monkeypatch.setattr(agentcore_app, "_service", StubService())
    monkeypatch.setattr(
        agentcore_app,
        "readiness",
        lambda: {
            "ready": True,
            "model": {"available": True, "detail": None},
            "region": {"detail": None},
            "database": {"detail": None},
            "warnings": [],
        },
    )

    result = agentcore_app.invoke(
        {"prompt": "How much does Rahul owe me?", "session_id": "s-1"}
    )
    assert result["status"] == "success"
    assert result["response"] == "Rahul owes ₹25,000.00 on FF-0001."
    assert result["tool_calls"][0]["tool"] == "get_client_balance"
    assert result["session_id"] == "s-1"


def test_the_agentcore_session_id_is_used_when_the_payload_omits_one(monkeypatch):
    """Requests carrying the session header land on the same microVM."""
    seen = {}

    class StubService:
        def chat(self, message, session_id=None):
            seen["session_id"] = session_id
            return {
                "session_id": session_id,
                "reply": "ok",
                "tool_calls": [],
                "turn": 1,
                "elapsed_seconds": 0.1,
            }

    class StubContext:
        session_id = "agentcore-session-abc"

    monkeypatch.setattr(agentcore_app, "_service", StubService())
    monkeypatch.setattr(
        agentcore_app,
        "readiness",
        lambda: {
            "ready": True,
            "model": {"available": True, "detail": None},
            "region": {"detail": None},
            "database": {"detail": None},
            "warnings": [],
        },
    )

    agentcore_app.invoke({"prompt": "hello"}, StubContext())
    assert seen["session_id"] == "agentcore-session-abc"


def test_an_unexpected_failure_does_not_leak_internals(monkeypatch):
    class ExplodingService:
        def chat(self, message, session_id=None):
            raise RuntimeError("connection string: postgres://user:hunter2@db")

    monkeypatch.setattr(agentcore_app, "_service", ExplodingService())
    monkeypatch.setattr(
        agentcore_app,
        "readiness",
        lambda: {
            "ready": True,
            "model": {"available": True, "detail": None},
            "region": {"detail": None},
            "database": {"detail": None},
            "warnings": [],
        },
    )

    result = agentcore_app.invoke({"prompt": "hello"})
    assert result["error"] == "internal_error"
    assert "hunter2" not in json.dumps(result)


# --- the persistence limitation, asserted rather than assumed ---------------


def test_storage_is_reported_as_not_durable_by_default(monkeypatch):
    """AgentCore microVM filesystems are per-session and ephemeral.

    This must be visible, not silently assumed to be fine.
    """
    monkeypatch.delenv("FF_STORAGE_DURABLE", raising=False)
    assert agentcore_app.storage_is_durable() is False

    warnings = agentcore_app.readiness()["warnings"]
    assert any("not durable" in w for w in warnings)
    assert any("ephemeral" in w for w in warnings)


def test_durability_can_be_declared_once_storage_is_actually_shared(monkeypatch):
    monkeypatch.setenv("FF_STORAGE_DURABLE", "true")
    assert agentcore_app.storage_is_durable() is True
    assert not any(
        "not durable" in w for w in agentcore_app.readiness()["warnings"]
    )


# --- observability ----------------------------------------------------------


def test_logs_are_one_json_object_per_line():
    record = logging.LogRecord(
        "freelanceflow", logging.INFO, __file__, 1, "invocation completed", (), None
    )
    record.session_id = "s-1"
    record.turn = 2

    line = JsonFormatter().format(record)
    assert "\n" not in line

    parsed = json.loads(line)
    assert parsed["message"] == "invocation completed"
    assert parsed["level"] == "INFO"
    assert parsed["session_id"] == "s-1"
    assert parsed["turn"] == 2
    assert parsed["timestamp"].endswith("Z")


def test_log_formatting_survives_an_unserialisable_field():
    record = logging.LogRecord(
        "freelanceflow", logging.INFO, __file__, 1, "x", (), None
    )
    record.path = Path("/tmp/x")
    assert json.loads(JsonFormatter().format(record))["path"]


def test_tool_summaries_do_not_log_client_data():
    """Arguments carry client names and amounts; they must not reach the logs."""
    summary = tool_call_summary(
        [
            {
                "tool": "record_payment",
                "arguments": {"invoice_id": 1, "amount_minor": 1_500_000},
                "status": "recorded",
                "error": None,
                "duration_seconds": 0.03,
            }
        ]
    )
    assert summary == [
        {
            "tool": "record_payment",
            "status": "recorded",
            "failed": False,
            "duration_seconds": 0.03,
        }
    ]
    assert "arguments" not in json.dumps(summary)
    assert "1500000" not in json.dumps(summary)


# --- deployment artefacts ---------------------------------------------------

DEPLOY = Path(__file__).resolve().parent.parent / "deploy"


def test_dockerfile_pins_arm64():
    """AgentCore requires ARM64. An amd64 image builds fine and then fails."""
    dockerfile = (DEPLOY / "Dockerfile").read_text(encoding="utf-8")
    assert "--platform=linux/arm64" in dockerfile
    assert "EXPOSE 8080" in dockerfile
    assert "app.agentcore_app" in dockerfile


def test_dockerfile_installs_a_font_that_has_the_rupee_sign():
    dockerfile = (DEPLOY / "Dockerfile").read_text(encoding="utf-8")
    assert "fonts-dejavu-core" in dockerfile


def test_runtime_requirements_exclude_the_web_stack():
    """The agent container should not carry the dashboard's dependencies."""
    lines = [
        line.strip()
        for line in (DEPLOY / "requirements-runtime.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    packages = {line.split(">=")[0].split("==")[0].strip() for line in lines}

    assert "bedrock-agentcore" in packages
    assert "strands-agents" in packages
    # The dashboard and the test tools have no business in the agent image.
    assert packages.isdisjoint({"fastapi", "uvicorn", "httpx", "pytest", "pypdf"})


@pytest.mark.parametrize(
    "name",
    [
        "execution-role-policy.json",
        "execution-role-trust-policy.json",
        "invoke-policy.json",
    ],
)
def test_iam_policies_are_valid_json(name):
    json.loads((DEPLOY / "iam" / name).read_text(encoding="utf-8"))


def test_iam_policies_avoid_service_wide_wildcards():
    """No bedrock:* or bedrock-agentcore:*, per the deployment requirements."""
    for path in (DEPLOY / "iam").glob("*.json"):
        policy = json.loads(path.read_text(encoding="utf-8"))
        for statement in policy.get("Statement", []):
            actions = statement.get("Action", [])
            actions = [actions] if isinstance(actions, str) else actions
            for action in actions:
                assert action not in ("bedrock:*", "bedrock-agentcore:*", "*"), (
                    f"{path.name} grants {action}"
                )


def test_the_invoke_policy_grants_only_invocation():
    policy = json.loads(
        (DEPLOY / "iam" / "invoke-policy.json").read_text(encoding="utf-8")
    )
    actions = [a for s in policy["Statement"] for a in s["Action"]]
    assert actions == ["bedrock-agentcore:InvokeAgentRuntime"]


def test_the_trust_policy_prevents_confused_deputy():
    policy = json.loads(
        (DEPLOY / "iam" / "execution-role-trust-policy.json").read_text(
            encoding="utf-8"
        )
    )
    condition = policy["Statement"][0]["Condition"]
    assert "aws:SourceAccount" in condition["StringEquals"]
    assert "aws:SourceArn" in condition["ArnLike"]
