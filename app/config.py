"""Central configuration. Everything reads paths and settings from here."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional at runtime
    pass

# Project root = the directory containing this package.
ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.getenv("FF_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.getenv("FF_DB_PATH", DATA_DIR / "freelanceflow.db"))
DOCS_DIR = Path(os.getenv("FF_DOCS_DIR", DATA_DIR / "documents"))

# Default currency for new invoices. ISO 4217.
DEFAULT_CURRENCY = os.getenv("FF_CURRENCY", "INR")

# Business identity printed on invoices and receipts (phase 3).
BUSINESS_NAME = os.getenv("FF_BUSINESS_NAME", "FreelanceFlow User")
BUSINESS_EMAIL = os.getenv("FF_BUSINESS_EMAIL", "")

# Invoice number prefix, e.g. FF-0007.
INVOICE_PREFIX = os.getenv("FF_INVOICE_PREFIX", "FF")
RECEIPT_PREFIX = os.getenv("FF_RECEIPT_PREFIX", "RC")


def ensure_dirs() -> None:
    """Create the directories the app writes into."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
