"""Model selection.

This project runs Claude on Amazon Bedrock. It does not use the Anthropic API
directly, and nothing here requires an ANTHROPIC_API_KEY.

    FF_MODEL_PROVIDER=bedrock  -> Amazon Bedrock. Production, and the default
                                  whenever AWS credentials resolve.
    FF_MODEL_PROVIDER=ollama   -> a local model, for development without AWS.
    FF_MODEL_PROVIDER=auto     -> Bedrock if AWS credentials resolve, otherwise
                                  Ollama if it is running locally.

Nothing else in the codebase knows or cares which one is in use, which is what
keeps the AgentCore deployment a configuration change rather than a rewrite.
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

from app.aws_config import RegionNotConfigured, require_region, resolve_region

# Sensible defaults per provider; override with FF_MODEL_ID.
BEDROCK_MODEL_ID = "global.anthropic.claude-sonnet-4-6"
OLLAMA_MODEL_ID = "llama3.1"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"

PROVIDERS = ("bedrock", "ollama")

_NOT_CONFIGURED = (
    "No model provider is available.\n"
    "  Production path -- Amazon Bedrock:\n"
    "    configure AWS credentials (aws configure, a profile, or an SSO\n"
    "    session) and enable Anthropic Claude under Bedrock > Model access.\n"
    "  Local path -- Ollama:\n"
    "    start Ollama on {ollama_host} and pull a model.\n"
    "  To pin one explicitly, set FF_MODEL_PROVIDER=bedrock|ollama."
)


class ModelNotConfigured(RuntimeError):
    """Raised when no usable model provider could be resolved."""


def ollama_host() -> str:
    return os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)


def aws_credentials_available() -> bool:
    """True if botocore can resolve credentials from any source."""
    try:
        import botocore.session

        return botocore.session.get_session().get_credentials() is not None
    except Exception:
        return False


def ollama_available(timeout: float = 0.5) -> bool:
    """True if something is listening where Ollama should be.

    Only consulted when resolving automatically. Asking for Ollama explicitly
    skips this, so a slow start-up is not mistaken for a missing install.
    """
    parsed = urlparse(ollama_host())
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 11434)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def resolve_provider() -> str:
    """Decide which provider to use, honouring FF_MODEL_PROVIDER."""
    choice = os.getenv("FF_MODEL_PROVIDER", "auto").strip().lower()

    if choice and choice != "auto":
        if choice not in PROVIDERS:
            raise ModelNotConfigured(
                f"Unknown FF_MODEL_PROVIDER: {choice!r}. "
                f"This project supports {' and '.join(PROVIDERS)}."
            )
        return choice

    if aws_credentials_available():
        return "bedrock"
    if ollama_available():
        return "ollama"
    raise ModelNotConfigured(_NOT_CONFIGURED.format(ollama_host=ollama_host()))


def build_model():
    """Return a configured Strands model instance."""
    provider = resolve_provider()
    model_id = os.getenv("FF_MODEL_ID")

    if provider == "bedrock":
        from strands.models import BedrockModel

        # Explicit, never inherited. A model enabled in one region is not
        # enabled in another, and guessing turns that into an opaque
        # AccessDenied at the first inference call instead of a clear error here.
        try:
            region = require_region()
        except RegionNotConfigured as exc:
            raise ModelNotConfigured(str(exc)) from exc

        return BedrockModel(
            model_id=model_id or BEDROCK_MODEL_ID,
            region_name=region,
            temperature=0.2,
        )

    if provider == "ollama":
        from strands.models.ollama import OllamaModel

        return OllamaModel(
            host=ollama_host(),
            model_id=model_id or OLLAMA_MODEL_ID,
        )

    raise ModelNotConfigured(f"Unknown FF_MODEL_PROVIDER: {provider!r}")


def provider_status() -> dict:
    """Describe what the app can currently talk to, for the API and the UI.

    The frontend uses this to show an honest "not configured" state instead of
    pretending a model is available.
    """
    try:
        provider = resolve_provider()
    except ModelNotConfigured as exc:
        return {
            "available": False,
            "provider": None,
            "model_id": None,
            "detail": str(exc),
        }

    model_id = os.getenv("FF_MODEL_ID") or (
        BEDROCK_MODEL_ID if provider == "bedrock" else OLLAMA_MODEL_ID
    )

    region = resolve_region()
    if provider == "bedrock" and not region:
        return {
            "available": False,
            "provider": provider,
            "model_id": model_id,
            "region": None,
            "detail": (
                "Bedrock is selected but no AWS region is configured. "
                "Set FF_AWS_REGION."
            ),
        }

    return {
        "available": True,
        "provider": provider,
        "model_id": model_id,
        "region": region if provider == "bedrock" else None,
        "detail": None,
    }
