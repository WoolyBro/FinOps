# Prompt 2 of 4 — page composition and the Agent screen

Paste after prompt 1 has finished. Same chat.

---

Two more sets of observed defects. Same rules: no global restyling, output the
complete changed files.

## 1. Panels are stretching instead of sizing to content

On `/`, the "Needs attention" panel is stretched to match "Recent activity"'s
height, leaving a large blank area below its four rows. The two-column grid is
stretching its children.

Add `items-start` to that grid so each panel sizes to its own content.

## 2. The Overview page is thin, and it shows

Content stops around 40% of the viewport height and the rest is empty canvas.
That is not a spacing problem — the page simply does not say enough.

Add one section below the two panels: a **"This month"** strip. Not more tiles —
a sentence and a bar:

- A plain sentence with real figures: "₹62,000.00 collected against
  ₹1,47,250.00 invoiced — 42% of what you billed this month."
- Beneath it a 4px full-width track in `--line` with an `--accent` fill at that
  percentage.
- To its right, two small figures: "Oldest unpaid — 37 days" and "Average time
  to payment — 24 days", each a 12px `--ink-muted` label above a 15px value.

Do not add filler anywhere else. On `/invoices`, once rows are 52px the table
will occupy more height; if it still ends before the fold, that is correct. A
table that ends is fine.

## 3. The Agent page — the screen that has to be convincing

This is the most important screen in the product and it currently has four
problems.

### 3.1 The composer is floating in the middle of the page

It sits at roughly 55% of viewport height with empty canvas above *and* below
it. It reads as a broken layout.

Make the page a flex column at `height: 100dvh`:

- the transcript is `flex: 1; overflow-y: auto` with bottom padding,
- the composer is a fixed-height sibling pinned at the bottom with a 1px top
  border in `--line` and a `--surface` background,
- the transcript auto-scrolls to the newest turn on mount and after each send.

### 3.2 The tool trace is collapsed by default, so it is invisible

All the user currently sees is "4 operations · 1.9s [hide]". That trace is the
single most important element on the page — it is what distinguishes this from
a chatbot.

**Expand it by default.** Collapsing is a user action, not an initial state.

### 3.3 The proportional duration bars were never built

Behind each trace row, render a bar: `height: 6px`, `background:
var(--accent-wash)`, `border-radius: 3px`, absolutely positioned at the row's
left edge, width set to that call's share of the turn's total duration. The
tool name and the timing sit above it.

Seeing `record_payment` visually consume most of the turn is what makes the
trace read as real telemetry rather than four decorative ticks. It is one line
of arithmetic and it is worth more than any amount of styling.

### 3.4 The failed-call exchange is missing

The seeded transcript has exactly one turn, and it succeeds. A demo that only
ever succeeds looks staged.

Add a second exchange to the seeded transcript:

- **User:** "mark FF-0004 as paid"
- **Trace:** `find_client` succeeds (0.19s); `record_payment` **fails** (0.24s) —
  its row renders in `--bad-ink` with a drawn cross, and the error prints
  verbatim beneath it: `Invoice FF-0004 has ₹28,500.00 outstanding; no amount
  was given.`
- **Reply:** "I did not record anything. FF-0004 has ₹28,500.00 outstanding and
  you did not say how much Priya paid. Tell me the amount and I will record it."

The reply must ask for the missing information rather than claiming success or
apologising at length. No result card follows a failed turn.

### 3.5 The composer's helper row is clumsy

"Enter to send · Shift+Enter for newline" currently occupies its own full-width
row inside the input box. Move it outside the textarea, as 11.5px
`--ink-faint` text sitting on the same line as the Send button, left of it.
