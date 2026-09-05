"""Structured logging for the AgentCore Runtime.

AgentCore ships container stdout to CloudWatch Logs. Plain prose lines are hard
to query there, so every log record is emitted as one JSON object on one line --
CloudWatch Logs Insights can then filter on fields directly.

Money never appears in these logs as a formatted string, and client names never
appear at all. What gets logged is which tool ran, whether it succeeded, and how
long it took. A log line is not a place to leak a client's billing details.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

LOGGER_NAME = "freelanceflow"

# Fields the standard LogRecord carries that we do not want repeated inside the
# JSON payload, so `extra=` fields can be picked out cleanly.
_RESERVED = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"asctime", "message", "taskName"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with any `extra=` fields merged in."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)
            )
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # default=str so a stray Decimal or Path cannot take down logging.
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str | None = None) -> logging.Logger:
    """Send structured logs to stdout. Safe to call more than once."""
    resolved = (level or os.getenv("FF_LOG_LEVEL", "INFO")).upper()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(resolved)

    # Bedrock retries are chatty at INFO and drown out the agent's own lines.
    for noisy in ("botocore", "boto3", "urllib3", "opentelemetry"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger(LOGGER_NAME)


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def tool_call_summary(tool_calls: list) -> list[dict]:
    """Reduce a tool trace to what is safe and useful to log.

    Names, outcomes and durations -- never arguments, which carry client names
    and amounts.
    """
    return [
        {
            "tool": call.get("tool"),
            "status": call.get("status"),
            "failed": bool(call.get("error")),
            "duration_seconds": call.get("duration_seconds"),
        }
        for call in tool_calls
    ]
