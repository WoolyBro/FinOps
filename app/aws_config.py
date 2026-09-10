"""Explicit AWS region configuration.

Silently inheriting whatever region happens to be in the caller's profile is a
bad default for a deployed agent: a Bedrock model that is enabled in one region
is not enabled in another, and the failure surfaces as an opaque AccessDenied
at the first model call rather than at start-up.

So the region is resolved from an explicit setting, in this order:

    FF_AWS_REGION           the project's own setting, checked first
    AWS_REGION              the conventional environment variable
    AWS_DEFAULT_REGION      what the AWS CLI exports

If none is set, `require_region()` raises with instructions rather than
guessing. `resolve_region()` returns None instead, for callers that want to
report the state rather than fail on it.
"""

from __future__ import annotations

import os
import re

# AgentCore Runtime regions, from the AWS regional availability announcements
# current as of September 2026. Used only to warn -- AWS adds regions faster
# than a hard-coded list can track, so an unknown region is a caution, never a
# refusal.
AGENTCORE_REGIONS: tuple[str, ...] = (
    "us-east-1",       # N. Virginia
    "us-east-2",       # Ohio
    "us-west-1",       # N. California
    "us-west-2",       # Oregon
    "ap-south-1",      # Mumbai
    "ap-south-2",      # Hyderabad
    "ap-southeast-1",  # Singapore
    "ap-southeast-2",  # Sydney
    "ap-southeast-5",  # Malaysia
    "ap-southeast-7",  # Bangkok
    "ap-northeast-1",  # Tokyo
    "eu-central-1",    # Frankfurt
    "eu-west-1",       # Ireland
    "eu-south-1",      # Milan
    "eu-south-2",      # Spain
)

# The default suggested to a new deployment. Mumbai is deliberate: the product
# bills in rupees for clients in India, so keeping inference in-region is the
# sensible starting point for latency and data residency.
SUGGESTED_REGION = "ap-south-1"

_REGION_PATTERN = re.compile(r"^[a-z]{2}(-gov)?-[a-z]+-\d$")

_MISSING = (
    "No AWS region is configured.\n"
    "  Set FF_AWS_REGION (preferred), AWS_REGION, or AWS_DEFAULT_REGION.\n"
    f"  Suggested: {SUGGESTED_REGION}\n"
    "  The region must be one where AgentCore Runtime is available AND where\n"
    "  you have enabled model access for the model you are using."
)


class RegionNotConfigured(RuntimeError):
    """No AWS region was explicitly configured."""


def resolve_region() -> str | None:
    """The configured region, or None. Never guesses."""
    for var in ("FF_AWS_REGION", "AWS_REGION", "AWS_DEFAULT_REGION"):
        value = (os.getenv(var) or "").strip()
        if value:
            return value
    return None


def require_region() -> str:
    """The configured region, or raise with instructions."""
    region = resolve_region()
    if not region:
        raise RegionNotConfigured(_MISSING)
    if not _REGION_PATTERN.match(region):
        raise RegionNotConfigured(
            f"'{region}' does not look like an AWS region code "
            f"(expected something like {SUGGESTED_REGION})."
        )
    return region


def is_agentcore_region(region: str) -> bool:
    return region in AGENTCORE_REGIONS


def region_status() -> dict:
    """Describe the region configuration, for health checks and the CLI.

    Reports rather than raises, so a readiness probe can say what is wrong
    instead of crashing the container on start-up.
    """
    region = resolve_region()
    if not region:
        return {
            "configured": False,
            "region": None,
            "source": None,
            "agentcore_supported": None,
            "detail": _MISSING,
        }

    source = next(
        var
        for var in ("FF_AWS_REGION", "AWS_REGION", "AWS_DEFAULT_REGION")
        if (os.getenv(var) or "").strip()
    )

    if not _REGION_PATTERN.match(region):
        return {
            "configured": False,
            "region": region,
            "source": source,
            "agentcore_supported": False,
            "detail": f"'{region}' does not look like an AWS region code.",
        }

    supported = is_agentcore_region(region)
    return {
        "configured": True,
        "region": region,
        "source": source,
        "agentcore_supported": supported,
        "detail": None
        if supported
        else (
            f"{region} is not in this project's known list of AgentCore "
            "Runtime regions. That list may simply be out of date -- check the "
            "AWS regional availability page before assuming it will not work."
        ),
    }
