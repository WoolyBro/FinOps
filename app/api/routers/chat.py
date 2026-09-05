"""The agent endpoints.

These handlers do not import Strands, build an agent, or know what a tool is.
They translate HTTP into an AgentService call and back.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_agent_service
from app.api.schemas import AgentStatus, ChatRequest, ChatResponse
from app.services.agent_service import AgentService, AgentUnavailable

router = APIRouter(tags=["agent"])


@router.get("/agent/status", response_model=AgentStatus)
def agent_status(service: AgentService = Depends(get_agent_service)) -> dict:
    """Whether a model is reachable, and which one.

    The frontend reads this to show a configuration state instead of a chat box
    that would fail on first use.
    """
    return service.status()


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    service: AgentService = Depends(get_agent_service),
) -> dict:
    """Run one turn of conversation.

    Returns the reply together with the tool calls the agent made, so the UI can
    show what actually happened rather than only the sentence at the end.
    """
    try:
        return service.chat(request.message, session_id=request.session_id)
    except AgentUnavailable as exc:
        # 503, not 500: nothing is broken, the model is simply not configured.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "agent_unavailable", "detail": exc.detail},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"error": "invalid_request", "detail": str(exc)},
        ) from exc


@router.delete("/chat/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def reset_session(
    session_id: str, service: AgentService = Depends(get_agent_service)
) -> None:
    """Forget a conversation. Business records are untouched."""
    if not service.reset(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "detail": f"No session {session_id}"},
        )
