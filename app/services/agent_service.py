"""The agent service.

All Strands invocation lives here. Route handlers call this; they never build
an Agent, never touch a model, and never see a tool. That boundary is what
makes the eventual AgentCore move a change of one file rather than a rewrite of
the API:

    Browser -> React (Vite) -> FastAPI -> AgentService -> Strands -> tools -> SQLite

The service also refuses to pretend. If no model provider is configured, chat
raises AgentUnavailable and the API reports that honestly, rather than
returning a plausible-looking reply that no model produced.
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.agent import build_agent
from app.model_provider import ModelNotConfigured, ollama_host, provider_status
from app.preflight import diagnose_failure
from app.security import redact_paths, scrub
from app.tracing import ToolCall, ToolTracer

log = logging.getLogger(__name__)


# A session holds a live Agent and its whole conversation, so an unbounded
# store is a memory leak with a network-facing trigger. Both limits are
# deliberate rather than generous.
MAX_SESSIONS = 200
SESSION_TTL = timedelta(hours=4)

# Session ids are server-issued hex. Accepting arbitrary client strings would
# let a caller name someone else's session and continue their conversation.
_SESSION_ID = re.compile(r"^[0-9a-f]{32}$")


class AgentUnavailable(RuntimeError):
    """No model provider is configured, so no agent can run."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class AgentFailed(RuntimeError):
    """The model failed partway through a turn.

    Carries the tool calls that completed before the failure: a turn can die
    after record_payment succeeded, and the user needs to see that it did.
    """

    def __init__(self, detail: str, tool_calls: list[dict]):
        self.detail = detail
        self.tool_calls = tool_calls
        super().__init__(detail)


def _is_connection_failure(exc: BaseException) -> bool:
    seen: BaseException | None = exc
    while seen is not None:
        name = type(seen).__name__
        if isinstance(seen, ConnectionError) or "ConnectError" in name or "Connection refused" in str(seen):
            return True
        seen = seen.__cause__ or seen.__context__
    return False


def _error_text(exc: BaseException) -> str:
    """Type names and messages down the cause chain.

    Strands can wrap a provider error (EventLoopException from ServerError),
    and the useful status code is on the inner one.
    """
    parts = []
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        parts.append(f"{type(exc).__name__} {exc}")
        exc = exc.__cause__ or exc.__context__
    return " | ".join(parts)


def explain_failure(exc: BaseException, status: dict) -> str:
    """A browser-safe, actionable account of why the model call failed.

    Recognised Bedrock causes get the preflight diagnosis. Anything else gets
    the exception's type only: raw provider errors can carry account ids,
    ARNs and paths, and those belong in the server log, not on a page.
    """
    provider = status.get("provider")
    model = status.get("model_id") or "the model"

    if provider == "gemini":
        text = _error_text(exc)
        if (
            "ServerError" in text
            or "UNAVAILABLE" in text
            or "INTERNAL" in text
            or "overloaded" in text.lower()
            or " 500 " in text
            or " 503 " in text
        ):
            return (
                f"Google's Gemini service returned a temporary error for {model}. "
                "This is on Google's side, not in your data or key -- try the "
                "message again in a few seconds."
            )
        if "API_KEY_INVALID" in text or "API key not valid" in text:
            return (
                "Google rejected the Gemini API key. Check GEMINI_API_KEY in "
                ".env against https://aistudio.google.com/apikey, then restart the API."
            )
        if "RESOURCE_EXHAUSTED" in text or " 429" in text or "quota" in text.lower():
            return (
                f"The Gemini free-tier limit for {model} was reached. Wait a "
                "minute and try again; the daily limit resets at midnight Pacific time."
            )
        if "NOT_FOUND" in text or " 404" in text:
            retired = "no longer available" in text
            return (
                f"Google {'has retired' if retired else 'does not offer'} {model} "
                "for this key. Set FF_MODEL_ID in .env to a model the key can "
                "use -- the models list at https://aistudio.google.com shows them."
            )
        if _is_connection_failure(exc):
            return "Could not reach Google's Gemini API. Check the internet connection."

    if provider == "ollama" and _is_connection_failure(exc):
        return (
            f"Could not reach Ollama at {ollama_host()}. Start it with "
            f"`ollama serve` (and `ollama pull {model}`), or set "
            "FF_MODEL_PROVIDER=bedrock."
        )
    if provider == "bedrock":
        diagnosis = diagnose_failure(exc, model, status.get("region"))
        if not diagnosis.startswith(f"{type(exc).__name__}: "):
            return redact_paths(" ".join(line.strip() for line in diagnosis.splitlines()))
    return (
        f"The model ({model}) failed before it could reply "
        f"({type(exc).__name__}). The server log has the details."
    )


@dataclass
class Session:
    """One conversation. The Agent carries its own message history."""

    session_id: str
    agent: object
    tracer: ToolTracer
    created_at: str
    last_used: datetime
    # The ledger this conversation belongs to. A session is never continued
    # from another workspace: its history is about the other ledger's clients.
    workspace: str | None = None
    turns: int = 0
    history: list[dict] = field(default_factory=list)


class AgentService:
    """Owns agent sessions and is the only thing that invokes Strands."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    # --- availability -----------------------------------------------------

    def status(self) -> dict:
        """What the app can currently talk to. Never raises."""
        status = provider_status()
        return {**status, "active_sessions": len(self._sessions)}

    def require_available(self) -> None:
        status = provider_status()
        if not status["available"]:
            raise AgentUnavailable(status["detail"])

    # --- sessions ---------------------------------------------------------

    def _new_session(self) -> Session:
        tracer = ToolTracer()
        try:
            # No console callback: Strands' default prints every streamed
            # reply to stdout, which on a host is the log -- client names and
            # amounts included. The trace and the API response carry it instead.
            agent = build_agent(tracer=tracer, callback_handler=None)
        except ModelNotConfigured as exc:
            raise AgentUnavailable(str(exc)) from exc

        return Session(
            session_id=uuid.uuid4().hex,
            agent=agent,
            tracer=tracer,
            created_at=_now(),
            last_used=datetime.now(timezone.utc),
            workspace=_workspace_id(),
        )

    def _evict(self) -> None:
        """Drop expired sessions, then the oldest if still over the cap.

        Caller holds the lock.
        """
        cutoff = datetime.now(timezone.utc) - SESSION_TTL
        for key in [
            key
            for key, session in self._sessions.items()
            if session.last_used < cutoff
        ]:
            del self._sessions[key]

        while len(self._sessions) >= MAX_SESSIONS:
            oldest = min(self._sessions, key=lambda k: self._sessions[k].last_used)
            del self._sessions[oldest]

    def session(self, session_id: str | None) -> Session:
        """Fetch an existing session, or start one.

        An id that is not a live server-issued session starts a fresh
        conversation rather than failing -- a restarted server should not break
        the page the user is looking at. It is never used as the new session's
        id: ids are issued here, so a caller cannot choose one and cannot name
        a session it was not given.
        """
        with self._lock:
            if session_id and _SESSION_ID.match(session_id):
                existing = self._sessions.get(session_id)
                if existing is not None and existing.workspace == _workspace_id():
                    existing.last_used = datetime.now(timezone.utc)
                    return existing

            self._evict()
            session = self._new_session()
            self._sessions[session.session_id] = session
            return session

    def reset(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def history(self, session_id: str) -> list[dict]:
        with self._lock:
            session = self._sessions.get(session_id)
            return list(session.history) if session else []

    # --- the one call that runs a model -----------------------------------

    def chat(
        self,
        message: str,
        session_id: str | None = None,
        on_event: Callable[[dict], None] | None = None,
    ) -> dict:
        """Run one turn and report what the agent actually did.

        Returns the reply plus the tool calls it made, so the UI can show the
        work rather than only the conclusion. With `on_event`, each model call
        and tool call is also reported the moment it starts and ends -- these
        are the tracer's hook events, not a simulation of progress.
        """
        if not message or not message.strip():
            raise ValueError("message cannot be empty")

        self.require_available()
        session = self.session(session_id)

        session.tracer.reset()
        session.tracer.listener = on_event
        if on_event is not None:
            on_event({"type": "turn_start", "session_id": session.session_id})
        started = datetime.now(timezone.utc)
        try:
            result = session.agent(message)
        except Exception as exc:
            log.exception("agent turn failed")
            raise AgentFailed(
                explain_failure(exc, provider_status()),
                _trace(session.tracer.calls),
            ) from exc
        finally:
            session.tracer.listener = None
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()

        # The model reads tool results that carry server paths, and can repeat
        # them. The prompt forbids it; this makes sure a lapse never reaches a
        # browser, a screen recording, or someone else's username on camera.
        reply = redact_paths(str(result).strip())
        tool_calls = _trace(session.tracer.calls)

        session.turns += 1
        session.last_used = datetime.now(timezone.utc)
        session.history.append({"role": "user", "content": message, "at": _now()})
        session.history.append(
            {
                "role": "assistant",
                "content": reply,
                "at": _now(),
                "tool_calls": tool_calls,
            }
        )

        return {
            "session_id": session.session_id,
            "reply": reply,
            "tool_calls": tool_calls,
            "turn": session.turns,
            "elapsed_seconds": round(elapsed, 3),
            "result_card": result_card(session.tracer.calls),
        }


def _trace(calls: list[ToolCall]) -> list[dict]:
    return [
        {
            "tool": call.name,
            "arguments": call.arguments,
            "status": call.status,
            "error": call.error,
            "duration_seconds": call.duration_seconds,
        }
        for call in calls
    ]


def result_card(calls: list[ToolCall]) -> dict | None:
    """The record a turn produced, read from the tool's result, not the reply.

    The reply is the model's prose about what happened; this is what actually
    happened. Rendering the card from the tool result means the figures a user
    checks at a glance -- amount, invoice, balance left -- cannot be a figure
    the model misremembered. A refused or failed call produces no card.
    """
    for call in reversed(calls):
        result = call.result if isinstance(call.result, dict) else None
        if call.error or not result:
            continue
        status = result.get("status")
        if call.name == "record_payment" and status == "recorded":
            payment = dict(result["payment"])
            # A receipt issued later in the same turn belongs on the card: the
            # payment snapshot above was taken before generate_receipt ran.
            if not payment.get("receipt_number"):
                payment["receipt_number"] = _receipt_issued_for(calls, payment["payment_id"])
            return scrub({"type": "payment", "payment": payment, "invoice": result["invoice"]})
        if call.name == "create_invoice" and status == "created":
            return scrub({"type": "invoice", "invoice": result["invoice"]})
        if call.name == "create_payment_reminder" and status == "prepared":
            return scrub({"type": "reminder", "reminder": result["reminder"]})
    return None


def _receipt_issued_for(calls: list[ToolCall], payment_id: int) -> str | None:
    """The receipt number a successful generate_receipt call returned, if any."""
    for call in calls:
        result = call.result if isinstance(call.result, dict) else None
        if (
            call.name == "generate_receipt"
            and not call.error
            and result
            and result.get("status") in ("created", "already_exists")
            and call.arguments.get("payment_id") == payment_id
        ):
            return result.get("receipt_number")
    return None


def _workspace_id() -> str | None:
    from app import workspaces

    workspace = workspaces.current()
    return workspace.id if workspace else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# One service for the process. Route handlers depend on this through
# app.api.deps.get_agent_service, so tests can swap it out.
agent_service = AgentService()
