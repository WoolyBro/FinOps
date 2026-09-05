"""AgentCore Runtime entry point.

Implements the AgentCore HTTP service contract for the existing FreelanceFlow
agent. Verified against the AWS docs rather than assumed:

    host      0.0.0.0
    port      8080
    POST      /invocations   JSON in, JSON out
    GET       /ping          {"status": "Healthy" | "HealthyBusy"}
    platform  ARM64 container
    session   X-Amzn-Bedrock-AgentCore-Runtime-Session-Id routes to a microVM

The `bedrock_agentcore` SDK provides the server and handles /ping wiring; this
module supplies the entrypoint and a readiness-aware ping handler.

Nothing about the agent changes here. This calls the same AgentService the
FastAPI layer calls, which is the whole point of having had that boundary:

    AgentCore Runtime -> this entrypoint -> AgentService -> Strands -> tools

IMPORTANT -- persistence. AgentCore gives each session its own microVM with its
own filesystem, and that filesystem is ephemeral by default. The SQLite database
this app writes is therefore NOT shared between sessions and does NOT survive a
deploy. See docs/AGENTCORE.md for the analysis and the migration path. This
entrypoint is correct; the storage underneath it is not yet production-durable,
and `readiness()` says so out loud rather than letting it pass unnoticed.
"""

from __future__ import annotations

import os
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp, PingStatus

from app.aws_config import region_status
from app.database import init_db
from app.model_provider import provider_status
from app.observability import configure_logging, tool_call_summary
from app.services.agent_service import AgentService, AgentUnavailable

log = configure_logging()
app = BedrockAgentCoreApp()

# One service for the container. Sessions inside it are keyed by the AgentCore
# session id, so a microVM reused across invocations keeps its conversation.
_service = AgentService()


# --- readiness -------------------------------------------------------------


def storage_is_durable() -> bool:
    """Whether the database lives somewhere that survives this microVM.

    False on a default AgentCore deployment: the container filesystem is
    ephemeral and per-session. Set FF_STORAGE_DURABLE=true once the database is
    on a mount that is genuinely shared and persistent (an EFS or S3 Files
    access point), or once it has moved off SQLite entirely.
    """
    return os.getenv("FF_STORAGE_DURABLE", "").strip().lower() in {"1", "true", "yes"}


def readiness() -> dict:
    """Everything the container needs in order to actually answer a request."""
    provider = provider_status()
    region = region_status()

    try:
        init_db()
        database_ok, database_detail = True, None
    except Exception as exc:  # a container that cannot open its DB is not ready
        database_ok, database_detail = False, str(exc)

    warnings = []
    if not storage_is_durable():
        warnings.append(
            "Storage is not durable: the SQLite database is on the microVM "
            "filesystem, which is per-session and ephemeral. Records will not "
            "be shared between sessions and will not survive a deploy."
        )
    if region["configured"] and not region["agentcore_supported"]:
        warnings.append(region["detail"])

    return {
        "ready": bool(provider["available"] and region["configured"] and database_ok),
        "model": {
            "available": provider["available"],
            "provider": provider.get("provider"),
            "model_id": provider.get("model_id"),
            "detail": provider.get("detail"),
        },
        "region": region,
        "database": {"ok": database_ok, "detail": database_detail},
        "warnings": warnings,
    }


@app.ping
def ping() -> PingStatus:
    """Health for the AgentCore control plane.

    Returns Healthy whenever the container can serve. Readiness problems -- a
    missing region, an unconfigured model -- are reported in the /invocations
    response and in the logs, not by failing the health check: a container that
    reports unhealthy gets recycled, which would turn a configuration mistake
    into a crash loop that hides the real cause.
    """
    return PingStatus.HEALTHY


# --- the entrypoint ---------------------------------------------------------


@app.entrypoint
def invoke(payload: dict, context: Any = None) -> dict:
    """Handle one AgentCore invocation.

    Args:
        payload: The JSON body. `prompt` is the user's message. An optional
            `session_id` overrides the AgentCore session id for conversation
            continuity.
        context: RequestContext from the SDK, carrying the AgentCore session id.

    Returns:
        A JSON-serialisable dict: the reply, the tool calls the agent made, and
        the session it belongs to. On failure, an `error` field -- never a
        fabricated reply.
    """
    prompt = (payload or {}).get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        log.warning("invocation rejected", extra={"reason": "empty_prompt"})
        return {
            "error": "invalid_request",
            "detail": "Provide a non-empty 'prompt' in the request body.",
        }

    # Prefer the AgentCore session id: requests carrying it land on the same
    # microVM, so the conversation and the process-local state line up.
    session_id = (payload or {}).get("session_id") or getattr(
        context, "session_id", None
    )

    state = readiness()
    for warning in state["warnings"]:
        log.warning("readiness warning", extra={"warning": warning})

    if not state["ready"]:
        detail = (
            state["model"]["detail"]
            or state["region"]["detail"]
            or state["database"]["detail"]
            or "The runtime is not configured."
        )
        log.error("invocation refused", extra={"reason": "not_ready"})
        return {"error": "not_ready", "detail": detail, "readiness": state}

    log.info(
        "invocation started",
        extra={"session_id": session_id, "prompt_chars": len(prompt)},
    )

    try:
        result = _service.chat(prompt, session_id=session_id)
    except AgentUnavailable as exc:
        log.error("agent unavailable", extra={"detail": exc.detail})
        return {"error": "agent_unavailable", "detail": exc.detail}
    except Exception as exc:
        # Log the traceback; return something the caller can act on without
        # leaking internals.
        log.exception("invocation failed", extra={"session_id": session_id})
        return {
            "error": "internal_error",
            "detail": f"{type(exc).__name__} while handling the request.",
        }

    log.info(
        "invocation completed",
        extra={
            "session_id": result["session_id"],
            "turn": result["turn"],
            "elapsed_seconds": result["elapsed_seconds"],
            "tool_calls": tool_call_summary(result["tool_calls"]),
        },
    )

    return {
        "response": result["reply"],
        "session_id": result["session_id"],
        "tool_calls": result["tool_calls"],
        "turn": result["turn"],
        "elapsed_seconds": result["elapsed_seconds"],
        "status": "success",
    }


if __name__ == "__main__":
    state = readiness()
    log.info("agentcore runtime starting", extra={"readiness": state})
    # Host defaults to 0.0.0.0 in the SDK; the port is the contract's 8080.
    app.run(port=int(os.getenv("PORT", "8080")))
