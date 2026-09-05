"""Terminal entry point.

    python -m app.cli                     interactive session
    python -m app.cli "Rahul paid 15k"    one-shot
    python -m app.cli --init-db           create the database and exit
"""

from __future__ import annotations

import sys

from app.config import DB_PATH
from app.database import init_db
from app.model_provider import ModelNotConfigured, resolve_provider


def _force_utf8_output() -> None:
    """Windows consoles default to cp1252, which cannot encode the rupee sign.

    Every money string this app produces carries a currency symbol, so without
    this the first invoice total printed would raise UnicodeEncodeError.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_output()
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--init-db" in argv:
        init_db()
        print(f"Database ready at {DB_PATH}")
        return 0

    from app.agent import build_agent

    try:
        provider = resolve_provider()
        agent = build_agent()
    except ModelNotConfigured as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        return 2

    if argv:
        agent(" ".join(argv))
        return 0

    print(f"FreelanceFlow  (model provider: {provider})")
    print("Type your request, or 'exit' to quit.\n")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if line.lower() in {"exit", "quit"}:
            return 0
        if not line:
            continue
        print()
        agent(line)
        print()


if __name__ == "__main__":
    raise SystemExit(main())
