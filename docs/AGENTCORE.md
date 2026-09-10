# Deploying FreelanceFlow to Amazon Bedrock AgentCore

The agent runs on AgentCore Runtime; the dashboard and its API stay where they
are. Nothing about the 21 business tools changed for this.

```
Browser -> Next.js -> FastAPI -> AgentService ─┬─ local: Strands -> Bedrock
                                               └─ deployed: InvokeAgentRuntime
                                                            -> AgentCore Runtime
                                                            -> app/agentcore_app.py
                                                            -> AgentService
                                                            -> Strands -> Bedrock
```

`app/agentcore_app.py` is the only new entry point. It calls the same
`AgentService` the API calls, which is why this phase touched no tool code.

---

## Read this first: SQLite is not durable on AgentCore

**Do not run this against real billing data yet.** The deployment is correct;
the storage underneath it is not.

AgentCore gives each session its own microVM with its own filesystem, and
[that filesystem is ephemeral by default](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html):
"Any data stored in memory or written to disk persists only for the compute
lifecycle."

For a billing system that means, concretely:

| What happens | Consequence for FreelanceFlow |
|---|---|
| Two chat sessions run concurrently | Two different databases. Invoice FF-0001 exists in one and not the other. |
| A session idles 15 minutes (default) | The microVM stops. Its database goes with it. |
| You deploy a new version | Every session's storage is wiped on next invoke. |
| A session hits its 8-hour max lifetime | New compute, empty disk. |

`readiness()` reports this as a warning on every invocation, and the runtime
logs it, so it cannot pass unnoticed. `FF_STORAGE_DURABLE=true` silences the
warning — set it **only** once the statements below are actually true.

### Why session storage does not fix it

[Managed session storage](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-filesystem-configurations.html)
survives stop/resume, which sounds like the answer. It is not, for two reasons:

- It is **isolated per session** — "each session can only access its own storage
  and cannot read or write data from other sessions." A freelancer's invoices
  must be one dataset, not one per conversation.
- It is **wiped on every runtime version update**. A deploy would erase the
  ledger.

### The smallest migration path (a later phase, not this one)

Every database access in the app already goes through `app/database.py`
(`connect()`, `get_db()`, `next_counter()`). Nothing else opens a connection.
That containment is what makes the migration small.

Two options, cheapest first:

**1. EFS-mounted SQLite.** Mount an EFS access point at `/mnt/data`, set
`FF_DATA_DIR=/mnt/data`. EFS is shared across sessions and supports the POSIX
advisory locking SQLite needs. Requires VPC network mode, an access point, and
port 2049 open. Roughly a day's work, no code change beyond configuration.
*Caveat:* SQLite over NFS is safe for one writer at a time. Fine for a
single-freelancer product; not fine for multi-tenant.

**2. Postgres.** Change `app/database.py` to open a connection pool against RDS
or Aurora Serverless v2. The SQL is close to portable already; the dialect work
is `AUTOINCREMENT` → `GENERATED ... AS IDENTITY`, `datetime('now')` → `now()`,
and `INSERT ... ON CONFLICT DO NOTHING` (which Postgres already supports). The
counters table and its transactional number reservation port unchanged, which
matters — that is what keeps invoice numbers gapless. Right answer before real
users; a few days including tests.

The deterministic tests would carry over to either, because they assert on
tool behaviour rather than on SQLite.

---

## What you need before deploying

1. **An AWS account** with credentials configured (`aws configure`, a profile,
   or an SSO session).
2. **Model access for Amazon Nova in your chosen region.** Bedrock enables
   foundation models by default, but verify: model access is *per region*, and
   this is the failure people hit. Bedrock console → Model access. Nova is
   first-party AWS, so this is normally a single click -- no usage-terms form
   to submit and wait on, unlike Anthropic/Meta/Mistral's Bedrock models.
3. **Node.js 20+** — the AgentCore CLI ships as an npm package.
4. **Python 3.10+**.
5. **Docker** — only for the `Container` build type. The default `CodeZip`
   build does not need it.

### Region

Set it explicitly. `app/aws_config.py` refuses to guess, because a model
enabled in one region is not enabled in another and an inherited region turns
that into an opaque `AccessDenied` at the first inference call.

```bash
export FF_AWS_REGION=ap-south-1
```

`ap-south-1` (Mumbai) is the suggested default: the product bills in rupees for
clients in India, so keeping inference in-region helps latency and data
residency. AgentCore Runtime is also available in `us-east-1`, `us-east-2`,
`us-west-1`, `us-west-2`, `ap-south-2`, `ap-southeast-1`, `ap-southeast-2`,
`ap-southeast-5`, `ap-southeast-7`, `ap-northeast-1`, `eu-central-1`,
`eu-west-1`, `eu-south-1` and `eu-south-2`. An unlisted region produces a
warning rather than a refusal — AWS adds regions faster than a hard-coded list
tracks them.

---

## The runtime contract

Taken from the AWS documentation and verified locally, not assumed:

| Requirement | Value |
|---|---|
| Host | `0.0.0.0` |
| Port | `8080` |
| Platform | ARM64 container |
| Invocation | `POST /invocations`, JSON in, JSON out |
| Health | `GET /ping` → `{"status": "Healthy"}` |
| Session header | `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id` |

The `bedrock-agentcore` SDK serves this; `app/agentcore_app.py` supplies the
entrypoint and the ping handler.

**Health vs readiness are deliberately separate.** `/ping` returns `Healthy`
even when no model is configured. A container that reports unhealthy gets
recycled, so failing the health check on a configuration mistake would produce
a crash loop that hides the cause. Readiness problems surface in the
`/invocations` response and the logs instead.

Run it locally exactly as AgentCore will:

```bash
python -m app.agentcore_app
curl localhost:8080/ping
curl -X POST localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -H 'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: local-test-session-0000000000000' \
  -d '{"prompt":"How much does Rahul owe me?"}'
```

---

## Deploying

```bash
npm install -g @aws/agentcore
agentcore --version
```

> If that errors instead of printing a version, an older pip
> `bedrock-agentcore-starter-toolkit` is shadowing it on PATH. Uninstall it and
> open a new terminal.

Point the CLI at `app/agentcore_app.py` as the entrypoint and deploy:

```bash
agentcore deploy --dry-run    # preview
agentcore deploy
agentcore status              # get the runtime ARN
agentcore logs --since 30m
```

For a Container build, `deploy/Dockerfile` is ready — ARM64 pinned, DejaVu
fonts installed so the rupee sign renders in PDFs, and only the runtime
dependencies (no FastAPI, no test tooling).

### Invoking it

```python
import boto3, json, uuid

client = boto3.client("bedrock-agentcore", region_name="ap-south-1")
response = client.invoke_agent_runtime(
    agentRuntimeArn="<from agentcore status>",
    runtimeSessionId=str(uuid.uuid4()),  # 33+ chars; reuse it for a conversation
    payload=json.dumps({"prompt": "How much does Rahul owe me?"}).encode(),
    qualifier="DEFAULT",
)
print(json.loads(b"".join(response["response"])))
```

Reuse the same `runtimeSessionId` across a conversation — it routes to the same
microVM, which preserves both the Strands conversation and (for now) the
database that session created.

---

## Minimum IAM permissions

Three policies in `deploy/iam/`, all scoped. No `bedrock:*`, no
`bedrock-agentcore:*`, no `"Resource": "*"` except where the service requires
it. Replace `REGION`, `ACCOUNT_ID`, `AGENT_NAME` and `AGENT_ID`.

**`execution-role-policy.json`** — what AgentCore assumes to run the agent:

- `bedrock:InvokeModel` / `InvokeModelWithResponseStream`, scoped to the Nova
  model and its inference profile.
- CloudWatch Logs, scoped to `/aws/bedrock-agentcore/runtimes/*`.
- X-Ray tracing — `"Resource": "*"` because X-Ray does not support
  resource-level permissions.
- `cloudwatch:PutMetricData`, conditioned to the `bedrock-agentcore` namespace.
- ECR read — **delete these two statements if you deploy with CodeZip.**

> **Inference profiles need two grants.** The default model
> `apac.amazon.nova-pro-v1:0` is a cross-region inference profile, so the
> policy allows both the profile ARN *and* the underlying `foundation-model`
> ARN it routes to. Granting only the profile produces an `AccessDenied` that
> names a region you never configured. The same two-grant shape applies to any
> Bedrock model you switch to via `FF_MODEL_ID`, first-party or third-party.

**`execution-role-trust-policy.json`** — lets `bedrock-agentcore.amazonaws.com`
assume the role, with `aws:SourceAccount` and `aws:SourceArn` conditions to
prevent the confused-deputy problem.

**`invoke-policy.json`** — for whatever calls the agent (the FastAPI backend, or
you running live checks). Grants exactly `bedrock-agentcore:InvokeAgentRuntime`
on one runtime ARN. Deliberately not `BedrockAgentCoreFullAccess`: something
that only sends prompts should not be able to delete runtimes.

The AgentCore CLI also needs deploy-time permissions (IAM role creation,
CodeBuild, S3, ECR, CDK bootstrap) — see
[Use the AgentCore CLI](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html#runtime-permissions-cli).
Those are development permissions; AWS says as much, and they are not suitable
for production.

---

## Observability

`app/observability.py` emits one JSON object per line to stdout, which is what
AgentCore ships to CloudWatch Logs. Queryable in Logs Insights without regex:

```
fields @timestamp, message, session_id, elapsed_seconds
| filter message = "invocation completed"
| sort @timestamp desc
```

**Client data is deliberately kept out of the logs.** `tool_call_summary()`
reduces a tool trace to names, outcomes and durations — never arguments, which
carry client names and amounts. There is a test asserting the amount does not
appear in a serialised summary.

---

## Testing

```bash
pytest -q                      # 428 tests. No AWS, no credentials, no spend.
pytest -m live                 # real model; opt-in, costs money
python -m app.live_check --scenario balance
```

The AgentCore tests assert the contract itself: ARM64 pinned in the Dockerfile,
`/ping` healthy while unconfigured, prompts validated, internals not leaked on
failure, IAM policies free of service-wide wildcards, and the persistence
warning present by default.

---

## Live validation order

Once credentials and model access are in place, in this order — do not skip
ahead:

1. `python -m app.live_check --scenario balance` — one small read. Confirm the
   tool chain is `find_client` → `get_client_balance`.
2. Verify the answer against the database directly.
3. `python -m app.live_check --scenario payment` — one mutation.
4. Verify the resulting invoice and payment rows.
5. Only then, `pytest -m live` for the full set.
