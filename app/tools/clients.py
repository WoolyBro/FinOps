"""Client tools exposed to the Strands agent.

Every tool returns a dict with an explicit "status" key. That matters more than
it looks: it is what lets the agent distinguish "no such client" from "lookup
failed" and ask the user instead of inventing a client record.
"""

from __future__ import annotations

from strands import tool

from app.database import get_db, normalise_name
from app.models import client_to_dict


@tool
def find_client(name: str) -> dict:
    """Look up a client by name.

    Matches case-insensitively, first on the full name and then on a partial
    match, so "rahul" finds "Rahul Sharma".

    Args:
        name: The client's name or part of it.

    Returns:
        status "found" with the client, "not_found" if there is no match, or
        "ambiguous" with a list of candidates when several clients match.
    """
    key = normalise_name(name)
    if not key:
        return {"status": "error", "error": "A client name is required."}

    with get_db() as conn:
        exact = conn.execute(
            "SELECT * FROM clients WHERE name_key = ?", (key,)
        ).fetchone()
        if exact:
            return {"status": "found", "client": client_to_dict(exact)}

        partial = conn.execute(
            "SELECT * FROM clients WHERE name_key LIKE ? ORDER BY name",
            (f"%{key}%",),
        ).fetchall()

    if not partial:
        return {
            "status": "not_found",
            "searched_for": name,
            "hint": "Ask the user whether to create this client before continuing.",
        }
    if len(partial) == 1:
        return {"status": "found", "client": client_to_dict(partial[0])}
    return {
        "status": "ambiguous",
        "searched_for": name,
        "matches": [client_to_dict(r) for r in partial],
        "hint": "Ask the user which client they meant.",
    }


@tool
def create_client(
    name: str,
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    notes: str | None = None,
) -> dict:
    """Create a new client.

    Refuses to create a duplicate: if a client with the same name already
    exists, the existing record is returned instead of a second copy.

    Args:
        name: The client's full name or company name. Required.
        email: Email address, used later for invoices and reminders.
        phone: Phone number.
        address: Billing address printed on invoices.
        notes: Any free-form note about the client.

    Returns:
        status "created" with the new client, or "already_exists" with the
        client that was already on file.
    """
    key = normalise_name(name)
    if not key:
        return {"status": "error", "error": "A client name is required."}

    with get_db() as conn:
        existing = conn.execute(
            "SELECT * FROM clients WHERE name_key = ?", (key,)
        ).fetchone()
        if existing:
            return {
                "status": "already_exists",
                "client": client_to_dict(existing),
            }

        cur = conn.execute(
            """INSERT INTO clients (name, name_key, email, phone, address, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name.strip(), key, email, phone, address, notes),
        )
        row = conn.execute(
            "SELECT * FROM clients WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return {"status": "created", "client": client_to_dict(row)}


@tool
def list_clients(limit: int = 50) -> dict:
    """List the clients on file, most recently added first.

    Args:
        limit: Maximum number of clients to return.

    Returns:
        status "ok" with a count and the list of clients.
    """
    limit = max(1, min(int(limit or 50), 200))
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM clients ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return {
        "status": "ok",
        "count": len(rows),
        "clients": [client_to_dict(r) for r in rows],
    }


@tool
def update_client(client_id: int, field: str, value: str) -> dict:
    """Update one field on an existing client.

    Args:
        client_id: The numeric id of the client, from find_client.
        field: One of name, email, phone, address, notes.
        value: The new value.

    Returns:
        status "updated" with the refreshed client record.
    """
    allowed = {"name", "email", "phone", "address", "notes"}
    if field not in allowed:
        return {
            "status": "error",
            "error": f"Cannot update '{field}'. Allowed fields: {sorted(allowed)}",
        }

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        if not row:
            return {"status": "not_found", "client_id": client_id}

        if field == "name":
            key = normalise_name(value)
            if not key:
                return {"status": "error", "error": "Name cannot be empty."}
            clash = conn.execute(
                "SELECT id FROM clients WHERE name_key = ? AND id != ?",
                (key, client_id),
            ).fetchone()
            if clash:
                return {
                    "status": "error",
                    "error": f"Another client is already named '{value}'.",
                }
            conn.execute(
                "UPDATE clients SET name = ?, name_key = ? WHERE id = ?",
                (value.strip(), key, client_id),
            )
        else:
            conn.execute(
                f"UPDATE clients SET {field} = ? WHERE id = ?", (value, client_id)
            )

        updated = conn.execute(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        return {"status": "updated", "client": client_to_dict(updated)}
