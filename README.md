# FreelanceFlow

An AI billing operations agent for freelancers, built on the
[Strands Agents SDK](https://strandsagents.com).

You tell it what happened in plain language:

> "I completed a ₹40,000 website for Rahul. He paid ₹15,000 today and the
> remaining ₹25,000 is due September 15."

It turns that into real records and real documents — clients, invoices,
payments, receipts, reminders — using deterministic Python tools. The model
decides *what* to do; Python does it.

## Status

**Phases 1-4 complete.** The deterministic business layer was built and tested
first; the live model gets connected only now that the tools are trustworthy.

| Phase | Scope | State |
|---|---|---|
| 1 | Strands agent, model provider, SQLite schema, client tools | done |
| 2 | Invoice numbering, creation, retrieval, validation, amount parsing | done |
| 2.8 | Deterministic invoice PDFs | done |
| 3 | Payments, balances, status transitions, receipts | done |
| 4 | Overdue detection, reminders, financial summaries | done |
| 5 | Live Strands + Bedrock | harness ready, awaiting credentials |
| 6 | FastAPI + Next.js UI, agent activity panel | |
| 7 | AgentCore deployment, demo, evaluation | |

335 tests pass with no credentials of any kind. 21 tools are registered with
the agent. The agent loop itself is proven offline against a scripted model
(`tests/test_agent_loop.py`); what remains unproven is whether a *real* model
chooses the right tools, which is what `pytest -m live` measures.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env
```

### Choosing a model provider

FreelanceFlow runs Claude on **Amazon Bedrock**. It does not use the Anthropic
API, and nothing in the app requires an `ANTHROPIC_API_KEY` — a key being
present in the environment changes nothing, and there is a test asserting that.

| `FF_MODEL_PROVIDER` | Uses | Needs |
|---|---|---|
| `auto` (default) | Bedrock if AWS credentials resolve, else Ollama if it is running | one of the two below |
| `bedrock` | Claude on Amazon Bedrock — **production** | `aws configure` + Claude enabled under Bedrock → Model access |
| `ollama` | A local model — **development without AWS** | Ollama running on `localhost:11434` |

`auto` probes for Ollama with a half-second socket check. Asking for a provider
explicitly skips that probe, so a slow Ollama start-up is never mistaken for a
missing install.

Nothing outside `model_provider.py` knows which one is in use, which is what
keeps the eventual AgentCore deployment a configuration change rather than a
rewrite.

### Setting up Bedrock

Four steps, all on your side — none of them can be scripted from here, because
they need your AWS account.

1. **Create an IAM user** with programmatic access and the
   `AmazonBedrockFullAccess` policy (or, more tightly,
   `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`).
2. **Request model access** in the Bedrock console → *Model access* → enable
   **Anthropic Claude**. This is the step people forget; credentials alone are
   not enough, and access can take a few minutes to activate.
3. **Install the AWS CLI and configure it** (`aws configure`), or put the
   credentials in your environment. `model_provider.py` resolves whatever
   botocore can find, so a profile, an SSO session or env vars all work.
4. **Pick a region that has the model** — `us-east-1` is the safe default and
   what `AWS_REGION` falls back to.

Verify it resolved:

```bash
python -c "from app.model_provider import resolve_provider; print(resolve_provider())"
```

That should print `bedrock`. If it raises, the message names both paths —
Bedrock and Ollama — and what each one needs.

## Running

```bash
python -m app.cli --init-db           # create the database
python -m app.cli                     # interactive session
python -m app.cli "Add a client called Rahul Sharma"
```

## Tests

The deterministic suite needs no credentials and spends nothing:

```bash
pytest -q                             # 335 tests, live ones skipped
```

Live tests call a real model and cost money, so they are opt-in:

```bash
pytest -m live                        # the 11 live-model tests
pytest -m live -k payment             # just one of them
```

To watch the loop by hand rather than through pytest — this prints the tool
chain the model chose, which is the thing worth looking at:

```bash
python -m app.live_check --scenario balance     # the two-tool loop
python -m app.live_check --scenario payment     # a real mutation
python -m app.live_check --scenario ambiguous   # two Rahuls; must ask
python -m app.live_check --scenario missing     # no amount given; must ask
python -m app.live_check --scenario shorthand   # "40k" must go via parse_amount
python -m app.live_check --scenario unknown     # no such client; must not invent
python -m app.live_check --scenario payment --full   # all 21 tools available
```

Each run uses a scratch database, so smoke tests never touch real records.

## Design decisions

**Money is stored as integer minor units** (paise, cents) — never floats. A
rounding error in an invoice total is not an acceptable failure mode.

**"Overdue" is derived, never stored.** It is computed from `due_date` and
outstanding balance at read time, so it cannot go stale while the app sits idle.

**Every tool returns an explicit `status`.** `found` / `not_found` / `ambiguous`
/ `already_exists` / `error`. This is what lets the agent say "I couldn't find
Rahul — should I create him?" instead of inventing a client. The system prompt
forbids reporting an action as done unless a tool actually returned success.

**Client names are deduplicated** via a normalised `name_key` with a unique
index, so "Rahul", "rahul " and "RAHUL" cannot become three separate clients.

**The database assigns invoice numbers, not the model.** `create_invoice`
reserves the number from a counter inside the same transaction as the insert, so
a failed insert returns the number rather than leaving a gap in the sequence.
`get_next_invoice_number` is a preview that deliberately does not reserve.

**`amount_paid` is not a column.** It is `SUM(payments.amount_minor)`, computed
on every read, so the stated balance and the payment ledger cannot disagree.
Delete a payment row and every balance in the system changes with it -- there is
a test asserting exactly that.

**Invoice status is a cache of the ledger, not an independent fact.** It is
recalculated inside the same transaction as every payment write, so UNPAID ->
PARTIALLY_PAID -> PAID follows the money rather than the model's opinion.
A cancelled invoice keeps its status and refuses payments outright.

**Payments cannot overshoot.** A payment larger than the outstanding balance is
refused with the real figure in the error, rather than being recorded and
leaving a negative balance to explain later.

**A payment keeps one receipt number for life.** Calling `generate_receipt`
again returns the existing receipt instead of issuing a second number, and the
number is reserved in the same transaction as the render, so a failed render
gives it back rather than leaving a gap in the sequence.

**A receipt records a moment, not a live view.** Each one shows the balance as
it stood when that money arrived, computed in SQL from the payments up to and
including it -- so regenerating an old receipt after later payments still shows
the historical balance.

**The model does no financial arithmetic.** `parse_amount` turns the user's own
words -- "40k", "1.5 lakh", "Rs 40,000/-", "$250" -- into minor units in Python.
The model passes the characters through; it never multiplies by 100 itself. Text
holding two numbers, or no number, is refused rather than guessed at.

**An identical invoice is flagged, not silently duplicated.** Same client, same
project, same amount, same day returns `duplicate_suspected` with the existing
invoice; the agent has to come back with `allow_duplicate=true` after asking.

**The model never generates documents.** It calls a tool; deterministic Python
renders the PDF. Layout, wording and every figure on the page are fixed code
reading from SQLite. The LLM is the orchestrator, not the printer. PDF tests
read the text back out of the generated file rather than trusting the return
value, so a document that reports success but prints the wrong balance fails.

**INR is written with Indian digit grouping** -- ₹1,50,000.00, not ₹150,000.00.
Other currencies keep western grouping and their own decimal rules, so JPY
prints ¥150,000 with no decimals. Formatting is integer arithmetic throughout;
nothing rounds.

**The rupee sign is absent from the PDF core fonts.** The generator locates and
embeds a system font that carries U+20B9, searching Windows, Linux and macOS
paths so a container build still renders correctly. If no such font exists it
falls back to "Rs. " rather than printing a black box.

**Document generation is a separate step from invoice creation.** A failed
render cannot take an invoice down with it, and the agent is told never to
claim a document exists unless `generate_invoice_pdf` returned "created".

**Every reporting tool is read-only and derived at query time.** There is no
stored `overdue`, `monthly_revenue`, or `total_outstanding` anywhere. Close the
app for three weeks and reopen it: every figure is exactly as correct as if it
had been running the whole time, because nothing was cached while it was closed.

**Money is never summed across currencies.** `get_overdue_invoices`,
`get_outstanding_invoices`, `get_client_balance` and `get_financial_summary` all
return a list of `{currency, total_minor, total_display}`, one entry per
currency present, rather than a single total that would silently add USD and
INR together. `list_invoices`/`list_payments` predate this and still sum
regardless of currency -- fine for a single-currency freelancer, a latent bug
for anyone billing in more than one. Worth fixing before Phase 5 if that matters.

**`get_outstanding_invoices` and `get_overdue_invoices` are deliberately
separate**, even though overdue is a subset of outstanding. An invoice due next
week and an invoice four days late are both outstanding, but a freelancer
chasing late payments needs the narrower list, not everything they're owed.

**A financial summary's period and its snapshot don't mean the same thing.**
`received` and the invoice-issued counts are scoped to `start_date`/`end_date`
because they're flows -- money that moved, invoices that went out. `outstanding`
and `overdue` are current totals across every open invoice regardless of when
it was issued, because a balance owed doesn't belong to a calendar month: an
invoice from three months ago that's still unpaid is still relevant today.
Documented explicitly in the tool's docstring since the two halves of one
return value are scoped differently on purpose.

**A reminder is drafted from the invoice, not phrased by the model.** The
invoice number, client name, outstanding balance, due date and days overdue in
the message text all come from `invoice_to_dict` -- the model never edits a
figure into the wording. A reminder only reaches `APPROVED` through
`approve_reminder`; there is no send capability at all yet, deliberately.

**The agent loop is tested separately from the model's judgement.**
`tests/scripted_model.py` is a Strands model with canned replies, so the loop --
hooks, tool execution, results fed back into the conversation, tracing -- is
proven offline with no credentials and no spend. The live tests then measure
only the thing that actually needs a real model: whether it picks the right
tools. Without that split, a failing live test is ambiguous between "the model
chose badly" and "our wiring is broken".

**Live tests assert on the tool chain, not the prose.** `ToolTracer` records
every call, its arguments and its result, and the live tests check those plus
the resulting database state. A fluent paragraph built on a skipped lookup or
an invented id is a failure that reads like a success.

**A reminder keeps one active draft per invoice.** Calling
`create_payment_reminder` again while a `DRAFT` or `APPROVED` reminder already
exists returns that reminder instead of writing a duplicate; `force=true` after
the user asks for a second one is the only way past it. A `CANCELLED` reminder
doesn't block a new draft.

## Layout

```
app/
  agent.py           the Strands Agent: tools + system prompt
  model_provider.py  Bedrock / Anthropic / Ollama selection
  database.py        SQLite schema, connections, counters
  models.py          row -> dict converters (what the model actually reads)
  money.py           minor-unit validation, parsing and currency formatting
  pdf_generator.py   deterministic invoice and receipt PDF rendering
  dates.py           ISO date parsing and derived overdue calculation
  config.py          paths and settings
  cli.py             terminal entry point
  live_check.py      manual live-model smoke test, prints the tool chain
  tracing.py         records which tools the model chose, and with what
  tools/
    amounts.py       parse_amount
    clients.py       find_client, create_client, list_clients, update_client
    invoices.py      create_invoice, get_invoice, list_invoices,
                     get_next_invoice_number, generate_invoice_pdf
    payments.py      record_payment, get_payment, list_payments,
                     generate_receipt
    reports.py       get_overdue_invoices, get_outstanding_invoices,
                     get_client_balance, get_financial_summary
    reminders.py     create_payment_reminder, approve_reminder,
                     list_reminders
tests/
  scripted_model.py  a Strands model with canned replies, for offline loop tests
  test_agent_loop.py the loop and tracer, proven without credentials
  test_agent_live.py real-model tests, skipped unless `-m live`
data/                SQLite database (gitignored)
  invoices/          generated invoice PDFs, named FF-0001.pdf
  receipts/          generated receipts, named RC-0001.pdf
```
