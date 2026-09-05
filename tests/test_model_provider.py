"""Provider resolution: Bedrock in production, Ollama locally, Anthropic never.

This project runs Claude through Amazon Bedrock. The Anthropic API is not a
supported path, and no part of the app may require an ANTHROPIC_API_KEY.
"""

import pytest

from app import model_provider
from app.model_provider import (
    ModelNotConfigured,
    provider_status,
    resolve_provider,
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Start from no provider configuration at all."""
    for var in (
        "FF_MODEL_PROVIDER",
        "FF_MODEL_ID",
        "ANTHROPIC_API_KEY",
        "OLLAMA_HOST",
        "FF_AWS_REGION",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
    ):
        monkeypatch.delenv(var, raising=False)


def no_aws(monkeypatch):
    monkeypatch.setattr(model_provider, "aws_credentials_available", lambda: False)


def with_aws(monkeypatch):
    monkeypatch.setattr(model_provider, "aws_credentials_available", lambda: True)


def no_ollama(monkeypatch):
    monkeypatch.setattr(model_provider, "ollama_available", lambda timeout=0.5: False)


def with_ollama(monkeypatch):
    monkeypatch.setattr(model_provider, "ollama_available", lambda timeout=0.5: True)


# --- automatic resolution ---------------------------------------------------


def test_bedrock_wins_when_aws_credentials_resolve(monkeypatch):
    with_aws(monkeypatch)
    with_ollama(monkeypatch)
    assert resolve_provider() == "bedrock"


def test_falls_back_to_ollama_when_there_is_no_aws(monkeypatch):
    no_aws(monkeypatch)
    with_ollama(monkeypatch)
    assert resolve_provider() == "ollama"


def test_raises_when_neither_is_available(monkeypatch):
    no_aws(monkeypatch)
    no_ollama(monkeypatch)
    with pytest.raises(ModelNotConfigured) as exc:
        resolve_provider()
    assert "Bedrock" in str(exc.value)
    assert "Ollama" in str(exc.value)


# --- the Anthropic API is not a path out of here ----------------------------


def test_an_anthropic_key_does_not_make_a_provider_available(monkeypatch):
    """The key being present must change nothing. Bedrock is the only cloud path."""
    no_aws(monkeypatch)
    no_ollama(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-be-ignored")

    with pytest.raises(ModelNotConfigured):
        resolve_provider()


def test_anthropic_is_not_a_selectable_provider(monkeypatch):
    monkeypatch.setenv("FF_MODEL_PROVIDER", "anthropic")
    with pytest.raises(ModelNotConfigured) as exc:
        resolve_provider()
    assert "bedrock" in str(exc.value)


def test_the_module_never_reads_the_anthropic_key():
    """A grep-style guard, so the dependency cannot creep back in.

    The docstring is allowed to say the key is not needed; what must not exist
    is code that reads it or builds an AnthropicModel.
    """
    from pathlib import Path

    source = Path(model_provider.__file__).read_text(encoding="utf-8")
    assert 'getenv("ANTHROPIC_API_KEY")' not in source
    assert "AnthropicModel" not in source
    assert "strands.models.anthropic" not in source


def test_supported_providers_are_exactly_bedrock_and_ollama():
    assert model_provider.PROVIDERS == ("bedrock", "ollama")


# --- explicit selection -----------------------------------------------------


def test_explicit_bedrock_does_not_need_a_credential_probe(monkeypatch):
    no_aws(monkeypatch)
    no_ollama(monkeypatch)
    monkeypatch.setenv("FF_MODEL_PROVIDER", "bedrock")
    assert resolve_provider() == "bedrock"


def test_explicit_ollama_skips_the_reachability_probe(monkeypatch):
    """Asking for Ollama explicitly must not fail because it is still starting."""
    no_aws(monkeypatch)
    monkeypatch.setattr(
        model_provider,
        "ollama_available",
        lambda timeout=0.5: pytest.fail("probe should not run for an explicit choice"),
    )
    monkeypatch.setenv("FF_MODEL_PROVIDER", "ollama")
    assert resolve_provider() == "ollama"


def test_unknown_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("FF_MODEL_PROVIDER", "openai")
    with pytest.raises(ModelNotConfigured):
        resolve_provider()


# --- status, which the API and UI report ------------------------------------


def test_status_when_unavailable(monkeypatch):
    no_aws(monkeypatch)
    no_ollama(monkeypatch)
    status = provider_status()
    assert status["available"] is False
    assert status["provider"] is None
    assert "Bedrock" in status["detail"]


def test_status_when_bedrock_is_available(monkeypatch):
    with_aws(monkeypatch)
    monkeypatch.setenv("FF_AWS_REGION", "ap-south-1")
    status = provider_status()
    assert status["available"] is True
    assert status["provider"] == "bedrock"
    assert status["model_id"] == model_provider.BEDROCK_MODEL_ID
    assert status["region"] == "ap-south-1"
    assert status["detail"] is None


def test_bedrock_without_a_region_is_not_available(monkeypatch):
    """Credentials alone are not enough -- a model is enabled per region."""
    with_aws(monkeypatch)
    status = provider_status()
    assert status["available"] is False
    assert status["provider"] == "bedrock"
    assert "region" in status["detail"].lower()


def test_building_a_bedrock_model_without_a_region_fails_clearly(monkeypatch):
    monkeypatch.setenv("FF_MODEL_PROVIDER", "bedrock")
    with pytest.raises(ModelNotConfigured) as exc:
        model_provider.build_model()
    assert "region" in str(exc.value).lower()


def test_ollama_status_does_not_require_a_region(monkeypatch):
    monkeypatch.setenv("FF_MODEL_PROVIDER", "ollama")
    status = provider_status()
    assert status["available"] is True
    assert status["region"] is None


def test_status_honours_an_overridden_model_id(monkeypatch):
    with_aws(monkeypatch)
    monkeypatch.setenv("FF_AWS_REGION", "ap-south-1")
    monkeypatch.setenv("FF_MODEL_ID", "global.anthropic.claude-haiku-4-5")
    assert provider_status()["model_id"] == "global.anthropic.claude-haiku-4-5"


# --- building the model -----------------------------------------------------


def test_builds_a_bedrock_model(monkeypatch):
    monkeypatch.setenv("FF_MODEL_PROVIDER", "bedrock")
    monkeypatch.setenv("FF_AWS_REGION", "ap-south-1")
    from strands.models import BedrockModel

    model = model_provider.build_model()
    assert isinstance(model, BedrockModel)
    assert model.get_config()["model_id"] == model_provider.BEDROCK_MODEL_ID


def test_ff_aws_region_wins_over_aws_region(monkeypatch):
    """The project's own setting takes precedence over the ambient one."""
    monkeypatch.setenv("FF_MODEL_PROVIDER", "bedrock")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("FF_AWS_REGION", "ap-south-1")

    model = model_provider.build_model()
    # BedrockModel keeps the region on its boto3 client, not in get_config().
    assert model.client.meta.region_name == "ap-south-1"


def test_builds_an_ollama_model(monkeypatch):
    monkeypatch.setenv("FF_MODEL_PROVIDER", "ollama")
    from strands.models.ollama import OllamaModel

    model = model_provider.build_model()
    assert isinstance(model, OllamaModel)


def test_ollama_host_is_configurable(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9999")
    assert model_provider.ollama_host() == "http://127.0.0.1:9999"
