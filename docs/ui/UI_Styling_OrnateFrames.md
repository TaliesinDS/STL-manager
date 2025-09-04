# UI Styling: Ornate Frames (Nine-slice, Tiling, and CSS Gradients)

This guide captures practical patterns for Europa Universalis–style ornate frames you can reuse in the STL Manager UI.

## Patterns at a glance
- Nine-slice (9-patch): 4 corners (no scale), 4 edges (tile/stretch one axis), 1 center (tile/fill). Scales cleanly to any size.
- Tiled strips: fixed-size left/right caps with a tiled center bar (good for headers/footers that stretch horizontally).
- Fixed ornate popups: bake scrollwork into a fixed-size frame; or layer non-scaling ornaments over a 9-slice base.

## Lightweight CSS approach (no images)
Use border gradients and layered box-shadows to fake a rounded gold frame. Add an inner black cut line and a faint gold halo for depth. Keep light direction consistent (e.g., top-left) by biasing gradient angles.

- Working demo: `docs/ui/demo/ornate_frame_demo.html` (open in a browser)
- Core class to copy: `.frame` (CSS below is also in the HTML demo)

```css
.frame {
  border: 6px solid transparent;             /* gold ring area */
  border-radius: 12px;
  background:
    /* panel fill */
    linear-gradient(#12100b, #17140d) padding-box,
    /* gold border with darker edges for rounded look */
    linear-gradient(
      140deg,
      #6a4b14 0%,
      #d8b85a 44%,
      #f2de8a 56%,
      #6a4b14 100%
    ) border-box;
  /* inner cut line, outer black line, faint gold halo, drop shadow */
  box-shadow:
    inset 0 0 0 1px rgba(0,0,0,0.7),
    0 0 0 1px #0c0a05,
    0 0 0 3px rgba(216,184,90,0.25),
    0 10px 24px rgba(0,0,0,0.45);
}
```

Tip: For an explicit black ring between two gold rings, wrap the panel in a parent div that provides the outer gold effect, and let the inner element provide the black ring and inner gold with its own `.frame` style.

## Asset-based approach (optional)
Create a single PNG with corners/edges/center, then use CSS `border-image` for true 9-slice. Pack assets into an atlas with 2–4 px padding to avoid bleeding; tile edges, don’t stretch them.

Example:
```css
.panel {
  border: 24px solid transparent;
  border-image-source: url(./frame_9slice.png);
  border-image-slice: 24 fill;
  border-image-repeat: round;
}
```

## Engine notes (if not Web)
- Unity: Sprite Editor → define borders → UI Image mode Sliced/Tiled.
- Unreal UMG/Slate: set Brush Margin (9-slice), choose tiling/stretch per edge.

## When to choose what
- Dynamic panels that resize often: CSS gradients or 9-slice.
- Headers/footers: three-slice “cap • tile • cap” strips.
- Fixed ornate popups: baked artwork, or a 9-slice base with decorative overlays.

## 9-slice (border-image) recipe for gold frames

A clean, seam-free gold frame with perfect corners using a single PNG and CSS `border-image`.

Checklist for asset prep
- Create a square source PNG (e.g., `256x256`) with a uniform band thickness (e.g., `16px`).
- Draw the gold band bevel (dark → mid → highlight → mid → dark) and add soft inner/outer black rings.
- Keep corners fully opaque and avoid rib/grain details inside corners; put any vertical ribbing only along the straight edges.
- Export at 1x and 2x for crispness: `frame_9slice@1x.png`, `frame_9slice@2x.png`.

Drop-in CSS
```css
/* 9-slice gold frame: corners unscaled, edges stretch, center fills */
.frame-nine {
  --b: 16; /* band thickness in px of the source PNG */
  border: calc(var(--b) * 1px) solid transparent;
  border-radius: 6px; /* modern browsers respect radius with border-image */
  background: linear-gradient(#12100b, #17140d) padding-box; /* panel fill */

  /* Prefer high-DPI via image-set when available */
  border-image-source: image-set(
    url('../img/frame_9slice@1x.png') 1x,
    url('../img/frame_9slice@2x.png') 2x
  );
  border-image-slice: var(--b) fill;   /* keep center; align with source band */
  border-image-width: 1;               /* match CSS border thickness */
  border-image-repeat: stretch;        /* gradient edges: stretch; textures: round */
}
```

Troubleshooting tips
- Hairlines at corners: ensure corner pixels are fully opaque and your cut distance exactly matches `--b` on all sides.
- Wavy or repeating edges: use `stretch` for gradient-style bands; only use `round` if your edge art is designed to tile.
- Soft rings look muddy: export a 2x asset and use `image-set` so thin ring lines align to device pixels.
- Radius artifacts: keep the same `border-radius` on the element using `border-image`; avoid inner wrappers that clip corners differently.
- Mismatched thickness: keep the PNG’s band exactly `--b` and the CSS `border` set to the same.

## Faction Browser: minimal CSS + HTML (from the demo)

Use this snippet for a resizable panel with a capped header strip. See the full working page at `docs/ui/demo/ornate_frame_demo.html`.

```css
/* Gold frame: CSS-only (no images) */
.frame {
  border: 6px solid transparent;  /* gold ring area */
  border-radius: 12px;
  background:
    /* panel fill */
    linear-gradient(#12100b, #17140d) padding-box,
    /* gold border with darker edges for rounded look */
    linear-gradient(
      140deg,
      #6a4b14 0%,
      #d8b85a 44%,
      #f2de8a 56%,
      #6a4b14 100%
    ) border-box;
  /* inner cut line, outer black line, faint gold halo, drop shadow */
  box-shadow:
    inset 0 0 0 1px rgba(0,0,0,0.7),
    0 0 0 1px #0c0a05,
    0 0 0 3px rgba(216,184,90,0.25),
    0 10px 24px rgba(0,0,0,0.45);
}
.frame .content { padding: 14px 16px; }

/* Header bar: cap • tile • cap */
.capbar {
  position: relative;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 8px 8px 0;
  color: #f5e8b0;
  text-shadow: 0 1px 0 #382a0a;
}
.capbar::before,
.capbar::after {
  content: "";
  position: absolute;
  top: 0; bottom: 0;
  width: 24px;               /* end caps */
  background: linear-gradient(180deg, #403015, #1f180a);
  box-shadow: inset 0 0 0 1px rgba(0,0,0,0.6);
}
.capbar::before { left: 0; border-top-left-radius: 8px; border-bottom-left-radius: 8px; }
.capbar::after  { right: 0; border-top-right-radius: 8px; border-bottom-right-radius: 8px; }
.capbar .strip {
  position: absolute; left: 24px; right: 24px; top: 0; bottom: 0;
  background: repeating-linear-gradient(90deg, #31240e 0px, #36270f 8px, #2b1f0c 16px);
  box-shadow: inset 0 0 0 1px rgba(0,0,0,0.5);
}
.capbar .label { position: relative; z-index: 1; font-weight: 600; letter-spacing: 0.03em; }
```

```html
<div class="frame">
  <div class="capbar">
    <div class="strip"></div>
    <div class="label">Faction Browser</div>
  </div>
  <div class="content">
    <!-- Your panel content here -->
  </div>
  
</div>
```
