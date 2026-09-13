# Prompt 3 of 4 — copy that reveals the machine, and numbers that don't add up

Paste after prompt 2 has finished. Same chat.

---

## 1. The app is describing its own implementation to the user

The chart on `/reports` is subtitled:

> "Six-month comparison (April 2026 – September 2026). Hand-rolled SVG paired
> bars."

The second sentence is build-spec language that leaked into the interface. A
freelancer does not care how the chart is drawn. Delete it.

Then audit every subtitle, label, tooltip and empty state in `src/` for the
same class of leak — any text describing how something is implemented, any text
that reads like it was written for a developer rather than for the person
using the product. Report what you find and remove it.

## 2. Generic subtitles

- `/invoices` reads "Manage billing schedules, track payments, and issue
  invoices." That is a three-verb filler sentence that restates the nav label
  and tells the user nothing. **Delete it entirely** — the table is
  self-evident and needs no introduction.
- `/reports` reads "Financial performance, collections velocity, and revenue
  reconciliation." "Collections velocity" is invented jargon. Replace with:
  "Invoiced against received, by month and by client."

A subtitle on every page is a template. A subtitle where it earns its place is
an interface. Keep the one on `/overdue` — it explains a derivation the user
would otherwise doubt. Drop the ones that are decoration.

## 3. Tile notes that say nothing

On `/reports`, "Settled to bank accounts" under Received and "Past contractual
terms" under Overdue are padding. Replace them with figures that add
information the tile does not already carry:

- Received → "across 4 payments"
- Overdue → "oldest 37 days · Priya Deshmukh"
- Outstanding → "across 8 open invoices"
- Invoiced → "excludes 1 cancelled"

## 4. Timestamps regress past 48 hours

The activity feed on `/` shows "1 month ago" and "3 months ago". Relative time
stops being useful after about two days and starts sounding vague.

Use: "Today" · "Yesterday at 4:12 pm" · then a date — "6 September" within the
current year, "14 May 2026" outside it.

## 5. A data-integrity error on /reports

"Issued invoices distribution" shows four boxes — Paid 3, Partially paid 2,
Unpaid 6, Overdue 4 — totalling **15**, against **12** invoices.

It is presenting a partition that is not one. **Overdue is a cross-cutting
attribute of unpaid invoices, not a status alongside them**, and Cancelled is
missing entirely.

In a billing product this is the worst class of defect, because the user cannot
tell a display bug from a ledger bug. Fix it:

- Show the true partition: **Paid 3 · Partially paid 2 · Unpaid 6 ·
  Cancelled 1 = 12**, with the total stated explicitly: "12 invoices issued".
- Show overdue as a separate qualifying line beneath it: "4 of these are
  overdue", count in `--bad-ink`.

Also: the "Invoiced in period" tile reads **11** while the table lists **12**
rows. If cancelled invoices are deliberately excluded, say so in the tile note
("excludes 1 cancelled"). Two numbers on the same screen that disagree with no
explanation is exactly what destroys trust in a financial tool.

Then check every other derived count in the app for the same problem.

## 6. Chart scaling

The bars top out at roughly 55% of the plot height, and the y-axis labels read
₹0 / ₹75,450 / ₹1,50,900 — raw maxima rather than round numbers.

- Round the domain up to a clean interval: max ₹1,50,000, gridlines at
  ₹50,000 / ₹1,00,000 / ₹1,50,000.
- Scale so the tallest bar fills about 90% of the plot height.
- April and August currently render as 1–2px slivers that look like rendering
  artifacts. Give every non-zero bar a 3px minimum height, and render a true
  zero as no bar with the month label in `--ink-faint`.
