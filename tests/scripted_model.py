"""A Strands model whose replies are scripted, for testing the agent loop offline.

The live tests prove a real model picks the right tools. This proves the
plumbing around it -- hooks, tracing, tool execution, tool results going back
into the conversation -- works without spending anything or needing
credentials. If a live test fails, this is how you tell "the model chose badly"
apart from "our instrumentation is broken".

A script is a list of turns. Each turn is either a list of tool calls to make,
or a string to reply with:

    ScriptedModel([
        [("find_client", {"name": "Rahul"})],
        "Rahul owes you 40,000 rupees.",
    ])
"""

from __future__ import annotations

import json
from typing import Any

from strands.models.model import Model


class ScriptedModel(Model):
    """Replays a fixed sequence of tool calls and text replies."""

    def __init__(self, script: list):
        self.script = list(script)
        self.turn = 0
        # Every (messages, tool_specs) the agent sent us, for assertions about
        # what the model was actually shown.
        self.requests: list[dict[str, Any]] = []

    # --- Model interface ---------------------------------------------------

    def update_config(self, **model_config: Any) -> None:
        self._config = model_config

    def get_config(self) -> Any:
        return getattr(self, "_config", {})

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError("ScriptedModel does not do structured output")
        yield  # pragma: no cover - makes this an async generator

    async def stream(
        self,
        messages,
        tool_specs=None,
        system_prompt=None,
        **kwargs: Any,
    ):
        self.requests.append(
            {
                "messages": messages,
                "tool_specs": tool_specs,
                "system_prompt": system_prompt,
            }
        )

        if self.turn >= len(self.script):
            step: Any = "(script exhausted)"
        else:
            step = self.script[self.turn]
        self.turn += 1

        yield {"messageStart": {"role": "assistant"}}

        if isinstance(step, str):
            yield {"contentBlockDelta": {"delta": {"text": step}}}
            yield {"contentBlockStop": {}}
            stop_reason = "end_turn"
        else:
            for index, (name, arguments) in enumerate(step):
                yield {
                    "contentBlockStart": {
                        "contentBlockIndex": index,
                        "start": {
                            "toolUse": {
                                "name": name,
                                "toolUseId": f"scripted-{self.turn}-{index}",
                            }
                        },
                    }
                }
                yield {
                    "contentBlockDelta": {
                        "contentBlockIndex": index,
                        "delta": {"toolUse": {"input": json.dumps(arguments)}},
                    }
                }
                yield {"contentBlockStop": {"contentBlockIndex": index}}
            stop_reason = "tool_use"

        yield {"messageStop": {"stopReason": stop_reason}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
                "metrics": {"latencyMs": 0},
            }
        }
