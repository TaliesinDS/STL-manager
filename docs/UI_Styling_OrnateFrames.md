# UI Styling: Ornate Frames (Nine-slice, Tiling, and CSS Gradients)

This guide captures practical patterns for Europa Universalis–style ornate frames you can reuse in the STL Manager UI.

## Patterns at a glance
- Nine-slice (9-patch): 4 corners (no scale), 4 edges (tile/stretch one axis), 1 center (tile/fill). Scales cleanly to any size.
- Tiled strips: fixed-size left/right caps with a tiled center bar (good for headers/footers that stretch horizontally).
- Fixed ornate popups: bake scrollwork into a fixed-size frame; or layer non-scaling ornaments over a 9-slice base.

## Lightweight CSS approach (no images)
Use border gradients and layered box-shadows to fake a rounded gold frame. Add an inner black cut line and a faint gold halo for depth. Keep light direction consistent (e.g., top-left) by biasing gradient angles.

- Working demo: `docs/demo/ornate_frame_demo.html` (open in a browser)
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
