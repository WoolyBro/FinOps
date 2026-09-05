"""Guards against a tool existing but never reaching the agent.

generate_invoice_pdf was written, tested and left unregistered -- the suite was
green and the agent still could not produce a document. These tests make that
class of mistake fail loudly.
"""

import importlib
import pkgutil

import pytest

from strands.tools.decorator import DecoratedFunctionTool

import app.tools
from app.agent import TOOLS, system_prompt


def all_defined_tools() -> dict[str, DecoratedFunctionTool]:
    """Every @tool defined anywhere under app.tools, by name."""
    found: dict[str, DecoratedFunctionTool] = {}
    for info in pkgutil.iter_modules(app.tools.__path__):
        module = importlib.import_module(f"app.tools.{info.name}")
        for attr in vars(module).values():
            if isinstance(attr, DecoratedFunctionTool):
                found[attr.tool_name] = attr
    return found


def test_every_defined_tool_is_registered_with_the_agent():
    registered = {t.tool_name for t in TOOLS}
    defined = set(all_defined_tools())
    assert defined - registered == set(), (
        "these tools exist but the agent cannot call them: "
        f"{sorted(defined - registered)}"
    )


def test_no_duplicate_tool_names():
    names = [t.tool_name for t in TOOLS]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.tool_name)
def test_every_tool_has_a_description(tool):
    """The description is the only thing the model reads before choosing."""
    assert tool.tool_spec.get("description", "").strip()


@pytest.mark.parametrize("tool", TOOLS, ids=lambda t: t.tool_name)
def test_every_tool_parameter_is_documented(tool):
    schema = tool.tool_spec["inputSchema"]["json"]
    for name, spec in schema.get("properties", {}).items():
        assert spec.get("description", "").strip(), (
            f"{tool.tool_name}.{name} has no description, so the model has to "
            "guess what to pass"
        )


def test_system_prompt_carries_todays_date():
    assert "2026-01-02" in system_prompt(today="2026-01-02")


def test_system_prompt_states_the_rules_that_keep_the_agent_honest():
    prompt = system_prompt()
    for phrase in ("Never invent", "parse_amount", "generate_invoice_pdf"):
        assert phrase in prompt
