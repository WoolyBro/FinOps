"""Request and response shapes for the API.

Responses are deliberately thin wrappers around what the tools already return.
The tool output is the contract -- re-modelling every field here would create a
second place for a money figure to be wrong.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="What the freelancer said, in their own words.",
    )
    session_id: str | None = Field(
        None,
        description="Continue an existing conversation. Omit to start a new one.",
    )


class ToolCall(BaseModel):
    tool: str
    arguments: dict
    status: str | None = None
    error: str | None = None
    duration_seconds: float | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    tool_calls: list[ToolCall]
    turn: int
    elapsed_seconds: float
    result_card: dict | None = Field(
        None,
        description=(
            "The record this turn created, taken from the tool result: "
            "{type: payment|invoice|reminder, ...}. Null when nothing was written."
        ),
    )


class AgentStatus(BaseModel):
    available: bool
    provider: str | None
    model_id: str | None
    detail: str | None = None
    active_sessions: int = 0


class ErrorResponse(BaseModel):
    """One shape for every failure, so the frontend has one thing to handle."""

    error: str = Field(..., description="A stable machine-readable code.")
    detail: str = Field(..., description="A human-readable explanation.")
