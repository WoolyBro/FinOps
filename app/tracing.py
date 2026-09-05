"""Tool-call tracing.

Phase 5 is about whether the model chooses the right tools, not whether the
final English paragraph reads well. A fluent answer built on a skipped lookup
or an invented id is a failure that looks like a success, so every live test
asserts against the recorded call chain rather than the prose.

This is also what the demo's "agent activity" panel will read from later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent, HookRegistry


@dataclass
class ToolCall:
    """One tool invocation: what the model chose, with what, and what it got."""

    name: str
    arguments: dict[str, Any]
    result: Any = None
    error: str | None = None
    duration_seconds: float | None = None

    @property
    def status(self) -> str | None:
        """The tool's own status field, which is what the agent had to read."""
        if isinstance(self.result, dict):
            return self.result.get("status")
        return None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        args = ", ".join(f"{k}={v!r}" for k, v in self.arguments.items())
        return f"{self.name}({args}) -> {self.status or self.error or 'ok'}"


class ToolTracer:
    """Records the tool calls an agent makes, in order.

    Attach with `Agent(hooks=[tracer])`, then read `tracer.calls` afterwards.
    """

    def __init__(self, echo: bool = False):
        self.calls: list[ToolCall] = []
        self.echo = echo
        self._by_use_id: dict[str, ToolCall] = {}

    # --- HookProvider -----------------------------------------------------

    def register_hooks(self, registry: HookRegistry, **_: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._on_before)
        registry.add_callback(AfterToolCallEvent, self._on_after)

    def _on_before(self, event: BeforeToolCallEvent) -> None:
        tool_use = event.tool_use or {}
        call = ToolCall(
            name=tool_use.get("name", "<unknown>"),
            arguments=dict(tool_use.get("input") or {}),
        )
        self.calls.append(call)
        use_id = tool_use.get("toolUseId")
        if use_id:
            self._by_use_id[use_id] = call
        if self.echo:
            print(f"  -> {call.name}({_short(call.arguments)})")

    def _on_after(self, event: AfterToolCallEvent) -> None:
        tool_use = event.tool_use or {}
        call = self._by_use_id.get(tool_use.get("toolUseId", "")) or (
            self.calls[-1] if self.calls else None
        )
        if call is None:
            return

        call.duration_seconds = getattr(event, "duration", None)
        if event.exception is not None:
            call.error = str(event.exception)
        else:
            call.result = _unwrap(event.result)

        if self.echo:
            outcome = call.error or call.status or "ok"
            print(f"     {outcome}")

    # --- reading the trace ------------------------------------------------

    @property
    def names(self) -> list[str]:
        """Tool names in call order, e.g. ['find_client', 'record_payment']."""
        return [c.name for c in self.calls]

    def called(self, name: str) -> bool:
        return name in self.names

    def first(self, name: str) -> ToolCall | None:
        return next((c for c in self.calls if c.name == name), None)

    def all_of(self, name: str) -> list[ToolCall]:
        return [c for c in self.calls if c.name == name]

    def reset(self) -> None:
        self.calls.clear()
        self._by_use_id.clear()

    def format(self) -> str:
        """A readable trace, for test failure messages and manual runs."""
        if not self.calls:
            return "(no tools were called)"
        lines = []
        for i, call in enumerate(self.calls, 1):
            lines.append(f"{i}. {call.name}({_short(call.arguments)})")
            lines.append(f"   -> {call.error or call.status or _short(call.result)}")
        return "\n".join(lines)


def _unwrap(result: Any) -> Any:
    """Pull the tool's own dict back out of the Strands ToolResult envelope.

    Strands wraps a tool's return value as {"content": [{"text"|"json": ...}]}.
    The tests care about the dict the tool actually returned.
    """
    if not isinstance(result, dict):
        return result
    content = result.get("content")
    if not isinstance(content, list) or not content:
        return result

    block = content[0]
    if not isinstance(block, dict):
        return result
    if "json" in block:
        return block["json"]
    if "text" in block:
        text = block["text"]
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return text
    return result


def _short(value: Any, limit: int = 160) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"
