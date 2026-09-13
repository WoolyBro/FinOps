# FreelanceFlow — pass 2: the de-AI-ification prompt

Paste below the rule into the **same AI Studio chat** that built the app, so it
still has the code in context. Do not start a new chat.

---

The build is structurally correct. It still reads as machine-generated. I am
going to tell you exactly why, and you are going to fix it. Do not restyle
anything — the palette, the type scale and the layout are right. What is wrong
is uniformity, synthetic data, missing micro-states, and decoration standing in
for information. Work through all six sections and output the revised files.

## 1. Kill the uniformity

The single biggest tell is that everything is equally important. Real interfaces
have a loudest element per screen and a lot of quiet around it. Right now every
panel has the same padding, every gap is the same, every heading is the same
size, and every card floats at the same elevation. That flatness is what reads
as "generated".

**Do this:**

- **Vary elevation by role.** Only the primary panel on a page carries
  `--shadow-sm`. Secondary panels drop to `box-shadow: none` and rely on their
  `1px solid var(--line)` alone. Modals keep `--shadow-lg`. Right now everything
  is lifted, so nothing is.
- **Vary density by role.** The Overview's "Needs attention" panel is the
  loudest thing on the page: give its rows 52px height and 18px horizontal
  padding. "Recent activity" is ambient: 36px rows, 13px text, `--ink-body`.
  They must not look like siblings.
- **Break the metric row's symmetry.** Four identical tiles in a perfect grid is
  a generated-dashboard signature. Make the **Outstanding** tile span two
  columns on the Overview, with its value at 32px and a one-line
  `--ink-faint` breakdown beneath ("₹2,85,500.00 across 7 invoices · oldest 37
  days"). The other three stay at 25px in single columns. Hierarchy, not
  a grid of equals.
- **Stop centring things.** Empty states may be centred. Nothing else. Page
  headers, panel headers, card content, tile content — all left-aligned, all
  sharing one left edge down the page.
- **Tighten the top.** There is too much air above the page title. 24px from the
  top of the content area to the title cap-height, not 40px+.
- **Column widths must not be equal.** Set explicit widths: the invoice-number
  column is `104px` and shrink-proof, Status is `128px`, Actions is sized to its
  content, and the Client column takes the remainder. Equal-width columns are
  what a generator produces; deliberate ones are what a designer produces.

## 2. Make the data look like it came from a real business

Right now the data is too clean, and clean data is a tell. Every client has a
full email and phone, every amount is round, every invoice has a PDF, dates are
evenly spaced. Real ledgers are lumpy.

**Change the mock dataset to include:**

- **Missing fields, rendered honestly.** Arjun Nair has no phone. Vikram Rao has
  no email *and* no phone — his client card must show a `--ink-faint` line
  reading "No contact details" rather than an empty gap or a dash. Two invoices
  have `description: null`; their detail pages omit the row entirely rather than
  showing "Description: —".
- **Amounts that are not all round.** ₹28,500.00 and ₹1,25,000.00 are fine, but
  add ₹47,250.00 and ₹9,800.00. Add one invoice at ₹2,40,000.00 so the Indian
  grouping is visibly exercised at a wide value, and one at ₹1,25,50,000.00
  somewhere in the client history so a 25px tile has to cope with a long string
  without wrapping badly.
- **A partial payment that is awkward.** FF-0005 is ₹40,000.00 with ₹15,000.00
  paid — good. Add FF-0011 at ₹47,250.00 with ₹47,000.00 paid, leaving ₹250.00
  outstanding. A 99.5% progress bar and a trivial remainder is exactly the case
  a generated demo never contains, and it is the case that proves the maths is
  real.
- **A cancelled invoice.** FF-0012, cancelled, ₹18,000.00. It must appear in the
  client's history with a struck-through amount and a neutral badge, and must be
  excluded from every total. Show it excluded — the client detail page's invoice
  count says "8 invoices · 1 cancelled".
- **Names and projects of realistic, uneven length.** Keep "Sana Qureshi" but add
  "Krishnamurthy Venkataraghavan" with the project "Multi-tenant billing portal
  — phase 2 (discovery + IA)". This name and this project must not break the
  table. That is the point of including them.
- **Irregular dates.** Invoices clustered in bursts — three in one week, then
  nothing for eighteen days. Freelancers do not invoice on a metronome.
- **`pdf_available: false` on two invoices.** Their rows show no PDF link, and
  the detail page's Download button is absent, not disabled.
- **One payment with `method: null` and `reference: null`.** Its row shows
  "Not recorded" in `--ink-faint`, not an em dash in a bold cell.

Remove any auto-generated **coloured circle avatars with initials**. Those are
the single most recognisable generated-UI artifact in existence. Clients are
identified by name in text. If a card needs a visual anchor, use a 3px left
border in `--line-strong` that turns `--bad-ink` when the client has anything
overdue — information, not decoration.

## 3. Add the micro-states that only real software has

A generated UI renders one state per screen: populated and idle. Add the rest.

- **Row hover** on every table row: `background: var(--surface-sunken)`, 120ms.
  The Actions cell's buttons are `opacity: 0` until the row is hovered or
  focused within, then fade in. On touch viewports they are always visible.
- **`:focus-visible`** on every interactive element: `2px solid var(--accent)`,
  `2px` offset. Tab through the whole app and make sure nothing is invisible
  when focused. Never `outline: none` without a replacement.
- **Sticky table headers** inside the scroll container, with the header row
  keeping its `--surface-sunken` background and gaining a `1px` bottom border
  that only appears once scrolled.
- **Optimistic-then-settled writes.** When a payment is recorded, the affected
  invoice row updates immediately and briefly flashes `--accent-wash` for
  600ms before settling. If the request then fails, it reverts and the toast
  carries the server's message.
- **Busy states in-place.** A button that is working reads "Recording…" in its
  own label. No overlay, no spinner, no skeleton replacing content that is
  already on screen.
- **Real skeletons** for first loads: grey `--line` blocks at the exact height
  of the rows they replace, so the layout does not jump when data arrives. Three
  rows, not ten. No shimmer animation.
- **Text selection colour**: `::selection { background: var(--accent-wash);
  color: var(--accent-ink); }`.
- **Scrollbars** in the sidebar and table containers: 10px, transparent track,
  `--line-strong` thumb at 6px radius, `--ink-faint` on hover. Firefox
  `scrollbar-width: thin` + `scrollbar-color`.
- **Truncation with intent.** Long client names truncate with `text-overflow:
  ellipsis` and carry a `title` attribute. Long project names wrap to a second
  line and clamp at two with `-webkit-line-clamp`. Never let either widen a
  column.
- **A `print` stylesheet** for the invoice detail page: hide the sidebar and all
  actions, black ink on white, borders only. Nobody asks for this, which is
  precisely why having it reads as real software.

## 4. Fix the icons and the typographic craft

- **Redraw every icon on a 16×16 grid with a 1.5 stroke and consistent optical
  weight.** Right now they vary — some are dense and dark, some are thin. Every
  icon must have the same number of strokes' worth of visual mass. Align them to
  the half-pixel grid so they render crisply: shapes at `x.25` / `x.75`
  coordinates with a 1.5 stroke land on whole pixels.
- **Apply `font-variant-numeric: tabular-nums` everywhere a number appears** —
  tiles, table cells, the progress label, the chart axis, durations in the tool
  trace. Verify it is actually inherited; it commonly is not.
- **Negative tracking scales with size.** 24px title at `-0.021em`, 25px metric
  at `-0.028em`, 32px metric at `-0.032em`, 14px body at `0`. Uniform tracking
  across sizes is a generated-CSS tell.
- **The rupee sign and the digits must share a baseline.** If the font renders
  ₹ visibly higher or lighter than the digits, wrap it in a span with
  `font-feature-settings` disabled or a 0.94em size — check it at 32px where it
  is obvious.
- **One weight jump per hierarchy level**, no more: 400 body → 550 labels → 600
  headings → 660 page titles. Nothing bold-800.
- **Hairlines must be 1px at every DPR.** Use `1px solid` with the border-box
  model, not `0.5px` and not a `box-shadow` inset trick.

## 5. Rewrite the copy so a human wrote it

Generated copy is uniform in length and hedges. Every subtitle is one line;
every empty state is two sentences; every label is a noun. Break that.

- **Subtitles vary in length by page.** Overdue's explains the derivation in
  three lines because it needs to. Payments' is six words: "Every payment
  recorded, newest first." Invoices' has none at all — the table is
  self-evident. A subtitle on every page is a template; a subtitle where it
  earns its place is an interface.
- **Numbers get context, not adjectives.** Not "Great job!" under Received —
  instead "₹3,02,000.00 · up from ₹1,84,000.00 last month" in `--ink-faint`,
  or nothing.
- **Write one genuinely specific empty state.** The Reminders empty state should
  read: "**No reminders drafted** — Two invoices are overdue. You can draft a
  reminder from either." with a link to `/overdue`. It knows something. That is
  the difference.
- **The reminder message bodies must be written, not templated.** Three
  sentences, naming the invoice, the amount and the elapsed time, in the voice
  of a freelancer who wants to be paid without souring the relationship. No
  "Dear Sir/Madam". No "I hope this email finds you well". Something a person
  would actually send.
- **Timestamps are specific.** "Yesterday at 4:12 pm" and "6 September" beat
  "1 day ago" and "4 days ago" once you are past 48 hours.

## 6. The agent page specifically

This is the screen that has to be convincing, and it is the one most likely to
still look like a chatbot demo.

- **The tool trace is not a list of green ticks.** Give each row a fixed-width
  duration column so the timings form a visual column, and render the durations
  proportionally: a 6px-tall bar behind each row, `--accent-wash`, width scaled
  to that call's share of the total. The user should see at a glance that
  `record_payment` took most of the turn. That single detail does more to prove
  the thing is real than any amount of styling.
- **Include one failed call in the seeded transcript.** A second exchange where
  the user writes "mark FF-0004 as paid" and the agent calls `find_client`,
  then `record_payment`, which returns an error: "Invoice FF-0004 has
  ₹28,500.00 outstanding; no amount was given." The trace row is `--bad-ink`
  with a drawn cross, the error prints verbatim beneath it, and the agent's
  reply asks for the amount instead of pretending it worked. **Software that
  shows its failures reads as real; software that only shows successes reads as
  a mockup.**
- **The reply text is not markdown-formatted.** No bullet lists, no bold
  scattered through the sentence, no headings. Two or three plain sentences with
  the amounts in them. If the agent lists invoices, it renders them as a result
  card, not as `- FF-0004: ₹28,500`.
- **Remove any typing indicator with three bouncing dots.** While a turn runs,
  the trace panel is already building — that *is* the progress indicator. Show
  the in-flight tool row with a single 6px dot pulsing at 1.4s, nothing else.
- **The composer sits on the canvas, not in a floating rounded bar.** A 1px top
  border above it, `--surface` background, and the input is a plain bordered
  textarea. No shadow, no pill, no gradient send button, no paperclip or
  microphone icons for features that do not exist.

---

Output the complete revised files. Do not describe the changes — make them. If
you cannot fit everything in one response, do sections 1–3 first and stop at a
file boundary, and I will tell you to continue.
