# FreelanceFlow — pass 3: fixing what the build actually got wrong

Written after running the generated app at 1280px and clicking through every
page. Unlike passes 1 and 2, every item below is a defect I observed, not a
precaution. Paste below the rule into the same AI Studio chat.

---

I ran the app. The architecture is right and most of the styling is right, so
do not restyle anything globally. What follows are specific, observed defects.
Fix all of them. Every item names the file and the symptom — work through them
in order and output the changed files.

## A. Outright bugs — fix these first

**A1. Three CSS custom properties are used but never defined.**
`--bad-line`, `--ok-line` and `--warn-line` appear in `StatTile.tsx` (line 31)
and `RemindersPage.tsx` (lines 123, 149, 225, 251), but `index.css` defines no
such variables. `border-color: var(--bad-line)` with no fallback resolves to
`currentColor`, so the "Overdue in period" tile on `/reports` is currently
drawing a dark navy border while its three neighbours draw a light grey one —
visibly wrong, and clearly unintended.

Define all three in `:root`, tinted to sit alongside the existing pastel badge
grounds, and audit for any other undefined variable while you are there:

```css
--ok-line:   #a3e6b0;
--warn-line: #f2d894;
--bad-line:  #f7c4bb;
```

**A2. `package.json` declares `lucide-react` and `motion` (Framer Motion).**
The brief prohibited both — icons are hand-drawn (and `Icons.tsx` correctly
draws them, so lucide is dead weight), and no page transitions or animation
library is wanted. Remove both dependencies and any import of them.

**A3. The print stylesheet hides too much.** `index.css` under `@media print`
hides every `header` and every `button` globally. On the invoice detail page
that removes the page header, so a printed invoice loses its own invoice number
and client name — the two things a printed invoice most needs. Scope it: hide
`aside`, `[role="dialog"]`, `.print\:hidden` and only buttons inside an actions
container. Keep the page header.

**A4. `::selection` sets `color: var(--ink)`.** The brief specified
`--accent-ink`. Trivial, but it is the difference between selected text looking
deliberate and looking default.

## B. The invoice table is broken — this is the most visible problem

Open `/invoices` at 1280px and look at rows FF-0004, FF-0005, FF-0006 and
FF-0008. Four separate failures compound there:

**B1. Due dates wrap to three lines.** "4 Aug 2026" is rendering as "4" /
"Aug" / "2026" stacked, because the overdue badge shares the Due cell and
starves it of width. Rows FF-0004/5/6 are ~45px tall while FF-0001/2/3 are
~33px. The table is visibly ragged.

**B2. The overdue badge is clipped mid-word.** It reads "37d overdu",
"23d overdu", "14d overdu" — the Record payment button is overlapping it. Text
is being cut off inside a financial table. That alone makes the product look
unfinished.

**B3. The Actions column does not align.** FF-0008 and FF-0010 have
`pdf_available: false`, so their rows show only "Record payment" — and because
the cell is right-aligned with no fixed structure, that button lands in a
different horizontal position from every other row's. The buttons zig-zag down
the page.

**B4. Column widths are inverted.** "Client & Project" is roughly 280px wide
with a large trailing gap, while Due is starved into wrapping. Yet FF-0002's
project still truncates — "Q3 retainer: brand identity refresh, packaging
guideli…" — with unused space to its right.

**Fix all four with an explicit column model.** Use `table-layout: fixed` with
a `<colgroup>`:

```
Invoice    104px   fixed, monospace, never shrinks
Client     auto    takes the remainder
Amount     140px   right-aligned, tabular
Status     128px   fixed
Due        150px   fixed, white-space: nowrap  ← must never wrap
Actions    180px   fixed
```

Then:

- **Move the overdue badge out of the Due cell** and into the Status cell,
  beneath the status badge on its own line. Status becomes a stacked cell:
  "Unpaid" on line one, "37d overdue" on line two. The Due cell then holds only
  a date and gets `white-space: nowrap`, which ends B1 permanently.
- **Give the Actions cell a fixed two-slot grid**, `grid-template-columns: 1fr
  auto`, so the Record payment slot and the PDF slot always occupy the same x
  positions. When there is no PDF, the slot stays empty rather than collapsing.
  That ends B3.
- **Set every row to a fixed 52px height** and let the two-line client cell sit
  inside it. Uniform row height is most of what makes a financial table read as
  professional.
- **Let the project line use the width it has**: `text-overflow: ellipsis` on a
  single line, but only after the column has actually run out — the current
  truncation is firing early because of a hard `max-width` somewhere. Remove it.

## C. Every page is top-heavy with a dead lower half

On `/`, `/invoices` and `/agent`, content stops around 40% of the viewport
height and the remaining 60% is empty canvas. On `/` specifically, the "Needs
attention" panel is stretched to match "Recent activity"'s height, leaving a
large blank area below its four rows — the grid is stretching children instead
of letting them size to content.

- Add `items-start` to the two-column Overview grid so panels size to their
  own content instead of matching the taller sibling.
- The page is short because it is thin, not because it is finished. Add a
  fourth section to the Overview: a **"This month"** strip below the two panels
  — invoiced, received, and the collection rate as a plain sentence
  ("₹62,000.00 collected against ₹1,47,250.00 invoiced — 42%"), with a 4px
  horizontal bar. It fills the space with information rather than padding.
- On `/invoices`, once rows are 52px the table will occupy more height. If it
  still bottoms out early, that is correct — a table that ends is fine. Do not
  add filler. **The dead space is only a problem where the layout caused it.**

## D. The Agent page — the one screen that has to be convincing

**D1. The composer is floating in the middle of the page.** It sits at roughly
55% viewport height with empty canvas above and below it. It must be pinned to
the bottom of the content column: make the page a flex column at
`height: 100dvh`, the transcript `flex: 1; overflow-y: auto`, and the composer
a fixed-height sibling with a 1px top border. Right now it reads as a broken
layout, which undermines the whole demo.

**D2. The tool trace is collapsed by default and therefore invisible.** All the
user sees is "4 operations · 1.9s [hide]". That trace is the single most
important thing on the page — it is the proof this is an agent and not a
chatbot. **Expand it by default.** Collapse is a user action, not an initial
state.

**D3. The proportional duration bars are missing.** Pass 2 asked for a 6px
`--accent-wash` bar behind each trace row, width scaled to that call's share of
the turn. It is not there. Add it. Seeing `record_payment` visually consume
most of the turn is what makes the trace read as real telemetry rather than as
four decorative ticks.

**D4. The failed-call exchange is missing.** The seeded transcript has exactly
one successful turn. Add the second exchange specified in pass 2: user types
"mark FF-0004 as paid", the trace shows `find_client` succeeding then
`record_payment` failing in `--bad-ink` with the error printed verbatim
("Invoice FF-0004 has ₹28,500.00 outstanding; no amount was given"), and the
agent's reply asks for the amount rather than claiming success. A demo that
only ever succeeds looks staged.

**D5. The composer's helper row is clumsy.** "Enter to send · Shift+Enter for
newline" currently occupies its own full-width row inside the input box. Move
it to 11.5px `--ink-faint` text sitting left of the Send button on the same
line as the button, outside the textarea.

## E. Copy that gives the machine away

**E1. `/reports` chart subtitle currently reads "Six-month comparison (April
2026 – September 2026). Hand-rolled SVG paired bars."** The app is describing
its own implementation to the freelancer. Delete the second sentence entirely.
Nowhere in the interface should implementation detail appear as user-facing
copy — audit every subtitle for this.

**E2. Generic three-verb subtitles.** `/invoices` reads "Manage billing
schedules, track payments, and issue invoices." That is filler, it restates the
nav label, and pass 2 explicitly said Invoices needs no subtitle because the
table is self-evident. Remove it. `/reports` reads "Financial performance,
collections velocity, and revenue reconciliation" — "collections velocity" is
invented jargon. Replace with "Invoiced against received, by month and by
client."

**E3. Tile notes that say nothing.** "Settled to bank accounts" under Received
and "Past contractual terms" under Overdue are padding. Replace with real
figures: "across 4 payments" and "oldest 37 days, Priya Deshmukh".

**E4. Timestamps regress past 48 hours.** The activity feed shows "1 month
ago" and "3 months ago". Pass 2 asked for specific dates beyond two days. Use
"Today", "Yesterday at 4:12 pm", then "6 September" and "14 May 2026".

## F. A data-integrity error on /reports

The "Issued invoices distribution" section shows four boxes: Paid 3,
Partially paid 2, Unpaid 6, Overdue 4 — totalling 15, against 12 invoices. It
is presenting a partition that is not one: **overdue is a cross-cutting
attribute of unpaid invoices, not a status alongside them**, and Cancelled is
missing entirely.

In a billing product, numbers that do not add up are the worst possible defect,
because the user cannot tell a display bug from a ledger bug. Fix it:

- Show the true partition — Paid 3 · Partially paid 2 · Unpaid 6 · Cancelled 1
  = 12 — and make the total explicit: "12 invoices issued".
- Show overdue as a separate qualifying line beneath it: "4 of these are
  overdue", with the count in `--bad-ink`.

Also check the "Invoiced in period" tile, which reads 11 while the table lists
12 rows. If cancelled invoices are deliberately excluded, say so in the note
("excludes 1 cancelled"). An unexplained discrepancy between two numbers on the
same screen is exactly what destroys trust in a financial tool.

## G. Chart scaling

The bars top out at roughly 55% of the plot height because the y-domain is set
from an unrounded maximum, and the axis labels read ₹0 / ₹75,450 / ₹1,50,900.

- Round the domain up to a clean interval: max → ₹1,50,000 with gridlines at
  ₹50,000 / ₹1,00,000 / ₹1,50,000.
- Set the domain so the tallest bar fills about 90% of the plot height.
- April and August currently render as 1–2px slivers. Give every non-zero bar a
  3px minimum height so it is visible as a value rather than a rendering
  artifact, and label a true zero month as "—" on the axis instead.

---

Output the complete revised files for every change above. Do not summarise the
changes. If the response would truncate, do sections A–C and stop at a file
boundary; I will tell you to continue with D–G.
