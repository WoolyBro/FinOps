"""Workspaces: the shared ledgers, and the per-browser demo sandbox."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app import workspaces
from app.api.deps import get_agent_service
from app.database import get_db
from app.services.agent_service import AgentService

router = APIRouter(tags=["workspaces"])


@router.get("/workspaces")
def list_workspaces() -> dict:
    """Each shared ledger with how many clients, invoices and payments it holds."""
    rows = workspaces.overview()
    return {"count": len(rows), "workspaces": rows}


@router.post("/sandbox/reset")
def reset_sandbox(service: AgentService = Depends(get_agent_service)) -> dict:
    """Restore this browser's demo sandbox to the sample ledger.

    Only the sandbox named by the request is touched; every other browser's
    copy, and the shared ledgers, are left exactly as they are. Conversations
    about this sandbox are forgotten too, since they refer to figures that no
    longer exist.
    """
    workspace = workspaces.current()
    if workspace is None or not workspace.sandbox:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "not_a_sandbox",
                "detail": "Only a demo sandbox can be reset, and this request is not using one.",
            },
        )

    workspaces.reset_sandbox(workspace)
    cleared = service.reset_workspace(workspace.id)
    with get_db() as conn:
        counts = {
            "client_count": conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0],
            "invoice_count": conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0],
            "payment_count": conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0],
        }
    return {"status": "reset", **counts, "conversations_cleared": cleared}
