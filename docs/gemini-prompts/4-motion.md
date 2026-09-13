# Prompt 4 of 4 — the motion system

Paste last, after prompts 1–3 have landed. Motion applied to a broken layout
just makes the breakage move.

---

Earlier I told you nothing should move. I am revising that: the app should feel
smooth. But I am specifying the motion precisely, because undisciplined
animation is what makes an interface feel generated — bouncy springs on
everything, staggered reveals on every list, numbers ticking up. None of that.

The governing idea: **motion explains state changes; it never decorates.** If an
animation does not help the user understand what just happened or where
something came from, it should not exist. This is a financial tool — it should
feel quick and precise, like the Stripe dashboard, not soft and playful.

No animation library. Everything below is CSS. Do not reinstall `motion`.

## 1. Tokens

Add to `:root` in `src/index.css`:

```css
/* Durations — short. Anything over 320ms feels sluggish in a dense tool. */
--dur-instant: 80ms;
--dur-fast:    140ms;
--dur-base:    200ms;
--dur-slow:    300ms;

/* Easings */
--ease-out:    cubic-bezier(0.16, 1, 0.30, 1);   /* entrances — fast start, soft landing */
--ease-in:     cubic-bezier(0.55, 0, 1, 0.45);   /* exits */
--ease-move:   cubic-bezier(0.65, 0, 0.35, 1);   /* something moving between two places */
```

**There is deliberately no spring or overshoot easing.** Overshoot on a
financial figure reads as unserious. If you feel one is needed, do not add it.

## 2. Hard rules

1. **Animate only `transform` and `opacity`.** Never `width`, `height`, `top`,
   `left`, `margin` or `padding` — they trigger layout on every frame. The one
   sanctioned exception is `grid-template-rows: 0fr → 1fr` for accordions,
   which is the modern way to animate to auto height.
2. **Exits are faster than entrances**, always. Enter at `--dur-base`, exit at
   `--dur-fast`. Real interfaces get out of the way quickly.
3. **Movement distance is small** — 4px to 8px. Large travel reads as a slide
   show. Never animate an element across more than 10% of the viewport.
4. **Animate on mount and on user action only. Never on data refresh.** If a
   poll or a refetch re-renders a table, the rows must not re-animate. Gate
   entrance animations behind a `hasAnimated` ref so they run exactly once.
5. **Stagger is capped.** 24ms per item, maximum 10 items, so no sequence runs
   longer than 240ms. Never stagger a list the user has already seen.
6. **No count-up number animations.** A balance that ticks from ₹0 to
   ₹2,40,150.00 is unreadable mid-flight and, in a billing tool, actively
   misleading. Money appears at its value.
7. **No shimmer on skeletons.** A 1.6s opacity breathe between 1 and 0.6 is
   enough.
8. **No page-level slide transitions**, no parallax, no scroll-triggered
   reveals, no `filter: blur()` transitions.

## 3. What gets motion

### Route change
The main content area, on mount: `opacity 0 → 1` and `translateY(6px) → 0`,
`--dur-base`, `--ease-out`. The sidebar never animates — it is persistent
furniture, and animating it makes the app feel like it is reloading.

Where supported, use the View Transitions API for this as a progressive
enhancement, falling back to the CSS above.

### Sidebar active indicator
Currently the active state is a background swap. Replace it with a single
absolutely-positioned 2px-wide bar in `--accent` on the left edge of the nav,
which **slides between items** using `transform: translateY()` at `--dur-base`
/ `--ease-move`. One element that moves, not eight that fade. This is the
detail that most makes a nav feel built rather than generated.

The `--accent-wash` background still cross-fades at `--dur-fast`.

### Table rows, first load only
Staggered `opacity 0 → 1` + `translateY(4px) → 0`, 24ms apart, capped at 10
rows; rows beyond the tenth appear with no delay. Never replays on filter
change or refetch — filtering is instant.

### Row hover
Background at `--dur-fast`. The Actions buttons go `opacity 0 → 1` at
`--dur-fast`. Both must be instant enough that a fast mouse never sees a
half-faded button.

### Buttons
`:active { transform: scale(0.98); }` at `--dur-instant`. Nothing on hover but
the existing background transition.

### Modals
- Backdrop: `opacity 0 → 1`, `--dur-fast`.
- Panel: `opacity 0 → 1` and `scale(0.97) → 1` plus `translateY(8px) → 0`,
  `--dur-base`, `--ease-out`.
- Exit: both at `--dur-fast` with `--ease-in`. Do not reverse the scale on
  exit — fade and a 4px drop is enough.

### Toasts
Enter: `translateY(12px) → 0` + fade, `--dur-base`. Exit: fade + `translateY(6px)`,
`--dur-fast`. When several stack, the ones below shift up with a `--dur-base`
transform transition rather than jumping.

### The tool trace — the one place motion earns real value
1. **Rows appear as the agent runs them**, one at a time, `opacity 0 → 1` +
   `translateY(4px) → 0` at `--dur-fast`. This is a genuine progress display,
   not decoration.
2. **The in-flight row's dot pulses**: `opacity` 1 → 0.35 → 1 over 1.4s,
   infinite, `ease-in-out`. One dot only.
3. **The duration bars grow from the left**: `transform: scaleX(0) → scaleX(1)`
   with `transform-origin: left`, `--dur-slow`, `--ease-out`, staggered 40ms.
   Runs once when the turn completes.
4. **The collapse toggle uses `grid-template-rows: 0fr → 1fr`** plus an opacity
   fade at `--dur-base`, so it animates to true auto height with no measured
   pixel values and no `max-height` guess.

### Payment progress bar
On mount: `transform: scaleX(0) → scaleX(target)`, `transform-origin: left`,
`--dur-slow`, `--ease-out`. Once per mount.

### Chart bars on /reports
Grow from the baseline: `transform: scaleY(0) → scaleY(1)`,
`transform-origin: bottom`, `--dur-slow`, `--ease-out`, staggered 40ms per
month. Fire once, via an `IntersectionObserver` that disconnects after the
first trigger — not on every scroll past.

### Optimistic write feedback
When a payment is recorded, the affected row flashes: a keyframe from
`--accent-wash` to `transparent` over 600ms, `ease-out`, once. No pulse, no
repeat, no border change.

## 4. Reduced motion

The existing `@media (prefers-reduced-motion: reduce)` block clamps everything
to 0.01ms, which is right for movement but wrong for opacity — instant appears
and disappears are jarring in a different way.

Rewrite it so that transforms and looping animations are disabled entirely,
while opacity transitions are kept and shortened to `--dur-instant`:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: var(--dur-instant) !important;
    transition-property: opacity, background-color, color, border-color !important;
    scroll-behavior: auto !important;
  }
}
```

The pulsing dot and the bar growth must not run at all under this setting.

## 5. Performance

- Apply `will-change: transform` **only** to the sidebar indicator and the
  trace duration bars, and remove it once the animation completes. Leaving
  `will-change` on dozens of table rows costs more than it saves.
- Add `contain: layout paint` to panel containers.
- The chart's `IntersectionObserver` must disconnect after firing once.

## 6. When you are done

State plainly which elements you animated and which you deliberately left
static, and confirm that no `width`, `height`, `top`, `left`, `margin` or
`padding` property is animated anywhere in the codebase. Output the complete
changed files.
