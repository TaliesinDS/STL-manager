# UI Assets Spec — Drawer and Tabs

This document defines the minimal asset pack and integration details for the new drawer and tab UI so that borders, tabs, and states stay visually consistent across the app.

## Goals
- One consistent ornamental border across panels (drawer, cards, tuner, etc.).
- Two tab variants: a base tab and a visually enhanced active tab that overlaps the drawer edge.
- Left and right dock support without doubling assets (prefer CSS mirroring).

## Minimum viable assets
- Frame border (9-slice)
  - Filename(s): `assets/ui/frame_9slice@1x.png`, `assets/ui/frame_9slice@2x.png` (optional `@3x`)
- Tab base (inactive/neutral)
  - Filename(s): `assets/ui/tab_base@1x.png`, `assets/ui/tab_base@2x.png`
- Tab active (slight overlap/glow/highlight)
  - Filename(s): `assets/ui/tab_active@1x.png`, `assets/ui/tab_active@2x.png`

## Nice-to-haves (optional)
- Tab hover and pressed variants: `tab_hover@2x.png`, `tab_pressed@2x.png`
- Thin shadow border (9-slice) for “drawer open” depth: `frame_shadow_9slice@2x.png`
- Badge background for counts (if not CSS-only): `tab_badge@2x.png`
- Resize handle (vertical repeat or slim 9-slice): `resize_handle_y@2x.png`

## Export specs
- Format: PNG with alpha (fastest path). If you want infinite scale for the border, SVG for the 9-slice is fine, but start with PNG.
- Densities: Provide `@1x` and `@2x`. Add `@3x` if you frequently design on 200%–300% scale.
- Color: Export as final-colors or neutral grayscale to allow CSS tinting.

### Sizing presets
- Standard preset (recommended): 96×96 at `@1x` (192×192 at `@2x`).
- High‑detail preset (for ornate bevel/engraving): 128×128 at `@1x` (256×256 at `@2x`).
- Oversized (e.g., 1024×1024): not recommended for this UI. It increases GPU upload and memory with no visible gain at on‑screen sizes.

### 9-slice frame recommendations
- Canvas size:
  - Standard: 96×96 px at `@1x` (192×192 at `@2x`).
  - High‑detail: 128×128 px at `@1x` (256×256 at `@2x`).
- Slice insets: 12 px at `@1x` (24 px at `@2x`). Adjust to match your corner radius + stroke. Corners/edges live in the perimeter; center remains transparent.
- The existing CSS uses a decorative frame thickness variable: `--frame-border: 6px`. If your 9‑slice uses 12 px slices, set `border-width: 12px` where applied (see CSS wiring below). At `@2x`, set `border-image-slice: 24`.

#### Edge rules for 9‑slice images
- No outer padding: the border’s outside edge should be flush with the image edge (the very first pixel row/column). Any transparent padding reduces effective resolution and can create halos.
- Opaque outermost pixels: avoid feathering to transparent at the outer edge; ensure the outermost pixel row is solid (e.g., the black ring). This prevents background bleed when composited.
- Match slices to border width: if your slice is 12 px at `@1x`, use `border-width: 12px` and `border-image-slice: 12` (double both at `@2x`). Stick to integer values to avoid half‑pixel scaling blur.
- Don’t bake outer shadows: add drop shadows in CSS (`box-shadow`) instead of the image; `border-image` clips to the element’s border box and will crop outer glows.
- Keep details away from stretch zones: place fine engraving near corners/caps; keep the side bands relatively uniform so `stretch`/`round` doesn’t distort details.

#### Rounded corners with 9‑slice
- `border-radius` clips the painted border (including `border-image`) to a rounded border box. You do not need to pre‑cut outside triangles in the source image.
- Corner tiles (the four 9‑slice corners) should include the full curved band (outer ring → gold → inner ring). The area inside the inner ring can be transparent so the element’s background fill (painted on `padding-box`) shows through.
- Avoid transparent wedges on the outer edge of the corner tiles; keep the outermost pixels opaque to prevent background bleed along the curve.
- If you see tiny “triangles” at the corners:
  - Ensure `border-width` matches your slice thickness (e.g., 12 px) and that `border-image-slice` uses the same number (doubled at `@2x`).
  - Make sure your element’s background is painted on the `padding-box` (default for `background`, or explicitly via `background-clip: padding-box`) so it doesn’t overlap the border region.
  - Check that corner art reaches both the outer and inner border arcs without gaps; anti‑alias the inner arc against transparency, not against a different color.
- Large radii: For very large `border-radius`, corners scale up the corner tiles. Keep corner gradients and engravings symmetric so scaling preserves the look.

### Button sizing (grid‑aligned defaults)
These sizes are derived from the UI mock’s grid tokens so assets/layout stay in sync.

- Grid: `--grid-u = 4px`, `--grid-major = 5` ⇒ 1 major = 20 px.
- Top row (domain) button width: `--btn-major-cols = 8` majors ⇒ 8 × 20 = 160 px.
- Second row (system) button width: `--btn2-major-cols = var(--btn-major-cols)` ⇒ 8 × 20 = 160 px (unless overridden).
- Row height: `--bar-row-h = 48px`; buttons are `height: 100%` of the row (visual interior minus framed borders).

##### Corner bleed for rounded art (filling the square corners)
If your original artwork has a rounded outer silhouette, you still need the 9‑slice image’s corner tiles to reach the square image edges. Simple ways to “bleed” the outer edge:
- Solid bleed: extend the outer ring color (e.g., black) straight to the top/left image edges in each corner tile (1–2 px at `@1x`, 2–4 px at `@2x`). This guarantees opaque outermost pixels and avoids gaps.
- Gradient bleed: push your outermost gradient/metal edge out to the square edges, but keep the final pixel row/column a flat color to avoid aliasing.
- Uniform cap: add a very thin, uniform outer stroke to your art (same color as the outer ring), so the outside of every side/corner ends in that stroke.

CSS helper (optional): if you want a safety net, add a 1 px outer stroke via `box-shadow` under the border image.
```css
.frame {
  /* paints a crisp 1px outer line around the border box */
  box-shadow: 0 0 0 1px #000000, /* then your existing shadows... */
              0 10px 24px rgba(0,0,0,0.45);
}
```
Use 2 px at `@2x`. This can mask tiny mismatches while you iterate on the assets.

### Tab asset recommendations
- Baseline height: match the CSS variable `--tab-size` (default 44 px). For `@2x`, export ~88 px tall. Include a few extra pixels of vertical padding if needed and scale via `background-size`.
- Horizontal slicing: design as three functional regions (can be baked into one image and stretched via `background-size`):
  1) Inner edge (meets the drawer): flat, non-overhanging.
  2) Middle: stretchable horizontally.
  3) Outer “overhang cap”: 16–24 px that protrudes past the drawer edge; keep this visually crisp (non-stretch).
- Active tab should slightly overlap the drawer edge and may include a brighter rim, bevel, or glow.
- Right dock: Use CSS mirroring via `transform: scaleX(-1)` on the tab container, then un-flip the inner label content (see wiring below), or export a mirrored asset set.

## File structure
```
assets/
  ui/
    frame_9slice@1x.png
    frame_9slice@2x.png
    tab_base@1x.png
    tab_base@2x.png
    tab_active@1x.png
    tab_active@2x.png
    # Optional
    tab_hover@2x.png
    tab_pressed@2x.png
    frame_shadow_9slice@2x.png
    tab_badge@2x.png
    resize_handle_y@2x.png
```

## CSS wiring examples

### Frame border via `border-image`
```css
/* Apply to .frame where you want image borders */
.frame {
  border-width: 12px;              /* match your 9-slice inset */
  border-style: solid;
  border-image-source: url('assets/ui/frame_9slice@2x.png');
  border-image-slice: 12 fill;     /* keep center fill as needed */
  border-image-width: 12;
  border-image-repeat: stretch;    /* or round if your edges repeat cleanly */
}
```

If you use the current gradient-based `.frame`, you can layer `border-image` on top or swap to the image-only approach; keep the variable `--frame-border` in sync with your chosen `border-width`.

### Tabs base and active
```css
.drawer-tab {
  background-image: url('assets/ui/tab_base@2x.png');
  background-repeat: no-repeat;
  background-size: 100% 100%;
}

.drawer-tab[aria-pressed='true'] {
  background-image: url('assets/ui/tab_active@2x.png');
}

/* Optional hover/pressed */
.drawer-tab:hover:not([aria-pressed='true']) {
  background-image: url('assets/ui/tab_hover@2x.png');
}
.drawer-tab:active:not([aria-pressed='true']) {
  background-image: url('assets/ui/tab_pressed@2x.png');
}

/* Right dock: flip the overhang cap, but unflip inner content */
[data-dock='right'] .drawer-tab {
  transform: scaleX(-1);
}
[data-dock='right'] .drawer-tab .txt,
[data-dock='right'] .drawer-tab .count {
  transform: scaleX(1); /* neutralize inherited flip if any */
}
```

### Drawer open/closed alignment (already wired)
- Tabs ride with the drawer edge when open and sit at the viewport edge when closed.
- Left dock uses `left: var(--drawer-w)` plus frame thickness; right dock uses `right: var(--drawer-w)`.

## Theming
- Two approaches:
  1) Two asset sets (dark/light). Swap paths based on `data-theme`.
  2) Neutral grayscale PNGs tinted via CSS (e.g., `filter`, `mix-blend-mode`, or overlay gradients) for subtle adjustments.
- Ensure contrast and readability for labels and count badges across themes.

## Performance
- Preload critical UI assets (`<link rel="preload" as="image" href="...">`) if necessary.
- Keep PNG sizes modest; prefer shared textures and fewer variants.
- Consider a sprite sheet if you find many micro-requests in production.

## QA checklist
- Borders: corners and edges don’t distort at common sizes; center remains transparent.
- Tabs: base and active align cleanly with the drawer edge; overhang cap remains crisp; no stretching artifacts.
- Right dock: mirrored visuals look correct; text and badges are readable (not inverted).
- DPI: verify on 1x and 2x (and 3x if shipped).
- Themes: adequate contrast in dark and light.

## Versioning and maintenance
- Use semantic suffixes in filenames for major look changes (e.g., `frame_9slice_v2@2x.png`).
- Keep this spec updated if `--tab-size`, `--frame-border`, or drawer measurements change.

---
If you want, we can add a minimal loader to prefetch the new images and a CSS variable gate to switch between gradient and image borders for A/B review.
