"""The FastAPI application.

    Browser -> React (Vite) -> FastAPI -> AgentService -> Strands -> tools -> SQLite

The frontend never talks to Strands. It talks to this, which talks to the
service layer. That boundary is what keeps an AgentCore deployment a change to
one service rather than a rewrite of the interface.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.middleware import WorkspaceMiddleware
from app.api.responses import UTF8JSONResponse
from app.api.routers import chat, commands, records, reports, workspaces
from app.database import init_db

API_PREFIX = "/api"

DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


class InsecureCorsConfiguration(RuntimeError):
    """The configured CORS policy would expose authenticated responses."""


def cors_origins() -> list[str]:
    """Allowed browser origins, overridable for a deployed frontend.

    A wildcard is refused rather than accepted, because this app sends
    credentialed requests: `*` combined with allow_credentials makes the
    browser echo whatever Origin it was given, which lets any site on the
    internet read a logged-in user's invoices. Failing at start-up is far
    better than shipping that.
    """
    configured = os.getenv("FF_CORS_ORIGINS", "").strip()
    if not configured:
        return DEFAULT_ORIGINS

    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    if any(origin == "*" for origin in origins):
        raise InsecureCorsConfiguration(
            "FF_CORS_ORIGINS may not contain '*': this API sends credentialed "
            "requests, and a wildcard origin with credentials would let any "
            "site read a user's billing data. List the exact origins instead."
        )
    return origins


log = logging.getLogger("freelanceflow.api")

TRUE_VALUES = ("1", "true", "yes", "on")


def static_dir() -> Path | None:
    """The built dashboard, if there is one to serve.

    In a deployment the API serves the dashboard from the same origin, so a
    judge opens one URL and the browser never makes a cross-origin call. In
    development Vite serves it instead and this finds nothing.
    """
    configured = os.getenv("FF_STATIC_DIR")
    directory = Path(configured) if configured else Path(__file__).resolve().parents[2] / "frontend" / "dist"
    return directory if (directory / "index.html").is_file() else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Safe to run repeatedly; makes a fresh checkout serve immediately.
    init_db()
    if os.getenv("FF_SEED_DEMO", "").strip().lower() in TRUE_VALUES:
        from app.seed import seed_if_empty

        seeded = seed_if_empty()
        if seeded:
            log.info("seeded demo ledger: %s", seeded)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="FreelanceFlow",
        description=(
            "Billing operations for freelancers. Every financial figure is "
            "derived from the invoice and payment ledger."
        ),
        version="0.6.0",
        default_response_class=UTF8JSONResponse,
        lifespan=lifespan,
    )

    # Added first so it sits inside CORS: a preflight is answered before any
    # workspace is opened, and a 400 for an unknown workspace still carries
    # the CORS headers the browser needs to read it.
    app.add_middleware(WorkspaceMiddleware)
    # Added first so it sits inside CORS: a preflight is answered before any
    # workspace is opened, and a 400 for an unknown workspace still carries
    # the CORS headers the browser needs to read it.
    app.add_middleware(WorkspaceMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_credentials=True,
        # PATCH is the client-edit endpoint; leaving it out made the browser's
        # preflight refuse every inline edit on the client page.
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(chat.router, prefix=API_PREFIX)
    app.include_router(commands.router, prefix=API_PREFIX)
    app.include_router(records.router, prefix=API_PREFIX)
    app.include_router(reports.router, prefix=API_PREFIX)
    app.include_router(workspaces.router, prefix=API_PREFIX)

    _install_error_handlers(app)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "service": "freelanceflow"}

    # Mounted last, so /api and /docs always win. The dashboard uses hash
    # routes (#/invoices), so the server only ever needs to serve index.html
    # and the built assets.
    dashboard = static_dir()
    if dashboard is not None:
        app.mount("/", StaticFiles(directory=dashboard, html=True), name="dashboard")

    return app


def _install_error_handlers(app: FastAPI) -> None:
    """One error shape for every failure: {"error": code, "detail": text}.

    Without this, a 404 raised by a handler, a validation failure and an
    unexpected exception would each come back shaped differently, and the
    frontend would need three ways to read the same thing.
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            body = detail
        else:
            body = {"error": _code_for(exc.status_code), "detail": str(detail)}
        return UTF8JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        problems = [
            {
                "field": ".".join(str(part) for part in err.get("loc", [])),
                "message": err.get("msg", "invalid"),
            }
            for err in exc.errors()
        ]
        summary = "; ".join(f"{p['field']}: {p['message']}" for p in problems)
        return UTF8JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": "invalid_request",
                "detail": summary or "The request body was not valid.",
                "problems": problems,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        # Never leak internals to a browser; the traceback is in the log.
        return UTF8JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "detail": "Something went wrong handling this request.",
            },
        )


def _code_for(status_code: int) -> str:
    return {
        400: "bad_request",
        404: "not_found",
        409: "conflict",
        405: "method_not_allowed",
        422: "invalid_request",
        502: "document_unavailable",
        503: "agent_unavailable",
    }.get(status_code, "error")


app = create_app()
