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

## Micro vs. Meso vs. Macro grids (and why examples look “big”)
Most web tutorials show macro column grids (8/12 columns with big gutters), not the micro baseline grid.

- Micro (baseline): 4px or 8px rhythm for spacing, paddings, borders, and text line-height. This is the precision layer we snap to.
- Meso (major step): a larger step built on the baseline (e.g., 20px = 5 × 4px). Use it to compose blocks while keeping micro precision inside.
- Macro (columns): page-wide columns and gutters. Our workbench can keep gutters at 0 and let the frame borders provide separation.

Tip: set the overlay to Unit = 4 and Major = 5 to visualize a 20px meso grid on top of the 4px baseline.

## “Place by coordinates” without a brittle global grid
Use an app-shell grid for the big regions and nested grids/subgrid inside each region. That way you still “pick a coord” (grid-row/column or named areas) but keep components modular and responsive.

- App shell: meta panel + control area.
- Control area: its own 3 fixed rows (Domains | Search | Theme, Domain-specific bar, Pins).
- Inside rows: place items by named lines/areas or numeric lines. Prefer `subgrid` where supported so children inherit the parent’s tracks without duplicating sizes.

This is more resilient than one giant page grid and keeps seams aligned while allowing local changes.

## Outer-edge snap vs. inner-edge optics
If your 9-slice frame art has perspective or uneven inner thickness (for realism):

- Snap the outer edges to the grid. This guarantees clean seams and row alignment.
- Treat the inner edge as an optical spacing problem. Keep consistent tokens for insets; they can be asymmetric to balance the perspective.

Patterns that work well:
- Asymmetric insets (preferred):
  - `--inset-t/r/b/l` tuned per frame style, still multiples of `--u` where possible. Content padding uses these insets.
- Optional “inner liner”: a subtle pseudo-element that defines a uniform inner rectangle (e.g., a faint inset 1px) to visually regularize the inner boundary without changing the frame art.
- Avoid stretching the border art to “fix” the inside; if you must, tiny per-side `border-image-width` nudges only (1–2px visual effect) and test across DPRs.

## Seam strategy (touching frames)
Pick one global approach and apply it everywhere:

- Overlap: adjacent items `margin-left: -1px` (simple, robust).
- Nudge: slightly increase `border-image-width` (e.g., `1.01–1.03`) so edges kiss without gaps.

Keep grid gaps at 0; let frames provide separation.

## Scaling across resolutions (tokens, not transforms)
Scale layout with design tokens and supply sharper art; don’t zoom the UI.

- Baseline/token scaling: define `--u` once and let row heights/paddings derive from it. Optionally increase `--u` at wider widths; avoid `transform: scale()` or `zoom` (they blur text and fatten 1px strokes).
- High‑DPR art: keep CSS `border-width` fixed (e.g., 20px) and serve 1x/2x sources with `image-set()` so the frame stays crisp without changing thickness.
- Subgrid helps children inherit scaled tracks when `--u` changes.

Example snippets (conceptual):

```css
:root { --u: 4px; --bar-row-h: calc(12 * var(--u)); }
@container (min-width: 1200px) { :root { --u: 5px; } } /* optional size tier */
.frame {
  border-width: 20px;
  border-image-slice: 20;
  border-image-repeat: stretch;
  border-image-source: image-set(
    url('../img/frame_20px@1x.png') 1x,
    url('../img/frame_20px@2x.png') 2x
  );
}
```

## Practical defaults for this project
- Baseline unit `--u = 4px`.
- Major step 20px (5 × 4px) for composition and row math.
- Top bar rows `--bar-row-h = 48px` (12 × 4px) or `44px` (11 × 4px) as variants.
- Panel frame border art: target 20px (5u) where possible; keep a 12px (3u) control-frame family for compact elements.

## Quick QA checklist
- Toggle the debug overlay; set Unit = 4, Major = 5; align the outer frame edges to major lines.
- Verify seams at common Windows scales: 100%, 125%, 150%, 200%.
- Confirm text baselines across neighbors feel level; adjust inner insets for optical balance, not by stretching the border art.

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

- Do inside edges need to be perfectly even?
  No. Keep outer edges grid-snapped for seams/rows, then use consistent (even asymmetric) inner insets for visual balance. You can add an inner liner for a uniform perceived boundary without altering the art.

- How do we handle smaller screens?
  Use overflow or control variants (e.g., search icon) rather than wrapping that breaks row integrity.

---

When you’re ready, we can add a dev-only overlay and a token block to the mock to validate the grid live—no functional changes required.
