"""The workspaces the dashboard can open, for its opening screen."""

from __future__ import annotations

from fastapi import APIRouter

from app import workspaces

router = APIRouter(tags=["workspaces"])


@router.get("/workspaces")
def list_workspaces() -> dict:
    """Each ledger with how many clients, invoices and payments it holds."""
    rows = workspaces.overview()
    return {"count": len(rows), "workspaces": rows}
