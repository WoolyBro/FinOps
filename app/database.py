"""SQLite schema and connection handling.

Design notes that matter for a billing system:

* Money is stored as an INTEGER in minor units (paise for INR, cents for USD).
  Never floats -- 0.1 + 0.2 problems in an invoice total are unacceptable.
* "Overdue" is never stored. It is derived from due_date and outstanding at read
  time, so it can never go stale while the app sits idle. Likewise `amount_paid`
  is not a column -- it is SUM(payments.amount_minor), so the ledger and the
  balance can never disagree.
* Invoice status is one of UNPAID / PARTIALLY_PAID / PAID / CANCELLED, and is
  maintained by the payment tools, never written by the model.
* Client names carry a normalised `name_key` with a UNIQUE index, so the agent
  cannot create "Rahul", "rahul " and "RAHUL" as three separate clients.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator

from app.config import DB_PATH, ensure_dirs

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    name_key    TEXT    NOT NULL,
    email       TEXT,
    phone       TEXT,
    address     TEXT,
    notes       TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_name_key ON clients(name_key);

CREATE TABLE IF NOT EXISTS invoices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number  TEXT    NOT NULL UNIQUE,
    client_id       INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    project         TEXT    NOT NULL,
    description     TEXT,
    amount_minor    INTEGER NOT NULL CHECK (amount_minor > 0),
    currency        TEXT    NOT NULL DEFAULT 'INR',
    issue_date      TEXT    NOT NULL,
    due_date        TEXT,
    status          TEXT    NOT NULL DEFAULT 'UNPAID'
                    CHECK (status IN ('UNPAID','PARTIALLY_PAID','PAID','CANCELLED')),
    pdf_path        TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_invoices_client ON invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);

CREATE TABLE IF NOT EXISTS payments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id    INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    amount_minor  INTEGER NOT NULL CHECK (amount_minor > 0),
    payment_date  TEXT    NOT NULL,
    method        TEXT,
    reference     TEXT,
    receipt_number TEXT   UNIQUE,
    receipt_path  TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);

CREATE TABLE IF NOT EXISTS reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id  INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    channel     TEXT    NOT NULL DEFAULT 'email',
    message     TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'DRAFT'
                CHECK (status IN ('DRAFT','APPROVED','SENT','CANCELLED')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    sent_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_reminders_invoice ON reminders(invoice_id);

-- Atomic sequences for human-facing document numbers.
CREATE TABLE IF NOT EXISTS counters (
    name   TEXT PRIMARY KEY,
    value  INTEGER NOT NULL DEFAULT 0
);
"""


def normalise_name(name: str) -> str:
    """Collapse a client name to a comparison key.

    "  Rahul   Sharma " and "rahul sharma" both become "rahul sharma".
    """
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def connect(db_path=None) -> sqlite3.Connection:
    """Open a connection with sane defaults for this app."""
    ensure_dirs()
    conn = sqlite3.connect(str(db_path or DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db(db_path=None) -> Iterator[sqlite3.Connection]:
    """Transactional connection: commits on success, rolls back on error."""
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path=None) -> None:
    """Create tables if they do not exist. Safe to call repeatedly."""
    with get_db(db_path) as conn:
        conn.executescript(SCHEMA)


def next_counter(conn: sqlite3.Connection, name: str) -> int:
    """Increment and return a named counter inside the caller's transaction."""
    conn.execute(
        "INSERT INTO counters(name, value) VALUES (?, 0) ON CONFLICT(name) DO NOTHING",
        (name,),
    )
    conn.execute("UPDATE counters SET value = value + 1 WHERE name = ?", (name,))
    row = conn.execute("SELECT value FROM counters WHERE name = ?", (name,)).fetchone()
    return int(row["value"])
