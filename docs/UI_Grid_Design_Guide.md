# STL Manager UI: Grid-First Design Guide

This guide distills the approach for designing a dense, low-empty-space UI where spatial relationships stay locked. It outlines a baseline-driven grid, how to integrate your 9-slice frames, and how to avoid wrap/overlap issues.

## Why adopt a grid-first approach
- Predictable alignment: explicit rows/columns keep elements in place regardless of content.
- Consistent density: zero-gutter layouts with touching frames are straightforward.
- Fewer hacks: fixed rows + overflow policies prevent accidental wrapping and overlap.
- Easy QA: a debug overlay makes misalignments obvious.

## Design goals
- Frames touch with no visible gaps; seams are hidden.
- Three fixed-height rows to the right of the meta panel:
  1) Domains | Search | Theme (right-side controls)
  2) Domain-specific buttons
  3) Pins (reserved)
- Inner content never changes row height; overflow is clipped or scrolled by design.
- All spacing and sizes snap to a consistent baseline unit.

## Baseline tokens (choose a base unit)
Pick a unit that matches your density and 9-slice art (examples: `--u: 4px` or `6px`). Then define everything as multiples of `--u`.

- Frame thickness (panels): `--frame-border = n * --u` (e.g., 18px → 4.5u; ideally land on whole multiples or scale art)
- Button frame thickness: `--btn-frame-border = 3u` (e.g., 12px)
- Topbar row height: `--bar-row-h = 10–12u` (e.g., 40–48px)
- Paddings/offsets: only multiples of `--u`

Benefits: No fractional pixels; borders and paddings align; fewer hairlines.

## Layout grid (macro)
- Top region uses CSS Grid: two columns → meta frame (fixed width) + control area (1fr).
- Control area: 3 explicit rows with zero gap so frames visually touch.
  - Row 1 columns: `1fr auto auto` (Domains | Search | Theme)
  - Row 2 columns: `1fr` (Domain-specific bar)
  - Row 3 columns: `1fr` (Pins)
- All rows share a fixed height `--bar-row-h` and use `align-items: stretch`.

Notes:
- Keep grid gaps at 0; rely on frame borders for separation.
- If a hairline seam appears, either overlap adjacent items by `-1px` or slightly increase `border-image-width` (e.g., `1.02`).

## Component grid (micro)
- Buttons (`.btn9`):
  - `height: 100%`, reduced vertical padding (`0–4px`) so labels never increase row height.
  - `white-space: nowrap; overflow: hidden; text-overflow: ellipsis` to avoid wrapping.
  - Use a slimmer `--btn-frame-border` than panel frames for a refined look.
- Search and Theme controls (framed):
  - Fill the row (`height: 100%`) and clip inner content (`.frame { overflow: hidden; }`).
  - Search input uses `box-sizing: border-box` and small vertical padding.

## 9-slice frame integration
- Align the source slice size (e.g., 28px) to the baseline (with `--u = 4px`, 28px = 7u).
- Seam strategies when frames touch:
  - Strategy A: negative margin on adjacent items (e.g., `margin-left: -1px`).
  - Strategy B: slightly increase `border-image-width` (e.g., `--biw: 1.02`).
- Keep `background-clip: border-box` and set `overflow: hidden` on frames so contents clip, not the border.

## Overflow policy (no cross-row wrapping)
- Domain bars: disable wrap (`flex-wrap: nowrap`) and select a policy:
  - Clip: `overflow: hidden` (strict)
  - Scroll: `overflow-x: auto` (user can scroll)
- Domain-specific bar: same policy as above.
- Pins row: fixed height; clip or scroll as needed.

## Responsiveness without breaking alignment
- Prefer reveal/hide and overflow management to line-wrapping.
- Use container queries or width thresholds to:
  - Collapse long domain lists into a “More” overflow.
  - Swap full search for an icon at narrow widths.
  - Keep the 3-row structure intact at all breakpoints.

## Debug overlay (dev-only)
Add a temporary overlay to verify grid alignment:

```css
.debug-grid::before {
  content: "";
  position: fixed; inset: 0; pointer-events: none; z-index: 9999;
  background-image:
    linear-gradient(transparent calc(var(--u) - 1px), rgba(255,255,255,0.06) 1px),
    linear-gradient(90deg, transparent calc(var(--u) - 1px), rgba(255,255,255,0.06) 1px);
  background-size: var(--u) var(--u), var(--u) var(--u);
}
```

Toggle `.debug-grid` on `<body>` while designing.

## Example token block (reference only)

```css
:root {
  --u: 4px;
  --frame-border: 18px;        /* panel frames (ornate) */
  --btn-frame-border: 12px;     /* button frames */
  --bar-row-h: calc(11 * var(--u));
  --biw: 1;                     /* border-image-width */
}
```

## Migration checklist
1) Choose `--u` and align `--frame-border`, `--btn-frame-border`, `--bar-row-h` to multiples of `--u`.
2) Convert (or validate) the top control area to Grid with 3 fixed rows, zero gaps.
3) Enforce `height: 100%` + clipping on all row children; prevent wrapping in bars.
4) Standardize a seam strategy (negative margin vs. small `border-image-width` increase) and apply consistently.
5) Add the debug overlay; validate across common widths; remove once verified.

## FAQ
- Why Grid over Flex here?
  Grid gives fixed, explicit rows and columns—which is ideal when spatial relationships must not change. Flex is great for single-axis flows, but it’s easy to get wrapping or alignment drift under pressure.

- Can we keep the ornate 9-slice frames?
  Yes. The key is to snap slice thicknesses and borders to the baseline and use a seam strategy when frames touch.

- How do we handle smaller screens?
  Use overflow or control variants (e.g., search icon) rather than wrapping that breaks row integrity.

---

When you’re ready, we can add a dev-only overlay and a token block to the mock to validate the grid live—no functional changes required.
