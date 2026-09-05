"""Dependencies shared by the routers."""

from __future__ import annotations

from app.services.agent_service import AgentService, agent_service


def get_agent_service() -> AgentService:
    """The process-wide agent service.

    A dependency rather than a direct import so tests can override it and
    exercise the chat endpoint without a model provider.
    """
    return agent_service
