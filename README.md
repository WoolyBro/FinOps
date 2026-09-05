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

**Phases 1-2 complete.** The deterministic business layer is being built and
tested first; the live model is connected once the tools are trustworthy.

| Phase | Scope | State |
|---|---|---|
| 1 | Strands agent, model provider, SQLite schema, client tools | done |
| 2 | Invoice numbering, creation, retrieval, validation, amount parsing | done |
| 2.8 | Deterministic invoice PDFs | done |
| 3 | Payments, balances, status transitions, receipts | done |
| 4 | Overdue detection, reminders, financial summaries | next |
| 5 | Live Strands + Bedrock | |
| 6 | FastAPI + Next.js UI, agent activity panel | |
| 7 | AgentCore deployment, demo, evaluation | |

249 tests pass with no credentials of any kind.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env
```

### Choosing a model provider

`app/model_provider.py` resolves the provider at runtime so the deterministic
half of the app is developable before AWS access lands.

| `FF_MODEL_PROVIDER` | Uses | Needs |
|---|---|---|
| `auto` (default) | Bedrock if AWS credentials resolve, else Anthropic | either of the below |
| `bedrock` | Amazon Bedrock | `aws configure` + Claude model access in the Bedrock console |
| `anthropic` | Anthropic API directly | `ANTHROPIC_API_KEY` |
| `ollama` | Local Ollama | Ollama running on `localhost:11434` |

Nothing outside `model_provider.py` knows which one is in use, so switching to
Bedrock for the final submission is a one-line env change.

## Running

```bash
python -m app.cli --init-db           # create the database
python -m app.cli                     # interactive session
python -m app.cli "Add a client called Rahul Sharma"
pytest -q                             # tool tests, no credentials needed
```

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
  tools/
    amounts.py       parse_amount
    clients.py       find_client, create_client, list_clients, update_client
    invoices.py      create_invoice, get_invoice, list_invoices,
                     get_next_invoice_number, generate_invoice_pdf
    payments.py      record_payment, get_payment, list_payments,
                     generate_receipt
tests/
data/                SQLite database (gitignored)
  invoices/          generated invoice PDFs, named FF-0001.pdf
  receipts/          generated receipts, named RC-0001.pdf
```
