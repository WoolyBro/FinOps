"""The FastAPI application.

    Browser -> Next.js -> FastAPI -> AgentService -> Strands -> tools -> SQLite

The frontend never talks to Strands. It talks to this, which talks to the
service layer. That boundary is what keeps an AgentCore deployment a change to
one service rather than a rewrite of the interface.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.responses import UTF8JSONResponse
from app.api.routers import chat, records, reports
from app.database import init_db

API_PREFIX = "/api"

DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def cors_origins() -> list[str]:
    """Allowed browser origins, overridable for a deployed frontend."""
    configured = os.getenv("FF_CORS_ORIGINS", "").strip()
    if not configured:
        return DEFAULT_ORIGINS
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Safe to run repeatedly; makes a fresh checkout serve immediately.
    init_db()
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(chat.router, prefix=API_PREFIX)
    app.include_router(records.router, prefix=API_PREFIX)
    app.include_router(reports.router, prefix=API_PREFIX)

    _install_error_handlers(app)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "service": "freelanceflow"}

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
        405: "method_not_allowed",
        422: "invalid_request",
        502: "document_unavailable",
        503: "agent_unavailable",
    }.get(status_code, "error")


app = create_app()
