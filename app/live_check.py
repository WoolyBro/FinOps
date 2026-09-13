"""Smoke test, run by hand against a real model.

    python -m app.live_check --preflight            # checks only, no model call
    python -m app.live_check --scenario balance     # one call
    python -m app.live_check --scenario payment     # one call, one mutation
    python -m app.live_check --provider gemini      # Gemini, free tier
    python -m app.live_check --provider ollama      # develop without AWS

Prints the tool chain the model chose, so you can see *why* an answer was right
or wrong rather than judging the paragraph at the end. Uses a scratch database
so it never touches data/freelanceflow.db.

COSTS AWS CREDITS. One run is one conversation -- a handful of model calls at
most, since the agent may take several turns to finish a task. Preflight is
free and makes no calls at all.

The provider defaults to bedrock and is enforced: if bedrock is asked for and
does not resolve, this fails rather than quietly running against Ollama. A pass
from the wrong model proves nothing.
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




def database_summary() -> str:
    """What the database actually contains, so the reply can be checked.

    The whole point of the exercise is proving the model read these rows rather
    than inventing them, which means printing the rows.
    """
    from app.database import get_db

    lines = []
    with get_db() as conn:
        clients = conn.execute("SELECT id, name FROM clients ORDER BY id").fetchall()
        lines.append(f"clients: {len(clients)}")
        for row in clients:
            lines.append(f"  #{row['id']} {row['name']}")

        invoices = conn.execute(
            """SELECT i.invoice_number, c.name, i.amount_minor, i.status,
                      COALESCE((SELECT SUM(p.amount_minor) FROM payments p
                                 WHERE p.invoice_id = i.id), 0) AS paid
                 FROM invoices i JOIN clients c ON c.id = i.client_id
                ORDER BY i.id"""
        ).fetchall()
        lines.append(f"invoices: {len(invoices)}")
        for row in invoices:
            outstanding = row["amount_minor"] - row["paid"]
            lines.append(
                f"  {row['invoice_number']} {row['name']}: "
                f"amount={row['amount_minor']} paid={row['paid']} "
                f"outstanding={outstanding} status={row['status']}"
            )

        payments = conn.execute(
            """SELECT p.id, p.amount_minor, p.payment_date, p.method,
                      i.invoice_number
                 FROM payments p JOIN invoices i ON i.id = p.invoice_id
                ORDER BY p.id"""
        ).fetchall()
        lines.append(f"payments: {len(payments)}")
        for row in payments:
            lines.append(
                f"  #{row['id']} {row['invoice_number']} "
                f"amount={row['amount_minor']} date={row['payment_date']} "
                f"method={row['method']}"
            )

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario", default="balance", choices=sorted(SCENARIOS),
        help="which check to run (default: balance)",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="give the agent all 22 tools instead of the scenario's subset",
    )
    parser.add_argument("--prompt", help="override the scenario's prompt")
    parser.add_argument(
        "--provider", default="bedrock", choices=("bedrock", "gemini", "ollama"),
        help="which provider this run requires (default: bedrock)",
    )
    parser.add_argument(
        "--preflight", action="store_true",
        help="run the checks and stop, without calling a model",
    )
    args = parser.parse_args(argv)

    # --- preflight ---------------------------------------------------------
    # Free, calls nothing, and refuses to run against the wrong provider: a
    # pass from Ollama would not prove anything about Bedrock.
    from app.preflight import preflight

    report = preflight(require_provider=args.provider)
    print(f"preflight ({args.provider}):")
    print(report.format())

    if not report.ok:
        print(
            f"\nRefusing to run: {len(report.failures)} prerequisite(s) not met.",
            file=sys.stderr,
        )
        print(
            "No model was called, so nothing was spent. This run will not fall "
            "back to another provider.",
            file=sys.stderr,
        )
        return 2

    if args.preflight:
        print("\nPreflight passed. No model was called.")
        return 0

    scenario = SCENARIOS[args.scenario]

    # A scratch database, so a smoke test never writes to real records.
    scratch = Path(tempfile.mkdtemp(prefix="freelanceflow-live-"))
    from app import config, database

    database.DB_PATH = scratch / "live.db"
    config.INVOICES_DIR = scratch / "invoices"
    config.RECEIPTS_DIR = scratch / "receipts"
    import app.pdf_generator as pdf

    pdf.INVOICES_DIR = scratch / "invoices"
    pdf.RECEIPTS_DIR = scratch / "receipts"

    database.init_db()
    seed(scenario["seed"])

    from app.agent import build_agent
    from app.tracing import ToolTracer

    tools = None if args.full else resolve_tools(scenario["tools"])
    tracer = ToolTracer()
    agent = build_agent(tools=tools, tracer=tracer)

    prompt = args.prompt or scenario["prompt"]
    tool_count = "all 22" if tools is None else str(len(tools))

    print()
    print(f"scenario : {args.scenario}")
    print(f"provider : {report.provider}")
    print(f"model    : {report.model_id}")
    print(f"region   : {report.region or '-'}")
    print(f"tools    : {tool_count}")
    print(f"database : {database.DB_PATH}")
    print(f"checking : {scenario['why']}")

    print("\n--- database before ---")
    print(database_summary())
    print(f"\nyou> {prompt}\n")

    try:
        result = agent(prompt)
    except Exception as exc:
        from app.preflight import diagnose_failure

        print("\n--- the model call failed ---", file=sys.stderr)
        print(diagnose_failure(exc, report.model_id, report.region), file=sys.stderr)
        if tracer.calls:
            print("\ntools that ran before the failure:", file=sys.stderr)
            print(tracer.format(), file=sys.stderr)
        return 1

    print("\n--- tool calls ---")
    print(tracer.format() if tracer.calls else "  (none -- the model answered "
          "without calling a tool, which for a financial question means it "
          "made the number up)")

    print("\n--- reply ---")
    print(str(result).strip())

    print("\n--- database after ---")
    print(database_summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
