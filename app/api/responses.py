"""JSON encoding for the API.

The CLI fixes its own stdout encoding, but that fix is a property of a terminal
process and has nothing to do with HTTP. The API states its encoding explicitly
instead of inheriting a default: every money string carries a currency symbol,
and ₹ must survive the trip to the browser as UTF-8 with the charset declared
in the header.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.responses import JSONResponse


class UTF8JSONResponse(JSONResponse):
    """JSON, non-ASCII preserved, charset declared."""

    media_type = "application/json; charset=utf-8"

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
