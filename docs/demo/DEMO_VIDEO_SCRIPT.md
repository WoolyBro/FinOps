# FreelanceFlow: demo video script (target 4:30, hard limit 5:00)

The video covers what the submission requires: a **working demo**, plus a pitch
on **the problem**, **who it's for** and **why it matters**. Voiceover over
slides and screen recording; you don't need to appear on camera.

Every agent message in this script was **rehearsed live** against the demo
ledger on `gemini-3.5-flash-lite`, and each produced the tool chain and result
shown below. Don't improvise new agent prompts on camera. Use these.

---

## Before you record (10 minutes)

### 1. Start the app on the clean recording ledger

A fresh ledger for recording is already seeded at `data/video`. To **reset it
before every take** (so Rahul's ₹40,000 invoice is unpaid again), run this from
the `freelanceflow` folder:

```bash
Remove-Item -Recurse -Force data\video; .venv\Scripts\python.exe -m app.seed --data-dir data/video
```

Then start the two servers, each in its own PowerShell window:

```bash
$env:FF_DATA_DIR="data/video"; .venv\Scripts\python.exe -m uvicorn app.api.main:app --port 8000
```

```bash
cd frontend; npm run dev
```

Open **http://localhost:5173**. The sidebar must say **Agent ready · Google
Gemini · gemini-3.5-flash-lite**.

### 2. Make the screen camera-ready

- Browser full screen (F11), zoom **110%** (Ctrl +), bookmarks bar hidden, no other tabs.
- Close notifications: Windows **Focus assist → Alarms only**.
- Open `docs/demo/slides.html` in a **second** full-screen browser window. Use the arrow keys to move between slides.

### 3. Mind the free-tier limit

Gemini's free tier limits requests **per minute**. The payment turn alone
makes about 5 model calls. **Leave about 30–60 seconds between agent
messages.** Trim the gap out when editing. If the Agent page ever says *"free-tier
limit reached"*, stop, wait a minute, reset the ledger and redo the take.
Your limits are listed at https://ai.dev/rate-limit.

### 4. Recording tool (free)

- **Clipchamp**, built into Windows 11: *Record & create → Screen and camera*, pick the browser window, microphone on. It also does the trimming.
- Or **OBS Studio** (free) if you prefer.

Record the **demo section in one continuous take**, then the **slide sections
separately**, and join them in Clipchamp. Agent replies take roughly 7–15
seconds. You may **speed up or cut the waiting**, but never cut in a result
from a different take.

---

## The script

Timings are targets. Voiceover lines are written to be read at a natural
pace, roughly 150 words a minute.

### 0:00–0:15 · Cold open *(screen: Agent page)*

**On screen:** type **`Rahul paid me ₹15,000 today`** and press Enter. Let the
trace appear, then the result card.

> **Voiceover:** "Rahul paid me fifteen thousand rupees today. That's all I
> typed. The agent found the client, found the right invoice and recorded the
> payment. And it showed its work."

*(If you record the cold open separately, reset the ledger before the main
demo take, so the payment happens again in the demo.)*

### 0:15–0:45 · The problem *(slide 2)*

> "Every independent freelancer is also their own accounts department. You
> raise invoices, chase late payments, match each bank transfer to the right
> invoice and keep receipts, usually across a spreadsheet, WhatsApp and a
> banking app. The work is small but constant, and the mistakes are
> expensive: a payment logged against the wrong invoice, a reminder sent for
> money that already arrived, a balance nobody trusts anymore."

### 0:45–1:05 · Who it's for *(slide 3)*

> "FreelanceFlow is for independent freelancers and very small studios:
> designers, developers, writers, consultants. They bill a handful of clients
> each month and don't have a bookkeeper. We built it for freelancers in India
> first: amounts in rupees, lakhs, Indian digit grouping, and UPI and NEFT
> payments."

### 1:05–1:30 · Why it matters *(slide 4)*

> "AI assistants can talk about your finances, but you can't trust them to
> keep your books. A language model will confidently give you a balance it
> never looked up. So we built FreelanceFlow around one rule: the AI decides
> what to do, and deterministic code does everything that touches money. It
> never invents a client, an invoice number or a rupee."

### 1:30–3:40 · Live demo *(screen recording, one take)*

**1:30 · Overview.** Point the cursor at the tiles and the *Needs attention* panel.

> "This is the dashboard, running live. Everything here is computed on the
> server from the ledger: outstanding money, what's overdue, what came in this
> month. Rahul Sharma's invoice FF-0005, forty thousand rupees, is still
> unpaid."

**1:50 · Invoices → click FF-0005.** Show status *Unpaid*, ₹40,000 outstanding, no payments.

> "Here's that invoice. Forty thousand outstanding, no payments yet."

**2:05 · Agent page.** Type **`Rahul paid me ₹15,000 today`** and press Enter.
While it works:

> "Now I just tell the agent what happened, the way I'd say it to a friend."

When the reply arrives, the **trace is already open** under your message.
Move the cursor down its rows, and click one row (e.g. `record_payment`) to show its arguments:

> "Look at the trace. These are real tool executions, not a loading
> animation. It found Rahul, parsed fifteen thousand rupees into an exact
> number, looked up his open invoices, recorded the payment in a database
> transaction and updated the invoice PDF. The tools themselves took a
> fraction of a second. The rest is the model deciding what to do."

Move the cursor to the **payment card**:

> "And this card isn't the AI's wording. It's built from what the payment
> tool actually returned: invoice total forty thousand, fifteen thousand paid,
> twenty-five thousand left on the invoice."

*(In the browser rehearsal the chain was `find_client → parse_amount →
get_outstanding_invoices → record_payment → generate_invoice_pdf`, 5 operations
in 12.6 s; on another run it also called `generate_receipt`. The model can
vary the order, and the trace shows whatever really ran, so describe what
you see on screen.)*

**2:50 · Wait ~30–60s off camera, then type:** **`Record ₹99,000 more against that same invoice`**

> "Now let me try to break it. Ninety-nine thousand more, on an invoice with
> only twenty-five thousand left."

When the refusal appears:

> "It refuses, quotes the real remaining balance, and writes nothing. The
> payment tool rejected it, and the agent is not allowed to claim success
> unless a tool says so."

*(Rehearsed: `parse_amount → record_payment → error`, reply names ₹25,000.00 outstanding, no result card.)*

**3:15 · Click "Open invoice" on the payment card.** Show *Partially paid*, ₹25,000 outstanding, the ₹15,000 payment in the history.
Open the **receipt** for that payment.

> "Back on the invoice: partially paid, twenty-five thousand outstanding, and
> the receipt is a real PDF, generated from the ledger, with Indian digit
> grouping."

**3:30 · Overdue page** (brief).

> "And everything the agent does, you can also do by hand: overdue
> invoices, reminder drafts, reports. The dashboard and the agent use the same
> tools, so there's no second, weaker path to your money."

### 3:40–4:15 · How it's built *(slide 5)*

> "Under the hood, it's a Strands Agents SDK agent with twenty-two
> deterministic Python tools for clients, invoices, payments, reports,
> reminders and documents. A Strands hook records every tool call, which is
> where that trace comes from. The model runs on Google Gemini, and the same
> agent also runs on Amazon Bedrock or a local model without code changes.
> FastAPI serves a React dashboard, and money is stored as integer paise, so
> nothing ever rounds."

### 4:15–4:30 · Trust *(slide 6)*

> "It's built to be trusted: five hundred and ninety-three automated tests,
> balances derived from the payment ledger rather than stored, overpayments
> refused, duplicates flagged, and server details kept out of the browser."

### 4:30–4:45 · Close *(slide 7)*

> "FreelanceFlow. Tell it what happened, and it keeps your books straight,
> without ever inventing a number. The code is open source, on GitHub."

**Stop. Total should land between 4:30 and 4:50.**

---

## If something goes wrong during a take

| What you see | Do this |
|---|---|
| "free-tier limit reached" | Wait 60 seconds, reset the ledger, restart the take |
| The agent asks "which invoice?" instead of recording | Answer it on camera ("FF-0005"). A clarifying question is correct behaviour and worth keeping |
| A reply takes over 30 seconds | Keep recording; cut the wait in editing |
| Sidebar says the agent is unavailable | The key isn't loaded: check `.env`, restart the API window |
| Anything else | Reset the ledger and redo the take. Never splice results from different takes |

## Upload checklist

- [ ] Under 5:00
- [ ] Problem, who it's for and why it matters are all spoken (0:15–1:30)
- [ ] The payment is shown happening live, with the trace visible
- [ ] The refusal is shown
- [ ] No API key, `.env` file or terminal with secrets visible on screen
- [ ] Uploaded as public or unlisted (YouTube or Loom), link tested in a private window
