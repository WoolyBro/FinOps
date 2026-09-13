# FreelanceFlow — UI generation prompt for Google AI Studio

Paste everything below the line into AI Studio (Build mode, Gemini). It is
written to be self-contained: the model does not need this repository to
produce the interface.

---

You are a senior product designer and front-end engineer. Build a complete,
production-quality web dashboard for a real product. Read the entire brief
before writing any code, and follow the prohibitions in section 2 literally —
they are the difference between an acceptable result and a rejected one.

## 1. The product

**FreelanceFlow** is a billing operations tool for independent freelancers in
India. A freelancer uses it to track clients, issue invoices, record incoming
payments, chase overdue money, and see where they stand financially.

It has two ways of doing the same work:

- **Direct manipulation** — tables, forms, detail pages. Everything is doable
  by hand.
- **An AI agent** — the freelancer types "Rahul paid me ₹15,000 today" and the
  agent selects and executes the same underlying operations, then reports what
  it did.

The agent is not a chatbot bolted on the side. It is a second control surface
over identical business logic. The UI must make that legible: when the agent
acts, the user sees exactly which operations ran, in what order, with what
result. Never present the agent as magic.

**Currency is INR.** Amounts use Indian digit grouping: ₹1,50,000.00 —
₹1,25,50,000.00 — not ₹150,000.00. Money is stored as integer paise and always
arrives from the server pre-formatted in an `*_display` field. **The UI never
does money arithmetic and never re-formats a currency value.** Render the
`_display` string the server gave you. This is a hard rule; a billing interface
that computes its own totals will eventually disagree with the invoice PDF, and
that is a defect, not a rounding difference.

## 2. Aesthetic direction — and what is forbidden

The reference is **Stripe's dashboard**: dense, calm, information-first,
confident with whitespace, zero decoration that does not carry meaning. Think
financial infrastructure, not a SaaS landing page.

### Forbidden — do not produce any of these

- Purple/pink or blue/teal **gradient backgrounds**, gradient text, gradient
  buttons, gradient borders, animated gradient blobs, mesh gradients.
- **Glassmorphism** — no `backdrop-blur` cards, no translucent frosted panels.
- **Neumorphism**, heavy inner shadows, embossed anything.
- **Emoji anywhere in the interface.** No 🚀 ✨ 💰 📊 in headings, buttons, empty
  states, or toasts. Icons are line SVGs only.
- **Dark-mode-by-default with neon accents.** This is a light interface.
- The words "seamless", "powerful", "effortless", "revolutionize", "supercharge",
  "unlock", "elevate", "AI-powered" in any user-facing copy.
- A marketing hero section, a pricing table, testimonials, a feature grid with
  three centred icon cards, or a "Get started in seconds" CTA. This is an
  application the user is already logged into.
- Rounded-full pill buttons everywhere, oversized 20px+ border radii, drop
  shadows larger than the element casting them.
- Centre-aligned body text. Centre-aligned table cells.
- Placeholder lorem ipsum, fake logos, "Company Inc." Use the realistic Indian
  freelance data specified in section 8.
- Framer Motion page transitions, scroll-triggered reveals, parallax, confetti,
  typewriter effects, animated counters that tick up.

### Required

**Palette** — use exactly these values as CSS custom properties:

```
--canvas:        #f6f9fc   /* page background — blue-tinted, never grey */
--surface:       #ffffff
--surface-sunken:#f7fafc   /* table headers, inset rows */

--ink:           #0a2540   /* headings — navy, never pure black */
--ink-strong:    #1a1f36   /* body default */
--ink-body:      #3c4257
--ink-muted:     #697386   /* secondary text, labels */
--ink-faint:     #8792a2   /* timestamps, hints */

--line:          #e3e8ee
--line-strong:   #d5dbe1

--accent:        #635bff   /* indigo — the ONLY accent colour */
--accent-hover:  #7a73ff
--accent-ink:    #3f37d6
--accent-wash:   #f0efff   /* active nav background */

--ok-bg:   #cbf4c9   --ok-ink:   #0e6245   /* paid */
--warn-bg: #fcedb9   --warn-ink: #983705   /* partially paid, draft */
--bad-bg:  #fde2dd   --bad-ink:  #a41c4e   /* overdue */
--neutral-bg: #e3e8ee  --neutral-ink: #3c4257  /* unpaid, cancelled */
```

**Elevation** — soft, layered, low-opacity navy. Never black shadows.

```
--shadow-xs: 0 1px 1px rgba(10,37,64,.04);
--shadow-sm: 0 1px 3px rgba(50,50,93,.08), 0 1px 2px rgba(10,37,64,.04);
--shadow-md: 0 4px 12px rgba(50,50,93,.10), 0 1px 3px rgba(10,37,64,.06);
--shadow-lg: 0 15px 35px rgba(50,50,93,.12), 0 5px 15px rgba(10,37,64,.08);
```

**Radii:** 8px on panels and cards, 6px on buttons, inputs and badges. Nothing
larger except the 50% on status dots.

**Typography:** Inter (or the system UI stack). Base size **14px**, line-height
1.5. Page titles 24px / weight 660 / letter-spacing -0.021em. Panel headings
14px / 600. Metric values 25px / 620 / letter-spacing -0.028em. Uppercase
section labels 11px / 600 / letter-spacing 0.06em / `--ink-faint`.

**All numerals in tables and metrics use `font-variant-numeric: tabular-nums`**
so columns align. Invoice numbers, receipt numbers and references render in a
monospace face.

**Density:** table rows ~44px tall, 12px vertical / 16px horizontal cell
padding. Panels have a 14px/18px header separated by a 1px `--line`. Page
gutters 28px top, 34px sides. Main content max-width 1240px.

**Motion:** 120ms ease on hover/background transitions only. Nothing else moves.
Respect `prefers-reduced-motion`.

**Borders over shadows for structure; shadows only to lift a surface off the
canvas.** Every panel is `1px solid var(--line)` + `--shadow-sm`.

## 3. Stack

- React with TypeScript, function components, hooks.
- Tailwind is acceptable, but the palette above must be defined as CSS custom
  properties and referenced through them — not hard-coded hexes scattered
  through class strings. Plain CSS modules or a single stylesheet is equally
  fine and often cleaner here.
- **No component library** (no MUI, Chakra, Ant, shadcn). Build the primitives.
- **No chart library.** The one chart in section 5.9 is hand-rolled SVG.
- Icons: inline 16×16 line SVGs, `stroke="currentColor"`, `stroke-width="1.5"`,
  `fill="none"`. Draw them yourself. No icon package.
- All data access goes through **one module, `lib/api.ts`**, exporting a single
  `api` object with one method per endpoint (section 6). Every component calls
  that module and nothing else. Ship it backed by the mock dataset in section 8
  behind a `USE_MOCK` flag, with the real `fetch` implementation written out and
  ready — swapping one constant must be the entire migration to the live server.

## 4. Layout shell

A fixed two-column grid: `232px` sidebar, `minmax(0, 1fr)` main. The sidebar is
white, `sticky`, full viewport height, `border-right: 1px solid var(--line)`.

**Sidebar contents, top to bottom:**

1. **Brand** — a 28px rounded-7px square with a subtle indigo gradient
   (`linear-gradient(160deg, #635bff, #4b45c6)`) containing a white "F", then
   "FreelanceFlow" at 14.5px/600 with "Billing operations" beneath it at
   11.5px/400 in `--ink-faint`. *(This gradient is the single permitted
   gradient in the entire interface.)*

2. **Grouped navigation.** Groups have small uppercase labels; the first group
   has none:

   - *(no label)* — Overview `/`, Agent `/agent`
   - **Billing** — Invoices `/invoices`, Clients `/clients`, Payments `/payments`
   - **Collections** — Overdue `/overdue`, Reminders `/reminders`
   - **Insights** — Reports `/reports`

   Each link is icon + label, 13.5px/500, 7px/8px padding, 6px radius. Hover:
   `--surface-sunken` background. Active: `--accent-wash` background,
   `--accent-ink` text, weight 600, icon at full opacity (0.75 otherwise).
   **A detail page keeps its parent section highlighted** — `/invoices/8` shows
   Invoices as active.

3. **Provider status badge**, pinned to the bottom (`margin-top: auto`) above a
   1px top border. Shows a 6px status dot with a soft ring
   (`box-shadow: 0 0 0 2.5px rgba(...)`) — green `#0e9f6e` when the agent is
   reachable, grey `--ink-faint` when not — then a bold line of status and a
   smaller detail line, e.g.

   ```
   ● Agent ready
   Amazon Bedrock · nova-pro
   ```
   or
   ```
   ● Agent unavailable
   Model access not enabled for this region
   ```
   or, if the API itself is unreachable:
   ```
   ● Backend offline
   Could not reach the API at localhost:8000
   ```

   Long model ids must wrap (`overflow-wrap: anywhere`), never overflow.

**Every page header** is a flex row: a left block with the 24px page title and a
`--ink-muted` subtitle (max 62ch), and a right block of actions. It wraps on
narrow viewports.

## 5. The pages

Build all ten. Each gets its own real screen — none may be a filtered view of
another with a different title.

### 5.1 Overview `/`

The answer to "where do I stand right now", above the fold, no scrolling.

- Four metric tiles in an auto-fit grid (`minmax(200px, 1fr)`, 14px gap):
  **Outstanding**, **Overdue** (value in `--bad-ink`), **Received this month**,
  **Active clients**. Each is a 12px/550 `--ink-muted` label above a 25px value,
  with an optional 12px `--ink-faint` note beneath ("across 6 invoices").
- **Needs attention** panel — up to 5 most-overdue invoices, worst first, each
  row: days-overdue badge, invoice number, client, outstanding, and a
  *Record payment* button. A "View all" link in the panel header.
- **Recent activity** panel — the last 8 events merged from invoices and
  payments into one reverse-chronological list. Each row is a one-line sentence
  with the amount emphasised: "Payment of ₹15,000.00 from Rahul Sharma against
  FF-0007" / "Invoice FF-0012 issued to Meera Iyer for ₹85,000.00", with a
  relative timestamp on the right ("2 days ago").
- A single-line agent affordance under the header: a text input reading
  *"Tell FreelanceFlow what happened…"* that navigates to `/agent` with the
  typed text pre-submitted. Not a floating bubble. Not a modal.

### 5.2 Agent `/agent` — the centrepiece

A conversation, but an auditable one.

Layout: a scrolling transcript with a composer pinned to the bottom of the
content column. Max-width ~760px for the transcript so lines stay readable.

- **User turns**: right-aligned, `--accent-wash` background, 6px radius,
  `--ink` text. No avatar.
- **Agent turns**: left-aligned on plain canvas, no bubble, no avatar. Body
  copy at 14px.
- **Between the user turn and the agent's reply, render the tool trace.** This
  is the most important component in the product. It is a bordered panel,
  `--surface-sunken`, containing an ordered list of the operations the agent
  ran:

  ```
  ┌─────────────────────────────────────────────────┐
  │ 3 operations · 1.8s                    [ hide ] │
  ├─────────────────────────────────────────────────┤
  │ ✓  find_client            {"name":"Rahul"}  0.2s│
  │ ✓  parse_amount           {"text":"15k"}    0.1s│
  │ ✓  record_payment      {"invoice_id":7,…}   1.5s│
  └─────────────────────────────────────────────────┘
  ```

  Each row: a status glyph (a drawn check in `--ok-ink`, a drawn cross in
  `--bad-ink` — **not emoji**), the tool name in monospace, the arguments
  collapsed to a single truncated line, and the duration right-aligned in
  `--ink-faint`. Clicking a row expands it to show the full arguments as
  pretty-printed JSON in a monospace block. The whole panel is collapsed to its
  summary line by default and remembers its state per turn.

  While a turn is in flight, show the trace building: rows appear as they are
  reported, the in-flight row carries a small pulsing dot instead of a check.
  If a tool returned an error, its row is `--bad-ink` and the error message
  renders beneath it verbatim — never rewritten, never hidden.

- **Result cards.** When a turn produced a document or mutated a record, the
  agent's reply is followed by a compact card — an invoice card with number,
  client, amount, status badge and a *Download PDF* action; or a payment card
  with the amount, the invoice it landed against, and the new outstanding
  balance. This is how the user verifies without leaving the conversation.
- **Composer**: a textarea that grows to a 5-line maximum, Enter to send,
  Shift+Enter for a newline, a *Send* button that is disabled while a turn is
  running. Below it, four suggestion chips on an empty transcript — real
  sentences, not commands:
  *"Rahul paid me ₹15,000 today"* · *"Who owes me money?"* ·
  *"Create an invoice for Meera for 85k for the brand redesign"* ·
  *"Draft reminders for everything overdue"*
- **When the agent is unavailable**, replace the composer with a bordered
  notice stating exactly why (from the status endpoint's `detail`) and a line
  saying every operation remains available manually, with links to Invoices and
  Payments. Do not disable the page. Do not show a fake reply. **Never
  fabricate an agent response under any circumstance.**

### 5.3 Invoices `/invoices`

- Header actions: a filter segmented control — All · Unpaid · Partially paid ·
  Paid · Overdue — and a primary *New invoice* button.
- A search input filtering by client name, invoice number or project, live.
- **Six columns, and no more.** Widening the table until a column falls off the
  panel edge is a failure mode to avoid:

  | Invoice | Client | Amount | Status | Due | Actions |
  |---|---|---|---|---|---|

  - *Invoice* — monospace number, links to the detail page.
  - *Client* — a stacked cell: client name at `--ink` on the first line, the
    project name at 12px `--ink-faint` on the second. **Do not use
    `white-space: nowrap` on this cell**; let it wrap.
  - *Amount* — right-aligned, tabular, with outstanding beneath it in 12px
    `--ink-faint` when partially paid ("₹25,000.00 outstanding").
  - *Status* — badge (section 7).
  - *Due* — formatted date, `--ink-muted`; if overdue, a red days-overdue badge
    beside it.
  - *Actions* — right-aligned; *Record payment* (primary, hidden when paid) and
    a *PDF* link when the document exists.

  Wrap the table in an `overflow-x: auto` container so it can never push the
  page into horizontal scroll.

- **New invoice modal** — a centred dialog, `--shadow-lg`, closable on Escape
  and backdrop click, focus trapped:
  1. **Client** — a combobox that searches existing clients as you type and
     offers *"Create 'Meera Iyer' as a new client"* as the last option when
     nothing matches.
  2. **Project** — text, required.
  3. **Amount** — a text field that accepts shorthand. As the user types "40k"
     or "1.5 lakh", show the parsed result live beneath the field in
     `--ink-muted`: *"₹40,000.00"*. **The parse is done by the server, not in
     the browser** — call the parse endpoint (debounced 300ms) and render what
     comes back. If the server cannot parse it, show its message and disable
     submit.
  4. **Issue date** (defaults today) and **Due date** (optional).
  5. **Description** — optional textarea.

  If the server responds that a near-identical invoice already exists, do not
  treat it as an error: render an inline amber warning naming the existing
  invoice, with *Cancel* and *Create anyway* — the second resubmits with the
  duplicate override set.

### 5.4 Invoice detail `/invoices/:id`

- Header: monospace invoice number as the title, status badge beside it,
  client name and project as the subtitle. Actions: *Download PDF*,
  *Record payment*.
- A three-tile row: **Invoice amount**, **Paid**, **Outstanding**.
- Beneath the tiles, a **payment progress bar** — a 6px track in `--line` with
  an `--accent` fill, labelled "₹15,000.00 of ₹40,000.00 · 37% paid". Fill turns
  `--ok-ink` at 100%.
- A **details** panel: issue date, due date, currency, description, created
  timestamp — a two-column definition list, labels in `--ink-muted`.
- A **payments against this invoice** panel: date, amount, method, reference,
  receipt number (monospace, linking to the receipt PDF), outstanding after.
  Empty state: "No payments recorded against this invoice yet."

### 5.5 Clients `/clients`

- Header action: *Add client*.
- A card grid, `minmax(280px, 1fr)`, not a table — clients are entities you
  browse, not rows you scan. Each card: name at 15px/600, email and phone in
  `--ink-muted` beneath, then a thin divider and two figures side by side —
  **Outstanding** and **Overdue** (red when non-zero) — and a footer line
  "7 invoices · 4 paid". The whole card is a link to the detail page; hover
  lifts it to `--shadow-md`.
- **Add client modal**: name (required), email, phone, address. If the server
  reports a possible duplicate, show the existing client inline with
  *Use existing* and *Create anyway*.

### 5.6 Client detail `/clients/:id`

- Header: client name; subtitle shows email and phone with an *Edit* action
  that turns each field into an inline editable control (pencil affordance,
  Enter commits, Escape cancels) — a modal is overkill for editing a phone
  number.
- Four tiles: **Invoiced**, **Paid**, **Outstanding**, **Overdue**.
- A small status distribution strip: "4 paid · 2 unpaid · 1 overdue" rendered
  as inline badges with counts.
- Two panels: **Invoices** (same six-column shape as 5.3, scoped) and
  **Payments** (as 5.7, scoped).

### 5.7 Payments `/payments`

The ledger. Reverse-chronological, this is the audit trail.

| Date | Amount | Client | Invoice | Method | Receipt |

Amount right-aligned and tabular; Client stacked with project; Invoice a
monospace link; Method a neutral badge with the reference beneath in
`--ink-faint`; Receipt a monospace number linking to the receipt PDF.

A date-range filter and a client filter in the header. A single **Total
received in range** tile above the table.

### 5.8 Overdue `/overdue` and Reminders `/reminders`

**Overdue** is collections, not a filtered invoice list — the ordering *is* the
feature. Sorted most-overdue first. Three tiles: **Total overdue**, **Invoices
late**, **Longest overdue** (with the client's name as the tile note). Columns:
Late by (red days badge) · Invoice · Client · Outstanding · Due · Actions, where
Actions are *Draft reminder* and *Record payment*.

The subtitle must explain the derivation: *"Past their due date with money still
owed, most overdue first. Nothing here is stored — it is worked out from due
dates and the payment ledger each time you look."*

**Reminders** lists drafted messages, grouped by status (Draft · Approved ·
Sent). Each is a panel showing the client, the invoice it concerns, the channel,
the created timestamp, and **the full message body in a bordered inset block
with preserved line breaks** — the freelancer must read the exact words before
approving. Draft cards carry *Approve* and *Discard*; approved cards carry
*Copy message* and a `--ink-muted` note: *"Approved messages are not sent
automatically — copy the text and send it yourself."* That is a deliberate
product decision, not a limitation; the copy should not apologise for it.

### 5.9 Reports `/reports`

- A date-range control in the header: presets (This month · Last month · This
  quarter · This financial year · Custom) plus two date inputs. Indian financial
  year runs April to March — the preset must reflect that.
- Four tiles: **Invoiced in period**, **Received**, **Outstanding**, **Overdue**.
- One **hand-rolled SVG chart**: monthly invoiced vs received over the last six
  months, as paired bars. Invoiced in `--line-strong`, received in `--accent`.
  Axis labels 11px `--ink-faint`, a single horizontal gridline set, values on
  hover via a small tooltip. No animation, no library, no gradient fills.
- A **breakdown by client** table: client, invoiced, received, outstanding,
  sorted by outstanding descending.
- An **invoices issued in period** count with the status distribution.

## 6. Data contracts

Type these exactly. Every `*_display` field is a server-formatted string to be
rendered verbatim; every `*_minor` field is integer paise, used only for
comparisons and for sending back to the server.

```ts
type CurrencyTotal = { currency: string; total_minor: number; total_display: string };

type Invoice = {
  invoice_id: number; invoice_number: string;
  client_id: number; client_name: string;
  project: string; description: string | null;
  currency: string;
  amount_minor: number; amount_paid_minor: number; outstanding_minor: number;
  amount_display: string; amount_paid_display: string; outstanding_display: string;
  issue_date: string; due_date: string | null;
  invoice_status: "UNPAID" | "PARTIALLY_PAID" | "PAID" | "CANCELLED";
  is_overdue: boolean; days_overdue: number;
  pdf_available: boolean;   // the server never sends a filesystem path
};

type Payment = {
  payment_id: number; invoice_id: number; invoice_number: string;
  client_id: number; client_name: string; project: string;
  amount_minor: number; amount_display: string;
  payment_date: string; method: string | null; reference: string | null;
  receipt_number: string | null; outstanding_after_display: string;
};

type Client = {
  client_id: number; name: string;
  email: string | null; phone: string | null; address: string | null;
  created_at: string;
};

type ClientBalance = {
  client_id: number; client_name: string;
  invoice_count: number; invoice_counts_by_status: Record<string, number>;
  invoiced_total: CurrencyTotal[]; paid_total: CurrencyTotal[];
  outstanding_total: CurrencyTotal[]; overdue_total: CurrencyTotal[];
};

type Summary = {
  period_start: string; period_end: string;
  received_total: CurrencyTotal[]; outstanding_total: CurrencyTotal[];
  overdue_total: CurrencyTotal[];
  invoices_issued_in_period: number;
  invoice_counts_in_period: Record<string, number>;
};

type Reminder = {
  reminder_id: number; invoice_id: number; invoice_number: string;
  client_id: number; client_name: string; client_email: string | null;
  project: string; channel: string; message: string;
  reminder_status: "DRAFT" | "APPROVED" | "SENT" | "CANCELLED";
  created_at: string; sent_at: string | null;
};

type AgentStatus = {
  available: boolean; provider: string | null; model_id: string | null;
  detail: string | null; active_sessions: number;
};

type ToolCall = {
  tool: string; arguments: Record<string, unknown>;
  status: string | null; error: string | null; duration_seconds: number | null;
};

type ChatResponse = {
  session_id: string; reply: string; tool_calls: ToolCall[];
  turn: number; elapsed_seconds: number;
};

type ParsedAmount = { amount_minor: number; currency: string; amount_display: string };
```

Note that totals are **arrays** of `CurrencyTotal`, not scalars. Render an empty
array as "₹0.00" on a money tile and as "—" elsewhere; render multiple entries
joined by "  ·  ".

**Endpoints** (base `http://localhost:8000`):

```
GET   /api/health
GET   /api/agent/status
POST  /api/chat                        { message, session_id }        -> ChatResponse
GET   /api/clients                     -> { count, clients }
POST  /api/clients                     { name, email?, phone?, address? }
GET   /api/clients/:id                 -> { balance, invoices, payments }
PATCH /api/clients/:id                 { field, value }
GET   /api/invoices                    -> { count, invoices }
POST  /api/invoices                    { client_id, project, amount_minor, currency?,
                                         issue_date?, due_date?, description?,
                                         allow_duplicate? }
GET   /api/invoices/:id                -> { invoice, payments }
GET   /api/invoices/:id/pdf            -> application/pdf
GET   /api/payments                    -> { count, payments }
POST  /api/payments                    { invoice_id, amount_minor, payment_date?,
                                         method?, reference?, allow_duplicate? }
GET   /api/payments/:id/receipt        -> application/pdf
GET   /api/reminders?status=&client_id=
POST  /api/reminders                   { invoice_id, force }
POST  /api/reminders/:id/approve
GET   /api/reports/summary?start_date=&end_date=
GET   /api/reports/overdue             -> { count, invoices, overdue_total }
GET   /api/reports/outstanding         -> { count, invoices, outstanding_total }
POST  /api/amounts/parse               { text, default_currency } -> ParsedAmount
```

**Error contract.** Failures return `{ error: string, detail: string }`. A
**409** is not a crash — it is the server declining a probably-duplicate write,
and the UI must render `detail` as an inline amber warning with a *Create
anyway* path that resends with `allow_duplicate: true`. A **422** is a
validation failure: bind `detail` to the offending field. A network failure
becomes "Could not reach the API at {base}. Is the backend running?" Always
surface the server's own wording; never replace it with "Something went wrong".

## 7. Component primitives

Build these once and use them everywhere.

- **Badge** — 11.5px/600, 2px/8px padding, 6px radius, pastel background with
  its saturated ink colour. Mapping: `PAID` → ok · `PARTIALLY_PAID` → warn ·
  `UNPAID` → neutral · `CANCELLED` → neutral, text struck through ·
  overdue / `days_overdue` → bad · `DRAFT` → warn · `APPROVED` → ok ·
  `SENT` → neutral.
- **Button** — three variants. *Default*: white, `1px solid --line-strong`,
  `--ink-body`, `--shadow-xs`, hover `--surface-sunken`. *Primary*: `--accent`
  background, white, `--shadow-sm`, hover `--accent-hover`. *Danger*: white with
  `--bad-ink` text and border. All: 13px/550, 6px/12px padding, 6px radius,
  visible `:focus-visible` ring (2px `--accent`, 2px offset). A disabled button
  is 50% opacity with `cursor: not-allowed`, and a busy button shows its own
  progress in its label ("Recording…") rather than a spinner overlay.
- **Panel** — white surface, `1px solid --line`, 8px radius, `--shadow-sm`,
  `overflow: hidden`, optional 14px/18px header with a bottom border.
- **Stat tile** — as specified in section 2's typography.
- **Table** — `--surface-sunken` header row, 11.5px/600 uppercase
  `--ink-muted` headers with 0.04em tracking, 1px `--line` row separators, no
  outer border of its own (the panel supplies it), hover row background
  `--surface-sunken`, numeric columns right-aligned and tabular.
- **Modal** — 480px default (640px for the invoice form), centred, white,
  `--shadow-lg`, backdrop `rgba(10,37,64,.28)`. Escape closes, focus is trapped,
  focus returns to the trigger on close, the body scroll locks.
- **Toast** — bottom-right, white, `--shadow-md`, 1px `--line`, auto-dismiss at
  3.2 seconds, stacking. Text is a plain factual sentence: "Payment recorded —
  balance updated". No emoji, no exclamation marks.
- **Loading** — skeleton rows matching the real row height for tables, and a
  quiet "Loading invoices…" line for panels. **No spinners on full pages, no
  progress bars at the top of the viewport.**
- **Empty state** — inside the panel, centred, ~48px vertical padding: a bold
  line then a `--ink-muted` explanation, and an action when one makes sense.
  Write them specifically:
  - Invoices: "**No invoices yet** — Create one, or tell the agent who to bill."
  - Overdue: "**Nothing is overdue** — Every invoice with a due date has either
    been paid or is still within terms."
  - Payments: "**No payments recorded** — Payments you record will appear here
    as a permanent ledger."
  - Reminders: "**No reminders drafted** — Draft one from any overdue invoice."
- **Error state** — a bordered `--bad-bg`-tinted panel with the server's
  message and a *Retry* button.

## 8. Mock data

Realistic Indian freelance work. Use these exact records so screens look
plausible and the maths is consistent.

**Clients:** Rahul Sharma (rahul@nexbuild.in, +91 98200 41122) · Meera Iyer
(meera@saffronstudio.co, +91 99401 77390) · Arjun Nair (arjun@finlytics.io) ·
Priya Deshmukh (priya@kitehouse.in, +91 98330 20514) · Vikram Rao
(vikram@orbitlabs.dev) · Sana Qureshi (sana@twelfthfloor.in, +91 97690 88214).

**Invoices** — numbers are gapless and sequential, `FF-0001` upward:

| # | Client | Project | Amount | Issued | Due | Status |
|---|---|---|---|---|---|---|
| FF-0001 | Rahul Sharma | E-commerce site build | ₹1,50,000.00 | 2026-05-14 | 2026-06-13 | PAID |
| FF-0002 | Meera Iyer | Brand identity refresh | ₹85,000.00 | 2026-06-02 | 2026-07-02 | PAID |
| FF-0003 | Arjun Nair | Dashboard UX audit | ₹42,000.00 | 2026-06-21 | 2026-07-21 | PAID |
| FF-0004 | Priya Deshmukh | Marketing site copy | ₹28,500.00 | 2026-07-05 | 2026-08-04 | OVERDUE, unpaid |
| FF-0005 | Rahul Sharma | Payment gateway integration | ₹40,000.00 | 2026-07-19 | 2026-08-18 | PARTIALLY_PAID, ₹15,000.00 paid |
| FF-0006 | Vikram Rao | API documentation | ₹36,000.00 | 2026-07-28 | 2026-08-27 | OVERDUE, unpaid |
| FF-0007 | Sana Qureshi | Design system components | ₹1,25,000.00 | 2026-08-11 | 2026-09-10 | UNPAID |
| FF-0008 | Meera Iyer | Packaging illustration set | ₹64,000.00 | 2026-08-24 | 2026-09-23 | UNPAID |
| FF-0009 | Arjun Nair | Analytics implementation | ₹55,000.00 | 2026-09-01 | 2026-10-01 | UNPAID |
| FF-0010 | Priya Deshmukh | Landing page redesign | ₹32,000.00 | 2026-09-06 | 2026-10-06 | UNPAID |

Today is **2026-09-10**, so FF-0004 is 37 days overdue and FF-0006 is 14 days
overdue. Derive every days-overdue figure from that date; do not hard-code
inconsistent numbers.

**Payments** — receipts `RC-0001` upward, methods drawn from UPI, NEFT, Bank
transfer, Cheque: FF-0001 settled in two payments (₹75,000.00 on 2026-05-20 via
NEFT, ₹75,000.00 on 2026-06-11 via NEFT) · FF-0002 in full on 2026-06-28 by UPI ·
FF-0003 in full on 2026-07-15 by UPI · FF-0005 ₹15,000.00 on 2026-09-10 by UPI,
reference `UPI/523901147722`.

**Reminders:** one DRAFT for FF-0004 and one APPROVED for FF-0006, each with a
real three-sentence message that names the invoice number, the amount and the
number of days overdue, and closes politely — the kind of message a freelancer
would actually send, not a template with `{{placeholders}}`.

**Agent status:** available, provider "bedrock", model
`apac.amazon.nova-pro-v1:0`, 1 active session.

**A pre-seeded agent transcript** demonstrating the tool trace, exactly one
exchange: user *"Rahul paid me ₹15,000 today"* → tool calls `find_client`
(0.21s), `list_invoices` (0.18s), `parse_amount` (0.09s), `record_payment`
(1.32s) → reply *"Recorded ₹15,000.00 from Rahul Sharma against FF-0005
(Payment gateway integration). That leaves ₹25,000.00 outstanding on the
invoice, due 18 August 2026. Receipt RC-0005 is ready."* followed by a payment
result card.

## 9. Copy rules

Write like a competent accountant, not like marketing.

- Plain declaratives. "Recorded ₹15,000.00 from Rahul Sharma." Not "Payment
  successfully recorded! 🎉"
- Explain derivations where a user might doubt a number: the overdue subtitle
  in 5.8 is the model for this. Balances are computed from the ledger every
  time, never stored — say so where it builds trust.
- Dates render as "18 August 2026" in prose and "18 Aug 2026" in table cells.
  Relative time ("2 days ago") only in the activity feed.
- Never apologise for a deliberate constraint. Reminders not auto-sending is a
  design choice; state it neutrally.
- Button labels are verbs: *Record payment*, *Draft reminder*, *Create anyway*,
  *Approve*. Never *Submit*, *OK*, *Click here*.

## 10. Accessibility and responsiveness

- Semantic landmarks: `<nav>`, `<main>`, real `<table>` with `<th scope>`.
- `aria-current="page"` on the active nav link. `aria-live="polite"` on the
  toast region and on the agent transcript.
- Every icon-only control has an `aria-label`. Modals use
  `role="dialog" aria-modal="true"` with a labelled title.
- Keyboard: full tab order, Escape closes modals, Enter submits forms, the
  agent composer's Enter/Shift+Enter split as specified.
- Contrast: all body text meets 4.5:1 on its background. `--ink-faint` is for
  12px+ secondary text only, never for anything essential.
- Below 900px the sidebar collapses to a top bar with a slide-in drawer; metric
  grids reflow to two columns then one; tables keep their horizontal scroll
  container rather than collapsing into cards.

## 11. Deliverable

A complete, runnable React + TypeScript application implementing all ten pages,
every modal, every state (loading, empty, error, populated, in-flight), the
shared primitives, and `lib/api.ts` with both the mock and live implementations.

Organise it sensibly — `components/` for primitives, `pages/` or `app/` for
screens, `lib/` for the API module and formatting helpers, one stylesheet
holding the token definitions.

Do not stub anything with `// TODO`. Do not summarise what you would build.
Build it.

---

*Generated for the FreelanceFlow hackathon submission. If Gemini's output drops
pages, re-prompt with: "Continue — you did not produce sections 5.6 through 5.9.
Output those files now, same conventions." Generating in two passes (shell +
Overview + Agent first, then the remaining seven pages) reliably beats asking
for everything in one shot.*
