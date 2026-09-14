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

Sandboxes
---------
A hosted demo is shared: every judge reaches the same server. So each browser
gets a *sandbox* -- a private copy of the sample ledger, named
`sbx-<32 hex>`, created from a template the first time that id is seen. A
judge's payments persist across refreshes, so they can confirm a change really
landed, and never appear in anyone else's copy. Resetting a sandbox restores
the template in place: Rahul's invoice is unpaid again, invoice numbering
starts over, and the documents generated since are gone.

Sandboxes are created lazily rather than issued, so a host restart that wipes
the disk costs nothing: the browser's id simply maps to a fresh copy. Unused
sandboxes expire, and their number is capped.
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from app.config import ROOT
from app.dates import today_iso

# Where workspace folders live. Read at call time (not bound at import) so
# tests can point it at a temporary directory.
WORKSPACES_ROOT = Path(os.getenv("FF_WORKSPACES_DIR", ROOT / "data"))

HEADER = "x-ff-workspace"
QUERY_PARAM = "workspace"


SANDBOX_ID = re.compile(r"^sbx-[0-9a-f]{32}$")
TEMPLATE_DIR = "_template"


class UnknownWorkspace(ValueError):
    """The request named a workspace that does not exist."""


class NotASandbox(ValueError):
    """Only a sandbox can be reset; the shared ledgers never are."""


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    description: str
    sandbox: bool = False

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
# Serialises template builds, sandbox creation and resets. All are brief file
# operations, and one lock keeps a reset from copying a half-built template.
_sandbox_lock = threading.RLock()
_last_touched: dict[str, float] = {}


def sandbox_ttl_seconds() -> float:
    return float(os.getenv("FF_SANDBOX_TTL_HOURS", "24")) * 3600


def sandbox_limit() -> int:
    return int(os.getenv("FF_SANDBOX_MAX", "500"))


def get(workspace_id: str) -> Workspace:
    key = (workspace_id or "").strip().lower() if isinstance(workspace_id, str) else ""
    if key in WORKSPACES:
        return WORKSPACES[key]
    if SANDBOX_ID.match(key):
        return Workspace(
            id=key,
            name="Demo sandbox",
            description="A private copy of the sample ledger for one browser.",
            sandbox=True,
        )
    raise UnknownWorkspace(
        f"Unknown workspace {workspace_id!r}. Use one of: {', '.join(WORKSPACES)}, "
        "or a sandbox id of the form sbx-<32 hex characters>."
    )


def current() -> Workspace | None:
    """The workspace this request is working in, or None outside a request."""
    return _current.get()


# --- sandboxes -------------------------------------------------------------------


def _template_db() -> Path:
    """The seeded sample ledger every sandbox is copied from.

    Rebuilt when the date changes, because the seed is dated relative to today:
    a template from last week would make every overdue figure a week stale.
    """
    root = WORKSPACES_ROOT / TEMPLATE_DIR
    db = root / "freelanceflow.db"
    stamp = root / "seeded_on"
    today = today_iso()
    with _sandbox_lock:
        if db.exists() and stamp.exists() and stamp.read_text(encoding="utf-8").strip() == today:
            return db

        root.mkdir(parents=True, exist_ok=True)
        if db.exists():
            db.unlink()
        builder = Workspace(id=TEMPLATE_DIR, name="template", description="")
        token = _current.set(builder)
        try:
            from app.seed import seed  # local: seed imports the tools, which import us

            seed()
        finally:
            _current.reset(token)
        _initialised.add(db)
        stamp.write_text(today, encoding="utf-8")
        return db


def _copy_template_into(workspace: Workspace) -> None:
    """Overwrite the workspace's ledger with the template, and clear its documents.

    Uses SQLite's backup API rather than a file copy: it replaces the database
    contents in place, so it works even while another request holds the file
    open, which a delete-and-copy would not on Windows.
    """
    template = _template_db()
    workspace.root.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(str(template))
    target = sqlite3.connect(str(workspace.db_path))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    for directory in (workspace.invoices_dir, workspace.receipts_dir):
        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True, exist_ok=True)


def _last_used(root: Path) -> float:
    db = root / "freelanceflow.db"
    try:
        return (db if db.exists() else root).stat().st_mtime
    except OSError:
        return 0.0


def _prune_sandboxes(keep: Path) -> None:
    """Delete expired sandboxes, then the least recently used beyond the cap."""
    if not WORKSPACES_ROOT.exists():
        return
    now = time.time()
    others = [p for p in WORKSPACES_ROOT.glob("sbx-*") if p.is_dir() and p != keep]
    doomed = [p for p in others if now - _last_used(p) > sandbox_ttl_seconds()]
    survivors = sorted((p for p in others if p not in doomed), key=_last_used)
    excess = len(survivors) + 1 - sandbox_limit()  # +1 for the one being kept
    if excess > 0:
        doomed.extend(survivors[:excess])
    for root in doomed:
        shutil.rmtree(root, ignore_errors=True)
        _last_touched.pop(root.name, None)


def _touch(workspace: Workspace) -> None:
    """Mark a sandbox as in use, at most every five minutes, so reads count too."""
    now = time.time()
    if now - _last_touched.get(workspace.id, 0) < 300:
        return
    _last_touched[workspace.id] = now
    try:
        os.utime(workspace.db_path, None)
    except OSError:
        pass


def reset_sandbox(workspace: Workspace) -> None:
    """Restore a sandbox to the sample ledger. Refuses anything that is not one."""
    if not workspace.sandbox:
        raise NotASandbox(
            f"The {workspace.id!r} ledger is shared and is never reset from the dashboard."
        )
    with _sandbox_lock:
        _copy_template_into(workspace)


def _ensure_ready(workspace: Workspace) -> None:
    """Create the folders and schema the first time a workspace is used."""
    if workspace.sandbox:
        # Checked on disk, not in the cache: an expired sandbox may have been
        # deleted and its id come back.
        if workspace.db_path.exists():
            _touch(workspace)
            return
        with _sandbox_lock:
            if not workspace.db_path.exists():
                _copy_template_into(workspace)
                _initialised.add(workspace.db_path)
                _prune_sandboxes(keep=workspace.root)
        return
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
