# Prompt 1 of 4 — undefined variables, dead dependencies, and the invoice table

Paste everything below the rule. Wait for it to finish before pasting prompt 2.

---

I ran the app at 1280px and went through every page. The architecture and the
palette are right — do not restyle anything globally. What follows are specific
observed defects. Fix all of them and output the complete changed files.

## 1. Three CSS custom properties are used but never defined

`--bad-line`, `--ok-line` and `--warn-line` are referenced in
`src/components/ui/StatTile.tsx` (line 31) and `src/pages/RemindersPage.tsx`
(lines 123, 149, 225, 251). `src/index.css` defines none of them.

`border-color: var(--bad-line)` with no fallback resolves to `currentColor`, so
the "Overdue in period" tile on `/reports` currently draws a dark red-navy
border while its three neighbours draw light grey. It looks like a mistake
because it is one.

Add to `:root` in `index.css`, tinted to sit with the existing pastel badge
grounds:

```css
--ok-line:   #a3e6b0;
--warn-line: #f2d894;
--bad-line:  #f7c4bb;
```

Then grep the whole `src/` tree for `var(--` and confirm every name resolves to
something defined in `:root`. Report any others you find.

## 2. Remove two dependencies that must not be there

`package.json` declares `lucide-react` and `motion`. Neither is wanted:

- `src/components/Icons.tsx` already hand-draws every icon on a 16×16 grid, so
  `lucide-react` is dead weight that is never rendered.
- All motion in this app will be CSS. No animation library.

Remove both from `package.json` and delete any import of either.

## 3. `::selection` uses the wrong token

`index.css` sets `color: var(--ink)`. It should be `var(--accent-ink)`.

## 4. The print stylesheet hides too much

`@media print` in `index.css` currently hides every `header` and every `button`
globally. On `/invoices/:id` that strips the page header, so a printed invoice
loses its own invoice number and client name — the two things a printed invoice
most needs.

Scope it: hide `aside`, `[role="dialog"]`, `.print\:hidden`, and buttons only
when they sit inside an actions container. The page header must survive.

## 5. The invoice table is visibly broken

Open `/invoices` at 1280px and look at rows FF-0004, FF-0005, FF-0006 and
FF-0008. Four failures compound:

- **Due dates wrap to three lines.** "4 Aug 2026" renders as "4" / "Aug" /
  "2026" stacked, because the overdue badge shares the Due cell and starves it
  of width. Those rows are ~45px tall while FF-0001/2/3 are ~33px, so the table
  is ragged.
- **The overdue badge is clipped mid-word.** It literally reads "37d overdu",
  "23d overdu", "14d overdu" — the Record payment button is overlapping it.
- **The Actions column does not align.** FF-0008 and FF-0010 have
  `pdf_available: false`, so they render only "Record payment", and because the
  cell is right-aligned with no fixed structure that button lands at a
  different x than every other row's. The buttons zig-zag down the page.
- **Column widths are inverted.** "Client & Project" holds ~280px with a large
  trailing gap, while Due is starved into wrapping — yet FF-0002's project
  still truncates early ("Q3 retainer: brand identity refresh, packaging
  guideli…") with unused space to its right. Something is applying a hard
  `max-width`; remove it.

### Fix it with an explicit column model

Give the table `table-layout: fixed` and a `<colgroup>`:

| Column | Width | Notes |
|---|---|---|
| Invoice | `104px` | fixed, monospace, never shrinks |
| Client & project | `auto` | takes the remainder |
| Amount | `140px` | right-aligned, tabular |
| Status | `128px` | fixed |
| Due | `150px` | fixed, `white-space: nowrap` |
| Actions | `180px` | fixed |

Then make these four structural changes:

1. **Move the overdue badge out of the Due cell into the Status cell**, on its
   own second line beneath the status badge. Status becomes a stacked cell:
   "Unpaid" above, "37d overdue" below. The Due cell then holds only a date and
   carries `white-space: nowrap`, which ends the wrapping permanently.
2. **Give the Actions cell a fixed two-slot grid**, `grid-template-columns: 1fr
   auto`. The Record payment slot and the PDF slot then always occupy the same
   x positions; when there is no PDF the slot stays empty rather than
   collapsing.
3. **Fix every row at 52px height.** Uniform row height is most of what makes a
   financial table read as professional rather than generated.
4. **Let the project line use the width it actually has.** Single line,
   `text-overflow: ellipsis`, truncating only when the column genuinely runs
   out.

Apply the same column discipline to the tables on `/payments`, `/overdue` and
`/clients/:id` — they share the same failure mode even where it is less
visible today.
