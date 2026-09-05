"""Model selection.

Bedrock is the target for the AWS submission, but the deterministic half of this
app (database, tools, documents) must be developable and testable before AWS
credentials exist. So the provider is resolved at runtime:

    FF_MODEL_PROVIDER=bedrock    -> Amazon Bedrock (default when AWS creds resolve)
    FF_MODEL_PROVIDER=anthropic  -> Anthropic API directly (ANTHROPIC_API_KEY)
    FF_MODEL_PROVIDER=ollama     -> local Ollama, for offline work
    FF_MODEL_PROVIDER=auto       -> Bedrock if credentials resolve, else Anthropic

Nothing else in the codebase knows or cares which one is in use.
"""

from __future__ import annotations

import os

# Sensible defaults per provider; override with FF_MODEL_ID.
BEDROCK_MODEL_ID = "global.anthropic.claude-sonnet-4-6"
ANTHROPIC_MODEL_ID = "claude-sonnet-4-6"
OLLAMA_MODEL_ID = "llama3.1"


class ModelNotConfigured(RuntimeError):
    """Raised when no usable model provider could be resolved."""


def aws_credentials_available() -> bool:
    """True if botocore can resolve credentials from any source."""
    try:
        import botocore.session

        return botocore.session.get_session().get_credentials() is not None
    except Exception:
        return False


def resolve_provider() -> str:
    """Decide which provider to use, honouring FF_MODEL_PROVIDER."""
    choice = os.getenv("FF_MODEL_PROVIDER", "auto").strip().lower()
    if choice != "auto":
        return choice
    if aws_credentials_available():
        return "bedrock"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise ModelNotConfigured(
        "No model provider configured.\n"
        "  For Bedrock: configure AWS credentials (aws configure) and request\n"
        "    access to Claude in the Bedrock console.\n"
        "  For the Anthropic API: set ANTHROPIC_API_KEY.\n"
        "  To pin one explicitly, set FF_MODEL_PROVIDER=bedrock|anthropic|ollama."
    )


def build_model():
    """Return a configured Strands model instance."""
    provider = resolve_provider()
    model_id = os.getenv("FF_MODEL_ID")

    if provider == "bedrock":
        from strands.models import BedrockModel

        return BedrockModel(
            model_id=model_id or BEDROCK_MODEL_ID,
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            temperature=0.2,
        )

    if provider == "anthropic":
        from strands.models.anthropic import AnthropicModel

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ModelNotConfigured(
                "FF_MODEL_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set."
            )
        return AnthropicModel(
            client_args={"api_key": api_key},
            model_id=model_id or ANTHROPIC_MODEL_ID,
            max_tokens=4096,
            params={"temperature": 0.2},
        )

    if provider == "ollama":
        from strands.models.ollama import OllamaModel

        return OllamaModel(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model_id=model_id or OLLAMA_MODEL_ID,
        )

    raise ModelNotConfigured(f"Unknown FF_MODEL_PROVIDER: {provider!r}")
