"""Phase 5 smoke test, run by hand against a real model.

    python -m app.live_check              # the two-tool loop only
    python -m app.live_check --full       # the full 21-tool agent
    python -m app.live_check --scenario payment

Prints the tool chain the model chose, so you can see *why* an answer was right
or wrong rather than judging the paragraph at the end. Uses a scratch database
so it never touches data/freelanceflow.db.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


def _force_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


SCENARIOS = {
    "balance": {
        "tools": ["find_client", "get_client_balance"],
        "seed": "invoice",
        "prompt": "How much does Rahul owe me?",
        "why": "The fundamental loop: one tool result feeds the next call.",
    },
    "payment": {
        "tools": [
            "find_client", "get_invoice", "list_invoices", "parse_amount",
            "record_payment", "generate_receipt",
        ],
        "seed": "invoice",
        "prompt": "Rahul paid me 15,000 rupees today for the website project. "
                  "Update everything.",
        "why": "The hero case: a real mutation, sequence chosen by the model.",
    },
    "ambiguous": {
        "tools": ["find_client", "list_invoices", "parse_amount", "record_payment"],
        "seed": "two_rahuls",
        "prompt": "Rahul paid me 15,000 rupees.",
        "why": "Two Rahuls. The agent must ask, not pick.",
    },
    "missing": {
        "tools": ["find_client", "create_client", "parse_amount", "create_invoice"],
        "seed": "client",
        "prompt": "Create an invoice for Rahul.",
        "why": "No amount given. The agent must ask, not invent one.",
    },
    "shorthand": {
        "tools": ["find_client", "parse_amount", "create_invoice"],
        "seed": "client",
        "prompt": "Create an invoice for Rahul for 40k for website development, "
                  "due September 15 2026.",
        "why": "parse_amount must receive '40k', not the whole sentence.",
    },
    "unknown": {
        "tools": ["find_client", "get_client_balance"],
        "seed": "empty",
        "prompt": "How much does Rahul owe me?",
        "why": "No such client. A number in the reply here is a hallucination.",
    },
}


def seed(kind: str) -> None:
    from app.tools.clients import create_client
    from app.tools.invoices import create_invoice

    if kind == "empty":
        return

    client = create_client(name="Rahul Sharma", email="rahul@example.com")["client"]
    if kind == "two_rahuls":
        other = create_client(name="Rahul Verma")["client"]
        for c in (client, other):
            create_invoice(
                client_id=c["client_id"],
                project="Website development",
                amount_minor=4_000_000,
            )
        return
    if kind == "invoice":
        create_invoice(
            client_id=client["client_id"],
            project="Website development",
            amount_minor=4_000_000,
            due_date="2026-09-15",
        )


def resolve_tools(names: list[str] | None):
    from app.agent import TOOLS

    if names is None:
        return None
    by_name = {t.tool_name: t for t in TOOLS}
    missing = [n for n in names if n not in by_name]
    if missing:
        raise SystemExit(f"unknown tools: {missing}")
    return [by_name[n] for n in names]


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario", default="balance", choices=sorted(SCENARIOS),
        help="which check to run (default: balance)",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="give the agent all 21 tools instead of the scenario's subset",
    )
    parser.add_argument("--prompt", help="override the scenario's prompt")
    args = parser.parse_args(argv)

    scenario = SCENARIOS[args.scenario]

    # A scratch database, so a smoke test never writes to real records.
    scratch = Path(tempfile.mkdtemp(prefix="freelanceflow-live-"))
    from app import database, config

    database.DB_PATH = scratch / "live.db"
    config.INVOICES_DIR = scratch / "invoices"
    config.RECEIPTS_DIR = scratch / "receipts"
    import app.pdf_generator as pdf

    pdf.INVOICES_DIR = scratch / "invoices"
    pdf.RECEIPTS_DIR = scratch / "receipts"

    from app.model_provider import ModelNotConfigured, resolve_provider

    try:
        provider = resolve_provider()
    except ModelNotConfigured as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        return 2

    database.init_db()
    seed(scenario["seed"])

    from app.agent import build_agent
    from app.tracing import ToolTracer

    tools = None if args.full else resolve_tools(scenario["tools"])
    tracer = ToolTracer()
    agent = build_agent(tools=tools, tracer=tracer)

    prompt = args.prompt or scenario["prompt"]
    tool_count = "all 21" if tools is None else str(len(tools))

    print(f"scenario : {args.scenario}")
    print(f"provider : {provider}")
    print(f"tools    : {tool_count}")
    print(f"database : {database.DB_PATH}")
    print(f"checking : {scenario['why']}")
    print(f"\nyou> {prompt}\n")

    result = agent(prompt)

    print("\n--- tool calls ---")
    print(tracer.format())
    print("\n--- reply ---")
    print(str(result).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
