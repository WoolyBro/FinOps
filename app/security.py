"""Security helpers shared by the API and the runtime.

Three jobs, all of them about not handing a client something it should not
have:

* `resolve_document` refuses to serve a file from outside the directories this
  app owns, so a path that reaches the file-serving endpoints can never escape
  into the filesystem.
* `scrub` strips absolute filesystem paths out of anything on its way to a
  client. Server paths leak the directory layout and, on a developer machine,
  the operator's own name.
* `safe_detail` turns an exception into a message a stranger may read.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Fields that carry a server-side filesystem path and must never cross the
# HTTP boundary. The document itself is served through its own endpoint.
PATH_FIELDS = frozenset({"pdf_path", "receipt_path"})

# Windows (C:\...) and POSIX (/home/...) absolute paths appearing in free text.
_WINDOWS_PATH = re.compile(r"[A-Za-z]:\\[^\s'\"]+")
_POSIX_PATH = re.compile(r"(?<![\w.])/(?:home|Users|mnt|opt|srv|var|tmp)/[^\s'\"]+")


class UnsafePath(ValueError):
    """A path resolved outside the directories this application owns."""


def is_within(path: Path, directory: Path) -> bool:
    """True if `path` is inside `directory` once symlinks are resolved.

    `Path.resolve()` first, so `..` segments and symlinks cannot be used to
    step outside.
    """
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except (ValueError, OSError):
        return False


def resolve_document(path: Path | str, allowed_dirs: list[Path]) -> Path:
    """Return a path that is safe to serve, or raise.

    Paths reaching the document endpoints come from a database column. Today
    only this application writes that column, but "only we write it" is an
    assumption that quietly stops being true. Containment is checked at the
    point of use so it holds regardless.
    """
    candidate = Path(path)
    if not any(is_within(candidate, directory) for directory in allowed_dirs):
        raise UnsafePath(
            "Refusing to serve a document from outside the document directories."
        )

    resolved = candidate.resolve()
    if not resolved.is_file():
        raise UnsafePath("The document is not a readable file.")
    return resolved


def scrub(value: Any) -> Any:
    """Remove server filesystem paths from a structure bound for a client.

    Drops the known path-bearing fields entirely, replacing each with a
    boolean saying whether the document exists, and redacts any absolute path
    left in free text.
    """
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in PATH_FIELDS:
                # Keep the useful fact -- does the document exist -- and drop
                # the location, which is nobody's business but the server's.
                cleaned[key.replace("_path", "_available")] = bool(item)
                continue
            cleaned[key] = scrub(item)
        return cleaned
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, str):
        return redact_paths(value)
    return value


def redact_paths(text: str) -> str:
    """Replace absolute filesystem paths in free text with a placeholder."""
    text = _WINDOWS_PATH.sub("<path>", text)
    return _POSIX_PATH.sub("<path>", text)


def safe_detail(exc: BaseException, fallback: str) -> str:
    """An error message fit for a client.

    Exception text routinely contains paths, and sometimes connection strings.
    Anything that still looks like a path after redaction is dropped in favour
    of the fallback, rather than trusting the redaction to have caught
    everything.
    """
    text = redact_paths(str(exc)).strip()
    if not text or "<path>" in text:
        return fallback
    return text
