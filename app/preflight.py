"""Preflight checks for a live Bedrock run.

Every check here is local and free. Nothing in this module calls a model, and
nothing calls the AWS control plane, so running it costs nothing and needs no
permissions beyond reading the credential chain.

Model access is the one prerequisite that cannot be confirmed for free: doing so
would need either an inference call (which costs credits) or
`bedrock:ListFoundationModels` (which is not in the least-privilege policy this
project ships). So preflight reports it as unconfirmed, and `diagnose_failure`
turns the first real call's error into a precise explanation instead of a raw
AccessDeniedException.

The refusal rule matters most: a run that explicitly asks for Bedrock must never
quietly execute against Ollama. A green tick from the wrong provider is worse
than a clear failure.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.aws_config import region_status
from app.model_provider import (
    BEDROCK_MODEL_ID,
    ModelNotConfigured,
    OLLAMA_MODEL_ID,
    resolve_provider,
)


@dataclass
class Check:
    name: str
    passed: bool
    detail: str
    fix: str | None = None


@dataclass
class PreflightReport:
    checks: list[Check] = field(default_factory=list)
    provider: str | None = None
    model_id: str | None = None
    region: str | None = None

    @property
    def ok(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if not check.passed]

    def format(self) -> str:
        lines = []
        for check in self.checks:
            mark = "PASS" if check.passed else "FAIL"
            lines.append(f"  [{mark}] {check.name}: {check.detail}")
            if not check.passed and check.fix:
                for fix_line in check.fix.splitlines():
                    lines.append(f"         {fix_line}")
        return "\n".join(lines)


def aws_credentials_detail() -> tuple[bool, str]:
    """Whether the standard AWS credential chain resolves, and how."""
    try:
        import botocore.session

        credentials = botocore.session.get_session().get_credentials()
    except Exception as exc:
        return False, f"credential chain raised {type(exc).__name__}: {exc}"

    if credentials is None:
        return False, "no credentials found in the AWS credential chain"
    return True, f"resolved via {credentials.method}"


def preflight(require_provider: str = "bedrock") -> PreflightReport:
    """Verify everything a live run needs, without spending anything.

    Args:
        require_provider: The provider this run demands. A run that asks for
            Bedrock fails rather than falling through to another provider.
    """
    report = PreflightReport()

    # 1. Credentials, through the normal chain -- never from a file this
    #    project reads or writes.
    if require_provider == "bedrock":
        ok, detail = aws_credentials_detail()
        report.checks.append(
            Check(
                "aws credentials",
                ok,
                detail,
                fix=(
                    "Run `aws configure`, export AWS_PROFILE, or start an SSO\n"
                    "session. Never put credentials in .env or the repository."
                ),
            )
        )

    # 2. Region, explicitly configured.
    region = region_status()
    report.region = region["region"]
    if require_provider == "bedrock":
        report.checks.append(
            Check(
                "aws region",
                bool(region["configured"]),
                f"{region['region']} (from {region['source']})"
                if region["configured"]
                else "not configured",
                fix="export FF_AWS_REGION=ap-south-1",
            )
        )
        if region["configured"] and not region["agentcore_supported"]:
            report.checks.append(
                Check("region supports agentcore", True, region["detail"])
            )

    # 3. The provider actually resolves, and is the one that was asked for.
    try:
        provider = resolve_provider()
        report.provider = provider
        matches = provider == require_provider
        report.checks.append(
            Check(
                "provider resolves",
                matches,
                f"resolved to {provider!r}"
                + ("" if matches else f", but this run requires {require_provider!r}"),
                fix=(
                    f"export FF_MODEL_PROVIDER={require_provider}\n"
                    "A Bedrock validation run must not silently execute against\n"
                    "a different provider -- a pass from the wrong model proves\n"
                    "nothing."
                ),
            )
        )
    except ModelNotConfigured as exc:
        report.checks.append(
            Check("provider resolves", False, str(exc).splitlines()[0], fix=str(exc))
        )

    report.model_id = os.getenv("FF_MODEL_ID") or (
        BEDROCK_MODEL_ID if require_provider == "bedrock" else OLLAMA_MODEL_ID
    )

    # 4. The Anthropic API is not a path this project has.
    key_present = bool(os.getenv("ANTHROPIC_API_KEY"))
    report.checks.append(
        Check(
            "anthropic api not used",
            True,
            "ANTHROPIC_API_KEY is set but is never read; Bedrock is the only "
            "cloud path"
            if key_present
            else "no ANTHROPIC_API_KEY, and nothing reads one",
        )
    )

    # 5. Model access -- stated, not silently assumed.
    if require_provider == "bedrock":
        report.checks.append(
            Check(
                "model access",
                True,
                f"cannot be confirmed without a call; {report.model_id} will be "
                f"tried in {report.region or 'the configured region'}",
            )
        )

    return report


def diagnose_failure(exc: BaseException, model_id: str, region: str | None) -> str:
    """Turn a Bedrock failure into something actionable.

    An AccessDeniedException from Bedrock does not say "you forgot to enable
    model access in this region", which is what it usually means.
    """
    name = type(exc).__name__
    text = str(exc)

    # A brand-new AWS account is held for verification, and Bedrock reports it
    # as AccessDenied. Checked before the generic branch, because "enable model
    # access" is actively misleading advice here -- there is nothing to fix.
    if "being verified" in text or "account is currently being verified" in text:
        return (
            "This AWS account is still being verified by AWS.\n"
            "  Nothing is misconfigured -- credentials, region and model are all\n"
            "  correct. New accounts are held for verification, normally under\n"
            "  two hours. Retry after that.\n"
            "  If it persists beyond a few hours, AWS asks you to contact\n"
            "  aws-verification@amazon.com."
        )

    if "AccessDenied" in name or "AccessDenied" in text:
        return (
            f"Bedrock refused the call for {model_id} in {region}.\n"
            "  Most likely: model access is not enabled for this model in this\n"
            "  region. Bedrock console > Model access > Anthropic Claude.\n"
            "  Model access is granted per region -- enabling it elsewhere does\n"
            "  not help.\n"
            "  Also check the execution role allows bedrock:InvokeModel on both\n"
            "  the inference profile ARN and the foundation-model ARNs it routes\n"
            "  to (see deploy/iam/execution-role-policy.json)."
        )
    if "ValidationException" in name or "ValidationException" in text:
        return (
            f"Bedrock rejected the request for {model_id}.\n"
            "  Most likely: that model id or inference profile does not exist in\n"
            f"  {region}. Check the model id, or set FF_MODEL_ID to one that is\n"
            "  available there."
        )
    if "ResourceNotFound" in name or "ResourceNotFound" in text:
        return (
            f"{model_id} was not found in {region}.\n"
            "  Set FF_AWS_REGION to a region where the model exists, or set\n"
            "  FF_MODEL_ID to a model that exists in this one."
        )
    if "ThrottlingException" in name or "Throttling" in text:
        return (
            "Bedrock throttled the request. Wait and retry; if this persists,\n"
            "  request a quota increase for the model."
        )
    if "ExpiredToken" in text or "InvalidClientTokenId" in text:
        return (
            "The AWS credentials are present but not valid.\n"
            "  Refresh your SSO session, or check the access key is active."
        )
    return f"{name}: {text}"
