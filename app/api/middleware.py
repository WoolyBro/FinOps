"""Put each request in the workspace it asked for.

Pure ASGI rather than BaseHTTPMiddleware: the workspace is a context variable,
and it has to be set in the same context the endpoint -- and, through Strands,
the agent's tool calls -- will run in.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs

from app import workspaces


class WorkspaceMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        requested = _requested_workspace(scope)
        if not requested:
            return await self.app(scope, receive, send)

        try:
            token = workspaces.activate(requested)
        except workspaces.UnknownWorkspace as exc:
            return await _reject(send, str(exc))

        try:
            await self.app(scope, receive, send)
        finally:
            workspaces.deactivate(token)


def _requested_workspace(scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == workspaces.HEADER.encode():
            return value.decode("latin-1").strip() or None
    query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
    values = query.get(workspaces.QUERY_PARAM)
    return values[0].strip() if values and values[0].strip() else None


async def _reject(send, detail: str) -> None:
    body = json.dumps({"error": "unknown_workspace", "detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 400,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
