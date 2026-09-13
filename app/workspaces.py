"""Workspaces: separate ledgers behind one API.

The dashboard opens on a choice -- the existing ledger, already holding sample
clients and invoices, or a new one that starts empty. Each workspace is its own
SQLite file and its own invoice and receipt folders, so nothing recorded in
one can appear in, or be changed from, the other. Not by the dashboard, not by
the agent.

The choice travels with every request -- the X-FF-Workspace header, or a
?workspace= query parameter for plain links like PDF downloads, which cannot
carry headers -- and is held in a context variable for that request alone.
database.connect() and the PDF renderer consult it. With no workspace set they
behave exactly as before, so the CLI, the test suite and the AgentCore
entrypoint are untouched.

A context variable rather than a global because two browser tabs can be on
different workspaces at the same moment; a process-wide "current workspace"
would let one tab's payment land in the other tab's ledger.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from app.config import ROOT

# Where workspace folders live. Read at call time (not bound at import) so
# tests can point it at a temporary directory.
WORKSPACES_ROOT = Path(os.getenv("FF_WORKSPACES_DIR", ROOT / "data"))

HEADER = "x-ff-workspace"
QUERY_PARAM = "workspace"


class UnknownWorkspace(ValueError):
    """The request named a workspace that does not exist."""


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    description: str

    @property
    def root(self) -> Path:
        return WORKSPACES_ROOT / self.id

    @property
    def db_path(self) -> Path:
        return self.root / "freelanceflow.db"

    @property
    def invoices_dir(self) -> Path:
        return self.root / "invoices"

    @property
    def receipts_dir(self) -> Path:
        return self.root / "receipts"


WORKSPACES: dict[str, Workspace] = {
    "demo": Workspace(
        id="demo",
        name="Existing dashboard",
        description=(
            "The sample ledger: clients, invoices, payments and reminders "
            "already recorded."
        ),
    ),
    "fresh": Workspace(
        id="fresh",
        name="New dashboard",
        description=(
            "A ledger of your own that starts empty. Everything you add stays here."
        ),
    ),
}

_current: ContextVar[Workspace | None] = ContextVar("ff_workspace", default=None)
_initialised: set[Path] = set()
_init_lock = threading.Lock()


def get(workspace_id: str) -> Workspace:
    try:
        return WORKSPACES[workspace_id.strip().lower()]
    except (KeyError, AttributeError):
        raise UnknownWorkspace(
            f"Unknown workspace {workspace_id!r}. Use one of: {', '.join(WORKSPACES)}."
        ) from None


def current() -> Workspace | None:
    """The workspace this request is working in, or None outside a request."""
    return _current.get()


def _ensure_ready(workspace: Workspace) -> None:
    """Create the folders and schema the first time a workspace is used."""
    if workspace.db_path in _initialised:
        return
    with _init_lock:
        if workspace.db_path in _initialised:
            return
        for directory in (workspace.root, workspace.invoices_dir, workspace.receipts_dir):
            directory.mkdir(parents=True, exist_ok=True)
        from app.database import init_db  # local: database imports this module

        init_db(workspace.db_path)
        _initialised.add(workspace.db_path)


def activate(workspace_id: str) -> Token:
    """Enter a workspace for the rest of the current context. Pair with deactivate."""
    workspace = get(workspace_id)
    _ensure_ready(workspace)
    return _current.set(workspace)


def deactivate(token: Token) -> None:
    _current.reset(token)


@contextmanager
def using(workspace_id: str) -> Iterator[Workspace]:
    token = activate(workspace_id)
    try:
        yield _current.get()
    finally:
        deactivate(token)


# --- what the storage layer asks ---------------------------------------------


def db_path() -> Path | None:
    workspace = current()
    return workspace.db_path if workspace else None


def invoices_dir() -> Path | None:
    workspace = current()
    return workspace.invoices_dir if workspace else None


def receipts_dir() -> Path | None:
    workspace = current()
    return workspace.receipts_dir if workspace else None


# --- the chooser ---------------------------------------------------------------


def overview() -> list[dict]:
    """Each workspace with how much is in it, for the opening screen."""
    from app.database import get_db

    queries = {
        "clients": "SELECT COUNT(*) FROM clients",
        "invoices": "SELECT COUNT(*) FROM invoices",
        "payments": "SELECT COUNT(*) FROM payments",
    }
    rows = []
    for workspace in WORKSPACES.values():
        with using(workspace.id):
            with get_db() as conn:
                counts = {
                    name: conn.execute(sql).fetchone()[0] for name, sql in queries.items()
                }
        rows.append(
            {
                "id": workspace.id,
                "name": workspace.name,
                "description": workspace.description,
                "client_count": counts["clients"],
                "invoice_count": counts["invoices"],
                "payment_count": counts["payments"],
            }
        )
    return rows
