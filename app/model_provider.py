"""Model selection.

Three supported providers, all through Strands: Google Gemini, Amazon Bedrock
and Ollama. The Anthropic and OpenAI APIs are not supported paths, and nothing
here reads an ANTHROPIC_API_KEY -- a test asserts it.

On Bedrock, the default model is Amazon Nova, AWS's own first-party model family. It was chosen over Anthropic's Bedrock models for a concrete,
practical reason: first-party AWS models carry no separate usage-terms
agreement to accept, only the ordinary one-click Bedrock model-access grant.
Anthropic's Bedrock models need that agreement accepted before
`authorizationStatus` will ever move off NOT_AUTHORIZED, which is a second gate
this project does not need. Override with FF_MODEL_ID for any other model this
account has been granted -- nothing else in the codebase assumes a vendor.

    FF_MODEL_PROVIDER=bedrock  -> Amazon Bedrock.
    FF_MODEL_PROVIDER=gemini   -> Google Gemini through Strands' GeminiModel,
                                  with a key from GEMINI_API_KEY. The free tier
                                  is enough for development and a demo.
    FF_MODEL_PROVIDER=ollama   -> a local model, for development offline.
    FF_MODEL_PROVIDER=auto     -> Gemini if a key is set, then Bedrock if AWS
                                  credentials resolve, then Ollama if running.

A Gemini key outranks AWS credentials in auto mode because the key exists for
one purpose only, while AWS credentials are often on a machine for unrelated
reasons -- their presence says nothing about Bedrock model access.

Nothing else in the codebase knows or cares which one is in use, which is what
keeps the AgentCore deployment a configuration change rather than a rewrite.
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

# Imported for its side effect: loading .env. Provider settings and keys are
# read here, and an entry point that never touched app.config -- live_check's
# preflight, for one -- would otherwise report a configured key as missing.
import app.config  # noqa: F401
from app.aws_config import RegionNotConfigured, require_region, resolve_region

# Sensible defaults per provider; override with FF_MODEL_ID.
# apac.amazon.nova-pro-v1:0 is the cross-region inference profile that serves
# ap-south-1 (Mumbai) and the rest of AWS's Asia-Pacific grouping.
BEDROCK_MODEL_ID = "apac.amazon.nova-pro-v1:0"
GEMINI_MODEL_ID = "gemini-3.5-flash-lite"
OLLAMA_MODEL_ID = "llama3.1"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"

PROVIDERS = ("bedrock", "gemini", "ollama")

DEFAULT_MODEL_IDS = {
    "bedrock": BEDROCK_MODEL_ID,
    "gemini": GEMINI_MODEL_ID,
    "ollama": OLLAMA_MODEL_ID,
}

GEMINI_KEY_HELP = (
    "Gemini is selected but GEMINI_API_KEY is not set. Get a free key at "
    "https://aistudio.google.com/apikey and add GEMINI_API_KEY=... to .env."
)

_NOT_CONFIGURED = (
    "No model provider is available.\n"
    "  Google Gemini: set GEMINI_API_KEY in .env (free key from\n"
    "    https://aistudio.google.com/apikey).\n"
    "  Amazon Bedrock: configure AWS credentials and enable Amazon Nova\n"
    "    under Bedrock > Model access.\n"
    "  Ollama: start Ollama on {ollama_host} and pull a model.\n"
    "  To pin one explicitly, set FF_MODEL_PROVIDER=gemini|bedrock|ollama."
)


class ModelNotConfigured(RuntimeError):
    """Raised when no usable model provider could be resolved."""


def ollama_host() -> str:
    return os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)


def gemini_api_key() -> str | None:
    """The Gemini key, if one is configured. Never logged or returned by the API."""
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    return key or None


GEMINI_THINKING_LEVELS = ("minimal", "low", "medium", "high")


def gemini_params() -> dict:
    """Generation settings for Gemini.

    Thinking defaults to "low". Newer Gemini models reason at length before
    every call by default, and an agent turn is several calls -- find the
    client, read the balance, answer -- so default thinking multiplies into a
    reply that takes over a minute. Choosing the right tool from a precise
    docstring needs little deliberation; the tools do the careful work.
    FF_GEMINI_THINKING=off sends no thinking setting, for models without one.
    """
    params: dict = {"temperature": 0.2}
    level = os.getenv("FF_GEMINI_THINKING", "low").strip().lower()
    if level in GEMINI_THINKING_LEVELS:
        params["thinking_config"] = {"thinking_level": level.upper()}
    return params


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
                f"This project supports {', '.join(PROVIDERS)}."
            )
        return choice

    if gemini_api_key():
        return "gemini"
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

    if provider == "gemini":
        key = gemini_api_key()
        if not key:
            raise ModelNotConfigured(GEMINI_KEY_HELP)
        from strands.models.gemini import GeminiModel

        return GeminiModel(
            client_args={"api_key": key},
            model_id=model_id or GEMINI_MODEL_ID,
            params=gemini_params(),
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

    model_id = os.getenv("FF_MODEL_ID") or DEFAULT_MODEL_IDS[provider]

    if provider == "gemini" and not gemini_api_key():
        return {
            "available": False,
            "provider": provider,
            "model_id": model_id,
            "region": None,
            "detail": GEMINI_KEY_HELP,
        }

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
