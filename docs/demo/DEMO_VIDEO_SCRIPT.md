# FreelanceFlow: demo video script

**Runtime:** about 4:40 (hard limit 5:00) · **Voiceover:** about 560 words · **Format:** voiceover over slides and screen recording

## What the judges must hear, and where

| Requirement | Where it happens |
|---|---|
| The problem | Scene 2 (0:15) |
| Who it's for | Scene 3 (0:45) |
| Why it matters | Scene 4 (1:05) |
| A working version | Scenes 5–9 (1:30–3:45): four live agent actions |
| How it's built (Strands) | Scene 10 (3:45) |

## The story in one line

Aditi, a freelancer, tells FreelanceFlow what happened. The agent records a
payment, refuses a mistake, chases the balance and bills a new client. It
shows every step, and it never invents a number.

*(Aditi is an illustrative user. Rahul, Meera and the invoices are the demo
ledger's sample data.)*

---

## Part 1 · Prepare (10 minutes, once)

**1. Reset the demo data before every take.** This makes Rahul's ₹40,000
invoice unpaid again. Run it from the `freelanceflow` folder, with the API
window closed:

```bash
Remove-Item -Recurse -Force data\video; .venv\Scripts\python.exe -m app.seed --data-dir data/video
```

**2. Start the app**, each command in its own PowerShell window:

```bash
$env:FF_DATA_DIR="data/video"; .venv\Scripts\python.exe -m uvicorn app.api.main:app --port 8000
```

```bash
cd frontend; npm run dev
```

Open **http://localhost:5173**. The bottom of the sidebar must say **Agent
ready · Google Gemini · gemini-3.5-flash-lite**.

**3. Make the screen clean.**
- Chrome or Edge, full screen (F11), zoom 110%, one tab, bookmarks bar hidden.
- Windows notifications off (Focus assist → Alarms only).
- Open `docs/demo/slides.html` in a second full-screen window. The arrow keys change slides.
- No terminal, `.env` file or API key anywhere on screen.

**4. Respect the free tier.** Gemini's free tier limits requests per
minute. **Wait about 30 seconds after each agent reply before typing the
next message**, then cut the waiting in editing. If the page ever says
*"free-tier limit reached"*, wait a minute, reset the data and restart the take.

**5. Record with Clipchamp** (built into Windows 11): *Record & create →
Screen and camera*, choose the browser window, microphone on.
- Record **Scenes 5–9 as one continuous take** (the live demo).
- Record the slide scenes separately, then join everything in Clipchamp.
- You may cut or speed up waiting. Never paste in a result from a different take.

---

## Part 2 · The script

Each scene lists **what's on screen**, **what you do**, and **what you say**.
Speak at a relaxed pace. The timings leave room for it.

### Scene 1 · Hook · 0:00–0:15
**Screen:** the first 12 seconds of your demo take (Scene 6, the payment), reused as a teaser. Same take, same result, so no reset is needed.

> "*Rahul paid me fifteen thousand rupees today.* One sentence. The payment is
> recorded, the invoice is updated, a receipt is issued, and you can see every
> step the AI took to do it. This is **FreelanceFlow**."

### Scene 2 · The problem · 0:15–0:45
**Screen:** slide 2

> "Meet Aditi, a freelance designer. She's great at design, but every month
> she's also her own accounts department. She raises invoices, matches every
> UPI transfer to the right invoice, and chases the clients who are late. It
> all lives across a spreadsheet, WhatsApp and a banking app. The work is small
> but it never stops, and one mistake, like chasing a client who has already
> paid, costs her time, money and trust."

### Scene 3 · Who it's for · 0:45–1:05
**Screen:** slide 3

> "FreelanceFlow is for people like Aditi: independent freelancers and small
> studios, designers, developers, writers and consultants, who bill a handful of
> clients and don't have a bookkeeper. We built it for India first: rupees
> and lakhs, Indian number formatting, UPI and NEFT."

### Scene 4 · Why it matters · 1:05–1:30
**Screen:** slide 4

> "Late or mismatched payments hit a freelancer's cash flow directly. AI
> could take this work off her hands, but today's assistants can't be trusted
> with a ledger: they'll confidently state a balance they never looked up. So
> FreelanceFlow is built on one rule. The AI decides *what* to do.
> Deterministic code does everything that touches money."

### Scene 5 · The dashboard · 1:30–1:45  ▶ *start the continuous demo take*
**Screen:** Overview page.
**Do:** move the cursor across the top tiles, then to Rahul's FF-0005 row in *Needs attention*.

> "This is Aditi's dashboard, live. Every figure is calculated on the server
> from the ledger. Rahul's invoice, FF-0005, forty thousand rupees, is overdue
> and unpaid."

### Scene 6 · Record a payment by talking · 1:45–2:30
**Do:** click **Agent**. Type exactly:

```
Rahul paid me ₹15,000 today
```

Press Enter. While it works:

> "She doesn't fill in a form. She just says what happened."

**When the reply appears:** move the cursor down the trace under the message. Click the `record_payment` row to open its arguments.

> "This trace is the Strands agent's real tool calls, not an animation. It
> found Rahul, turned *fifteen thousand rupees* into an exact amount, matched
> his open invoice and recorded the payment in a single database transaction."

**Do:** move the cursor to the payment card. Click **View receipt**, hold for two seconds, then close it.

> "And this card comes straight from the payment tool's result, not the AI's
> wording: forty thousand invoiced, fifteen thousand paid, twenty-five
> thousand left. Plus a real receipt."

*(Rehearsed live: `find_client → parse_amount → get_outstanding_invoices →
record_payment → generate_invoice_pdf → generate_receipt`, about 15 seconds.
The model sometimes skips the receipt step. If **View receipt** is there,
the receipt is generated when you open it, so the scene still works. Describe
what's on screen.)*

### Scene 7 · Try to break it · 2:30–2:50
**Do:** wait ~30 seconds (cut later). Type exactly:

```
Record ₹99,000 more against that same invoice
```

> "Now let's try to break it: ninety-nine thousand more, on an invoice with only twenty-five thousand left."

**When the reply appears:**

> "Refused. It quotes the real balance and writes nothing. The agent can't
> claim success unless the tool says so."

*(Rehearsed live: `parse_amount → record_payment → error`, about 8 seconds, no card.)*

### Scene 8 · Chase the balance · 2:50–3:15
**Do:** wait ~30 seconds (cut later). Type exactly:

```
Draft a reminder for the balance Rahul still owes
```

**When the reminder card appears:** point at the message text, then click **Review in Reminders**. Hover over **Approve**, but don't click it.

> "It drafts the reminder from the invoice's own figures: the balance, the due
> date, how many days late. And it's only a draft. Nothing goes to a client
> until Aditi approves it."

*(Rehearsed live: `create_payment_reminder → prepared`, about 6 seconds. The
draft names FF-0005 and ₹25,000.00 outstanding.)*

### Scene 9 · Bill a new job in plain words · 3:15–3:45  ▶ *end of the continuous take*
**Do:** click **Agent**, wait ~30 seconds (cut later). Type exactly:

```
Create an invoice for Meera for 85k for brand guidelines, due in 30 days
```

**When the invoice card appears:** click **View PDF** and hold on the PDF for two seconds.

> "Last one. *Eighty-five k* becomes exactly eighty-five thousand rupees. The
> invoice number comes from the database, never from the model, and the PDF is
> ready to send."

*(Rehearsed live: `find_client → parse_amount → create_invoice →
generate_invoice_pdf`, about 10 seconds, creating FF-0011 for ₹85,000.00 due
in 30 days.)*

> **Running long?** Cut Scene 9 first. The video still covers every requirement without it.

### Scene 10 · How it's built · 3:45–4:15
**Screen:** slide 5

> "Under the hood, it's an agent built with the **Strands Agents SDK**,
> using twenty-two deterministic Python tools. A Strands hook records every tool
> call, which is the trace you just saw. The model is Google Gemini, behind
> one provider layer, so the same agent also runs on Amazon Bedrock or a local
> model. FastAPI serves the React dashboard, and money is stored as integer
> paise, so nothing ever rounds."

### Scene 11 · Built to be trusted · 4:15–4:30
**Screen:** slide 6

> "Five hundred and ninety-six automated tests. Balances derived from the
> payment ledger, never stored. Overpayments refused, duplicates flagged, and
> nothing sent without approval."

### Scene 12 · Close · 4:30–4:40
**Screen:** slide 7

> "FreelanceFlow. Freelancers say what happened, and their books stay right,
> without the AI ever inventing a number. It's open source, on GitHub."

---

## Part 3 · If something goes wrong

| On screen | What to do |
|---|---|
| "free-tier limit reached" | Stop. Wait 60 seconds, reset the data, restart the take |
| "temporary error… on Google's side" | Wait 10 seconds, send the same message again. If nothing was recorded, keep recording |
| The agent asks a question ("Which invoice?") | Answer it on camera ("FF-0005"). Asking instead of guessing is the point, so keep it |
| "Agent unavailable" in the sidebar | The key didn't load. Check `.env`, restart the API window |
| A reply takes over 30 seconds | Keep recording, then cut the wait |
| Anything else | Reset the data and redo the take |

## Part 4 · Before you upload

- [ ] Under 5:00
- [ ] The problem, who it's for and why it matters are all spoken
- [ ] The payment happens live with the trace visible
- [ ] The refusal is shown
- [ ] No API key, `.env` or terminal on screen
- [ ] Uploaded to YouTube or Loom as **Unlisted** (or Public), with the link tested in a private window
