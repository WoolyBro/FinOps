# Prompt: FreelanceFlow architecture diagrams

Paste everything below the line into Claude. It describes the system as it
actually exists in the repository (github.com/WoolyBro/FinOps), including what
is *not* built, so the diagrams stay accurate.

---

You are a senior software architect preparing the **architecture diagrams for
a hackathon submission**. The judges will read them on the GitHub README and in
a slide. They must be accurate enough that an engineer reading the code finds
nothing on the diagram that isn't there, and clear enough that a non-engineer
understands the idea in ten seconds.

Read the whole brief before drawing anything. Section 6 lists what you must not
draw. Treat it as strictly as section 3.

## 1. The product in one paragraph

**FreelanceFlow** is an AI billing-operations agent for independent freelancers
in India, built on the **Strands Agents SDK**. A freelancer types what happened
in plain language, e.g. *"Rahul paid me ₹15,000 today"*. A Strands agent
reasons about the request and calls **deterministic Python tools** that find the
client, match the invoice, parse the amount, record the payment in a SQLite
ledger and issue a receipt PDF. The model decides *which* tools to call; it
never computes money, invents invoice numbers or writes documents. Every tool
call is recorded and shown to the user. The same tools also power a full
10-screen web dashboard, so the app works by hand even with no model.

**The core idea every diagram should communicate:** *the LLM orchestrates;
deterministic code owns the money.*

## 2. What to produce

Produce **four diagrams**. For each, give:

- **Mermaid source** in a fenced ` ```mermaid ` block. It must render on GitHub, so quote any label containing parentheses, colons or slashes, use `<br/>` for line breaks, and never use `end` as a node id.
- **A one-paragraph caption** (3–5 sentences) explaining what the diagram shows.

Then, for **Diagram 1 only**, also produce a **polished standalone SVG**
(viewBox about 1600 × 1000) in the visual style of section 7, suitable for a
slide.

| # | Diagram | Type |
|---|---|---|
| 1 | **System architecture** (the hero diagram) | Layered component / container view |
| 2 | **One agent turn: "Rahul paid me ₹15,000 today"** | Sequence diagram |
| 3 | **Data model** | Entity-relationship diagram |
| 4 | **Deployment** | Deployment view: local dev, hosted demo, AWS target |

## 3. The system, component by component

Use these exact names. File paths are given so labels can reference the code.

### 3.1 Presentation layer: the dashboard (`frontend/`)

- **React 19 + TypeScript + Vite 6 + Tailwind CSS 4** single-page app.
- **Hash routing** (`#/invoices`). There are **10 screens**: Overview, Agent, Invoices, Invoice detail, Clients, Client detail, Payments, Overdue, Reminders, Reports.
- **`src/lib/api.ts`** is the **only module that talks to the backend**. All calls go to relative `/api/...` on the same origin.
- The **Agent screen** shows the conversation, a **tool-call trace** under each reply (tool name, arguments, status, duration), and a **result card** (payment / invoice / reminder).
- **The browser does no money arithmetic.** It renders `*_display` strings the server sends (e.g. `₹1,50,000.00`).

### 3.2 API layer: FastAPI (`app/api/`)

- **`main.py`**: app factory. It sets one error shape for every failure (`{"error", "detail"}`), a CORS policy that refuses `*`, UTF-8 JSON responses, and a startup hook that creates tables and optionally seeds demo data (`FF_SEED_DEMO`). In deployment it also **serves the built dashboard** (static files mounted last, so `/api` always wins).
- **`middleware.py` → `WorkspaceMiddleware`**: reads `X-FF-Workspace` (or `?workspace=`) and selects a per-request ledger via a Python `ContextVar`.
- **Routers:**
  - `chat.py`: `POST /api/chat`, `DELETE /api/chat/{session_id}`, `GET /api/agent/status`
  - `commands.py`: the writes: `POST /api/clients`, `PATCH /api/clients/{id}`, `POST /api/invoices`, `POST /api/payments`, `POST /api/reminders`, `POST /api/reminders/{id}/approve`, `POST /api/reminders/{id}/cancel`, `POST /api/amounts/parse`
  - `records.py`: the reads: clients, invoices, payments, reminders, plus **PDF downloads** `GET /api/invoices/{id}/pdf` and `GET /api/payments/{id}/receipt`
  - `reports.py`: `GET /api/reports/overview | summary | monthly | clients | overdue | outstanding`
  - `workspaces.py`: `GET /api/workspaces`
- A tool refusal (duplicate, overpayment, nothing outstanding) is returned as **HTTP 409 carrying the tool's own explanation**.

### 3.3 Service layer (`app/services/`)

- **`agent_service.py` → `AgentService`**: the **only component that constructs a Strands Agent or invokes a model**. Route handlers never import Strands.
  - Holds agent **sessions** in memory, one Strands `Agent` per conversation: TTL 4 hours, hard cap 200, **server-issued** 32-hex session ids, never shared across workspaces.
  - Runs one turn and returns `{session_id, reply, tool_calls[], turn, elapsed_seconds, result_card}`.
  - Builds the **`result_card` from the tool's return value** (e.g. `record_payment`'s result), **not from the model's reply text**.
  - Explains failures in plain language (bad key, quota reached, model retired) without leaking internals.
- **`views.py`**: **every derived figure a screen shows** (overview totals, collection rate, monthly invoiced-vs-received series with chart scale, per-client breakdown, period summary, ledger totals). It reuses the reporting tools' helpers.
- **`data_service.py`**: reads for the dashboard, calling the tools. Also guards document paths.
- **`write_service.py`**: writes for the dashboard, **through the exact same tools the agent uses**, so there's no second, weaker path into the database.

### 3.4 Agent layer: Strands Agents SDK

- **`app/agent.py`**: `build_agent()` creates a `strands.Agent` with a **system prompt of hard rules** and **22 tools**. Key rules: never invent financial facts, never do arithmetic (always `parse_amount`), never claim success unless a tool returned it, ask when information is missing, and stop on `duplicate_suspected`.
- **`app/model_provider.py`**: picks the model behind the agent:
  - **Google Gemini** `gemini-3.5-flash-lite` via Strands `GeminiModel`, with thinking level **low**. **Default; verified working live.**
  - **Amazon Bedrock**, Amazon Nova `apac.amazon.nova-pro-v1:0`, via Strands `BedrockModel`. **Implemented; not live-validated** (Bedrock model access wasn't granted).
  - **Ollama** `llama3.1` via Strands `OllamaModel`. **Implemented; local/offline option.**
  - `auto` mode order: Gemini (if key) → Bedrock (if AWS credentials) → Ollama (if running).
- **`app/tracing.py` → `ToolTracer`**: a **Strands hook provider** registered on `BeforeToolCallEvent` / `AfterToolCallEvent` (and model-call events). It records each call's name, arguments, result, status and duration. This is the source of the trace the UI shows and of the result cards.

### 3.5 Tool layer: 22 deterministic `@tool` functions (`app/tools/`)

| Module | Tools |
|---|---|
| `amounts.py` | `parse_amount` ("40k", "1.5 lakh", "Rs 40,000/-" → integer paise) |
| `clients.py` | `find_client`, `create_client`, `list_clients`, `update_client` |
| `invoices.py` | `create_invoice`, `get_invoice`, `list_invoices`, `get_next_invoice_number`, `generate_invoice_pdf` |
| `payments.py` | `record_payment`, `get_payment`, `list_payments`, `generate_receipt` |
| `reports.py` | `get_overdue_invoices`, `get_outstanding_invoices`, `get_client_balance`, `get_financial_summary` |
| `reminders.py` | `create_payment_reminder`, `approve_reminder`, `cancel_reminder`, `list_reminders` |

Every tool returns an explicit **status** (`found`, `not_found`, `created`,
`recorded`, `duplicate_suspected`, `already_exists`, `error`, …). That's how
the agent knows to ask rather than guess.

### 3.6 Data and documents

- **SQLite** ledger (`app/database.py`). **Money is stored as integer minor units (paise).**
- **`app/workspaces.py`**: separate ledgers, `demo` (sample data) and `fresh` (starts empty). Each workspace has **its own SQLite file and its own invoice/receipt PDF folders**.
- **`app/pdf_generator.py`**: **ReportLab** renders invoice and receipt PDFs deterministically from the ledger, with an embedded font for the ₹ sign.
- **`app/seed.py`**: demo ledger (6 clients, 10 invoices, payments, reminders), dated relative to today. It is written **through the tools**, not with raw SQL.

### 3.7 Other entry points (secondary; show small or in Diagram 4)

- **`app/cli.py`**: terminal chat with the same agent.
- **`app/live_check.py` + `app/preflight.py`**: live-model smoke test on a scratch database, with a free preflight that verifies configuration without calling a model.
- **`app/agentcore_app.py`**: **Amazon Bedrock AgentCore Runtime** entrypoint (`BedrockAgentCoreApp`, `POST /invocations`, `GET /ping`, port 8080, ARM64). It calls the same `AgentService`.
- **Tests**: 588 offline tests, including a **`ScriptedModel`** (a fake Strands model) that proves the agent loop without credentials; live-model tests are opt-in.

## 4. The flows to draw

### 4.1 Diagram 2: one agent turn, "Rahul paid me ₹15,000 today"

Participants, left to right: **Freelancer (browser)** · **Dashboard (React)** · **FastAPI** · **AgentService** · **Strands Agent** · **Gemini** · **Tools** · **SQLite** · **ToolTracer** (a hook, drawn as a side participant or a note).

Steps:

1. The freelancer types the sentence on the Agent screen.
2. The dashboard calls `POST /api/chat {message, session_id}`.
3. FastAPI → `AgentService.chat()`, which gets or creates the session's Strands `Agent`.
4. The Agent sends the conversation plus 22 tool specs to **Gemini**. Gemini replies with a tool call.
5. **Typical tool chain** (label it *"typical: the model chooses the order; ToolTracer records what actually ran"*):
   1. `find_client(name="Rahul")` → `found`
   2. `list_invoices(client_id, open)` → the unpaid invoice FF-0005 (₹40,000)
   3. `parse_amount("₹15,000")` → `1500000` paise
   4. `record_payment(invoice_id, 1500000, today)`. **Inside one SQLite transaction:** insert the payment, recalculate the status (UNPAID → PARTIALLY_PAID) → `recorded` + outstanding **₹25,000.00**
   5. `generate_receipt(payment_id)` → receipt number reserved + receipt PDF rendered
6. Between steps, the Agent loops back to Gemini with each tool result; show this as the reasoning loop.
7. `ToolTracer` records every call via `BeforeToolCallEvent` / `AfterToolCallEvent`.
8. Gemini writes the final reply.
9. `AgentService` builds `result_card` **from `record_payment`'s result** (not from the reply) and returns `{reply, tool_calls[], result_card, elapsed_seconds}`.
10. The dashboard renders the reply, the **tool trace**, and a **result card showing ₹40,000 → ₹15,000 paid → ₹25,000 outstanding**.

Add a note on the **refusal path**: if the amount exceeded the balance,
`record_payment` returns an error with the real outstanding figure, nothing is
written, no result card is produced, and the agent tells the user why.

### 4.2 Dashboard write (show as a short arrow path in Diagram 1)

Record payment form → `POST /api/payments` → `write_service` → **the same `record_payment` tool** → SQLite. A refusal comes back as 409 with the tool's message.

## 5. Data model: Diagram 3

```
clients   (id PK, name, name_key UNIQUE, email, phone, address, notes, created_at)
invoices  (id PK, invoice_number UNIQUE, client_id FK→clients, project, description,
           amount_minor INTEGER >0, currency DEFAULT 'INR', issue_date, due_date,
           status CHECK in UNPAID|PARTIALLY_PAID|PAID|CANCELLED, pdf_path, created_at)
payments  (id PK, invoice_id FK→invoices, amount_minor INTEGER >0, payment_date,
           method, reference, receipt_number UNIQUE, receipt_path, created_at)
reminders (id PK, invoice_id FK→invoices, channel DEFAULT 'email', message,
           status CHECK in DRAFT|APPROVED|SENT|CANCELLED, created_at, sent_at)
counters  (name PK, value)  -- atomic sequences for invoice and receipt numbers
```

Relationships: a client has 0..n invoices; an invoice has 0..n payments and
0..n reminders. `counters` has no foreign keys.

Annotate these **derived, never-stored** facts as notes beside the diagram:

- `amount_paid = SUM(payments.amount_minor)`. There's **no** `amount_paid` column.
- `outstanding = amount_minor − amount_paid`.
- `is_overdue` / `days_overdue` are computed at read time from `due_date` and outstanding.
- `name_key` is the normalised name, so "Rahul", "rahul " and "RAHUL" are one client.
- Invoice numbers `FF-0001…` and receipt numbers `RC-0001…` come from `counters`, reserved in the same transaction as the insert (gapless).

## 6. Accuracy rules: do NOT draw these

These don't exist in the system. Drawing any of them makes the diagram wrong:

- **No** Anthropic or OpenAI API, no ChatGPT/Claude as the agent's model. The providers are Gemini, Bedrock (Nova) and Ollama, nothing else.
- **No** Next.js. The frontend is React + Vite.
- **No** Redis, Postgres, message queue, vector database, RAG pipeline, embeddings, MCP server, auth/login service, API gateway, load balancer or Kubernetes.
- **No** email, SMS or WhatsApp sending. Reminders are drafted and approved; **there is no send capability**.
- **No** direct browser-to-model or browser-to-Strands call. Everything goes browser → FastAPI → AgentService.
- **No** model writing to the database or rendering PDFs. Only tools do.
- **No** mock or sample-data mode in the frontend.

**Status labels.** Where you show these, mark them exactly as follows. A dashed border plus a small "planned" or "not live-validated" tag works.

| Item | Label |
|---|---|
| Gemini provider | **live** (default) |
| Bedrock / Amazon Nova provider | **implemented, not live-validated** |
| Ollama provider | implemented (local) |
| Workspaces (`demo` / `fresh`) in the API | **implemented** |
| Workspace chooser screen in the dashboard | **planned** |
| Streaming tool events live to the UI while a turn runs | **planned** (the tracer already emits events; there's no streaming endpoint yet) |
| Before/after balance card and audit-trail screen | **planned** |
| AgentCore Runtime deployment | **implemented entrypoint; storage is not durable there (SQLite is per-session)** |

Leave out planned items entirely rather than drawing them as solid.

## 7. Diagram 1 layout and visual style

### Layout (left to right, or top to bottom; pick one and hold it)

Group into **labelled bands**:

1. **User**: Freelancer (browser)
2. **Presentation**: React dashboard (10 screens, `lib/api.ts`)
3. **API**: FastAPI routers + WorkspaceMiddleware
4. **Services**: AgentService · views · data_service · write_service
5. **Agent (Strands Agents SDK)**: `Agent` + system prompt, `ToolTracer` (hooks), `model_provider`
6. **Model providers** (external): Gemini (live) · Bedrock/Nova (not live-validated) · Ollama (local)
7. **Deterministic tools**: 22 tools in 6 groups
8. **State**: SQLite ledgers per workspace · invoice/receipt PDFs (ReportLab)

Arrows to show, each labelled:

- Browser ⇄ Dashboard ⇄ FastAPI: `/api (same origin)`
- FastAPI → AgentService: `POST /api/chat`
- FastAPI → write_service / data_service / views: `dashboard reads & writes`
- AgentService → Strands Agent: `one turn`
- Strands Agent ⇄ Model provider: `reasoning + tool selection`
- Strands Agent → Tools: `tool calls`
- write_service → Tools: `same tools`. Make this visible; it's the design point.
- Tools → SQLite / PDFs: `all money, numbering & documents`
- ToolTracer ⇢ AgentService: dashed, `trace + result card`

Add a **trust boundary**: a dashed outline around everything server-side, with
a small callout: *"API key, file paths and model never reach the browser"*.

Add **three short callouts** (keep them to one line each):

1. *"LLM orchestrates; deterministic tools own the money."*
2. *"Result cards come from tool results, not model text."*
3. *"Dashboard and agent share one set of tools."*

### Style

Match the product's design language:

- Background `#F6F9FC`, boxes `#FFFFFF` with a 1px `#E3E8EE` border and 8px radius, text `#0A2540` (navy, never pure black), secondary text `#697386`.
- **One accent colour**, indigo `#635BFF`, used only for the **Strands Agent band** and the main chat arrow, so the eye lands on the agent.
- Status colours used sparingly: live `#0E6245` on `#CBF4C9`; not validated or planned `#983705` on `#FCEDB9`.
- External systems (model providers) in a visually distinct style, e.g. a dashed border.
- Sans-serif (Inter or the system UI font), labels 13–14px, band titles 12px uppercase.
- **No** gradients, 3D, drop-shadow-heavy cards, clip-art, emoji or stock cloud icons. Flat and precise, like Stripe's documentation diagrams.
- Include a small **legend** (solid = implemented, dashed = external / planned) and a title: **"FreelanceFlow: system architecture"**.
- It must stay readable when scaled to GitHub's README width (about 900px).

## 8. Diagram 4: deployment

Show three environments side by side:

1. **Local development**: Vite dev server `:5173`, proxying `/api` → Uvicorn/FastAPI `:8000`; local SQLite in `data/`; `.env` holds `GEMINI_API_KEY`.
2. **Hosted demo (Render, free tier)**: GitHub repo `WoolyBro/FinOps` → Render Blueprint (`render.yaml`) → **one Docker container** built by a multi-stage `Dockerfile` (stage 1 `node:24-slim` builds the dashboard; stage 2 `python:3.13-slim` runs Uvicorn serving **both** `/api` and the dashboard on Render's `PORT`). `GEMINI_API_KEY` is a Render secret. **Ephemeral disk**: the demo ledger is re-seeded on start when empty. Outbound HTTPS to the Gemini API. The instance sleeps when idle.
3. **AWS target (optional)**: `deploy/Dockerfile` (ARM64) running `app/agentcore_app.py` on **Amazon Bedrock AgentCore Runtime**, with least-privilege IAM policies in `deploy/iam/`, and Bedrock (Amazon Nova) as the model. Mark it "implemented, not deployed" and note *"SQLite is per-session here; production needs EFS or Postgres"*.

## 9. Before you answer, check

- [ ] Every component on the diagrams appears in section 3; nothing from section 6 appears.
- [ ] The **Strands Agents SDK** is named explicitly and visibly.
- [ ] `write_service → same tools` is drawn, not implied.
- [ ] `result_card` comes from the tool result in both Diagram 1 and Diagram 2.
- [ ] Provider statuses match section 6 exactly: Gemini live; Bedrock not live-validated.
- [ ] Planned items are dashed or omitted, never solid.
- [ ] Every Mermaid block renders on GitHub (quoted labels, no reserved words as ids).
- [ ] Captions are 3–5 sentences, plain English, no marketing words ("seamless", "revolutionary", "powerful").

Output order: Diagram 1 (Mermaid, caption, SVG), then Diagrams 2, 3 and 4 (Mermaid and caption each).
