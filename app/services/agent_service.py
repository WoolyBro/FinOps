"""The agent service.

All Strands invocation lives here. Route handlers call this; they never build
an Agent, never touch a model, and never see a tool. That boundary is what
makes the eventual AgentCore move a change of one file rather than a rewrite of
the API:

    Browser -> Next.js -> FastAPI -> AgentService -> Strands -> tools -> SQLite

The service also refuses to pretend. If no model provider is configured, chat
raises AgentUnavailable and the API reports that honestly, rather than
returning a plausible-looking reply that no model produced.
"""

from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.agent import build_agent
from app.model_provider import ModelNotConfigured, provider_status
from app.tracing import ToolTracer


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


@dataclass
class Session:
    """One conversation. The Agent carries its own message history."""

    session_id: str
    agent: object
    tracer: ToolTracer
    created_at: str
    last_used: datetime
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
            agent = build_agent(tracer=tracer)
        except ModelNotConfigured as exc:
            raise AgentUnavailable(str(exc)) from exc

        return Session(
            session_id=uuid.uuid4().hex,
            agent=agent,
            tracer=tracer,
            created_at=_now(),
            last_used=datetime.now(timezone.utc),
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
                if existing is not None:
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

    def chat(self, message: str, session_id: str | None = None) -> dict:
        """Run one turn and report what the agent actually did.

        Returns the reply plus the tool calls it made, so the UI can show the
        work rather than only the conclusion.
        """
        if not message or not message.strip():
            raise ValueError("message cannot be empty")

        self.require_available()
        session = self.session(session_id)

        session.tracer.reset()
        started = datetime.now(timezone.utc)
        result = session.agent(message)
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()

        reply = str(result).strip()
        tool_calls = [
            {
                "tool": call.name,
                "arguments": call.arguments,
                "status": call.status,
                "error": call.error,
                "duration_seconds": call.duration_seconds,
            }
            for call in session.tracer.calls
        ]

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
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# One service for the process. Route handlers depend on this through
# app.api.deps.get_agent_service, so tests can swap it out.
agent_service = AgentService()
