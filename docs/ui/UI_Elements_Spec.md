# UI Elements Spec (Workbench + Drawer)

This reference captures the purpose, visual spec, and planned interactions of key UI elements in the workbench mock. It is wiring‑free (visual intent only) and maps to the current HTML/CSS in `docs/ui/demo/workbench_layout_mock_4px_20major_48bar.html`.

## Structure Tree (overview)
- Shell
  - Topbar
  - Drawer ecosystem
    - Drawer tabs (attached)
    - Drawer (filters panel)
  - Ambient info panel
- App grid
  - Workbench (left)
  - Inspector (right)
    - Subgrids overview
    - Action buttons (slots)
      - Favorite target indicator (new visual intent)
    - Metadata grid
    - Files box
    - Footer: Notes + License (inline)
- Appendices
  - Element spec template
  - Open questions / TODO

---

## Shell

### Topbar
- Purpose: Primary scope and quick system/domain switching.
- Contents:
  - Meta card (app title + current DB/profile)
  - Domain bar (Tabletop, Display, etc.)
  - Search (framed control)
  - Theme toggle (framed control)
  - System bar (contextual to domain)
  - Pins row (future quick toggles)
- Visual:
  - Uses ornate 9-slice frame assets for meta and controls
  - Top-row buttons support decorative overhang art
- Planned interactions (future):
  - Toggle domain → swap system list
  - Search type-to-filter

### Drawer ecosystem

#### Drawer tabs (attached)
- Purpose: Quick entry to filters without occupying workbench width.
- Contents: Lineage, Base, NSFW, More.
- Visual:
  - Left/right dock aware, overhang caps, badge support using green round button asset
  - Separate visual vs hit layers for clean tuck-under effect
- Planned interactions (future):
  - Click tab → open drawer to that panel
  - Badge numbers reflect active filters per panel

#### Drawer (filters panel)
- Purpose: Filter configuration with scrollable body and sticky footer.
- Contents: Panel header (title, pin, close), body (panel content), footer (Apply/Clear).
- Visual: Framed container, resizable width, pinned state remembered.
- Planned interactions (future): Persist pin state, width, and last-opened panel.

### Ambient info panel
- Purpose: Subtle, non-interactive background information area under drawer region.
- Contents: Workspace stats, keyboard tips (grid overlay toggle).
- Visual: Low-contrast framed card; non-interactive

---

## App grid

### Workbench (left)
- Purpose: Results + sidecar view.
- Contents:
  - Workbench toolbar (grid/list toggle, sidecar, sort badge)
  - Workbench-inner (cards grid OR rows list)
  - Optional sidecar (files)
- Visual: Ornate frame with inner padding; responsive grid/list.
- Planned interactions (future): Toggle grid/list, open sidecar.

### Inspector (right)
- Purpose: Detail and quick actions for a selection.
- Structure:
  - Framed, fixed-position column aligned to topbar search and app frame top.
  - Inner scroll for content; bottom inset reserved for footer.
- Visual: All boxes use small ornate frames with consistent spacing.

#### Subgrids overview
1) Name box (wide)
2) Middle cluster: `midgrid`
   - Left sidecol: NSFW, Scale/Base, (Rect action slot)
   - Center: Tall preview
   - Right sidecol: Support, Segmentation, Rect action slot (currently Favorite)
3) Metadata grid: `insp-meta-grid` (2 columns x 3 rows)
4) Files box
5) Inspector footer: Notes + License (inline)

#### Action buttons (slots)
- Purpose: Single-action quick buttons in side columns.
- Current labels:
  - Left side: NSFW (sq), Scale/Base (sq), (rect reserved)
  - Right side: Support (sq), Segmentation (sq), Favorite (rect)
- Visual: Rect height 36px; label only (no wiring).

##### Favorite target indicator (new visual intent)
- Location: Inspector → Right sidecol → Rect action labeled “Favorite”.
- Purpose: Show the current favorite target for the main Favorite action.
- Indicator visuals:
  - Small round badge in the top-right of the Favorite rect (`greenroundbutton.png`)
  - Text content:
    - Star (★) when target is “Favorites” (default)
    - Number (1–9) when target is a user collection; for 10+ use 2-digit (e.g., 12)
  - Tooltip text example: “Target: Favorites” or “Target: Collection 3 (Skulls)”
- Planned behaviors (future; not wired here):
  - Clicking Favorite: send to the current target (1 click)
  - Changing target:
    - Click/long-press on a small top-right indicator elsewhere (e.g., a tiny selector near topbar) opens menu
    - Menu items: Favorites, recent collections, All collections…, New collection…
  - Power shortcuts: Shift+Click = last-used collection; Ctrl+Click = open menu; hover chips on desktop for top collections
- Rationale:
  - Keeps common action (fav) one-click
  - Switching target is explicit but lightweight; indicator always reflects current target

#### Metadata grid
- Purpose: Show key attributes (system, factions, codex unit, designer, collection).
- Visual: 2 columns × 3 rows of small framed boxes.

#### Files box
- Purpose: Placeholder for asset list / file details.
- Visual: Larger framed area; optional grid background.

#### Footer: Notes + License (inline)
- Purpose: Use fixed footer space for a simple note and inline licensing info.
- Contents:
  - Notes: Disabled textarea + disabled checklist (Is printed, Post-processed, Primed, Painted)
  - License inline: two compact rows (Owner, Get it link)
- Visual:
  - Footer space reserved by `--inspector-frame-bottom`
  - Notes in a framed box; license rows inline within the same frame (no extra vertical cost)

---

## Appendices

### Element spec template (for new subgrids)
Use this structure when documenting additional elements:

- Name
- Purpose
- Contents
- Visual (assets, sizes, states)
- Planned interactions (future)
- Notes (a11y, keyboard, edge cases)

### Open questions / TODO
- Define the global placement for the “target selector” badge (top-right of workbench or topbar?)
- Finalize color tagging or number-only for collections
- Decide on max recents in quick menu (3–5?) and search for All collections view
- Accessibility: keyboard map and ARIA roles for menus

---

## Banner Dropdowns (Row‑1 Menus)

This section specifies the banner dropdown used by all top‑row domain buttons (Tabletop, Display, DnD, Terrain, Scale, Unsorted, Favorites). Banners are always used; scrolling is enabled only if the menu has 8+ items (currently only Favorites).

Source: `docs/ui/demo/workbench_layout_mock_4px_20major_48bar.html`

### Structure
- `#bannerMenu` (container)
  - `.menu-frame` — decorative skin: `menubanner1.png`, anchored bottom center
    - `.menu-scroll` — scroll container (only scrolls if 8+ items)
      - `.menu-items` — grid (`gap: 4px`)
        - `.menu-item` — `<button role="menuitem">…</button>`

### Spacing controls
- Head gap: `--banner-head-gap` (crest clearance)
- Tail gap: `--banner-tail-gap` (tip clearance)

Configuration precedence (evaluated on open):
1) Active top‑row button `data-head-gap` / `data-tail-gap`
2) `#bannerMenu` `data-head-gap` / `data-tail-gap`

The resolved values are applied as inline CSS variables on `.menu-frame`. The scroller (`.menu-scroll`) uses those via padding:
- `padding-top: calc(6px + var(--banner-head-gap, 24px))`
- `padding-bottom: calc(6px + var(--banner-tail-gap, 16px))`

### Sizing and scrolling rules
- Always open the banner for row‑1 buttons.
- Determine `shouldScroll = (items.length >= 8)`.
- Visible rows `n = shouldScroll ? 7 : items.length`.
- Desired height `desired = padTop + (itemH * n) + rowGap*(n-1) + padBottom`.
- Clamp to viewport below the button: `finalH = clamp(desired, 120, window.innerHeight - menuTop - 8)`.
- Apply `finalH` to `.menu-frame` (`height` and `max-height`).
- If `shouldScroll`:
  - Set `.menu-scroll` height to `finalH - (tailGap + 8)` to reserve the tail and an extra 8px guard, `overflow-y: auto`.
- Else:
  - Clear explicit scroller size and set `overflow-y: hidden`.

### Accessibility
- `.menu-items` has `role="menu"` and an `aria-label` based on the domain.
- `.menu-item` uses `role="menuitem"` and is focusable.
- Close on outside click or Escape.

### Theming
- `.menu-frame` has transparent background and square corners; only the PNG is visible.
- Skin can be swapped by changing the `background-image` URL in CSS.

### Troubleshooting
- Items overlap the tail when scrolled: confirm we subtract `tailGap + 8` from scroller height and the banner applies `--banner-tail-gap`.
- Non‑scroll menus show a scrollbar: ensure `shouldScroll` is false and scroller overflow is hidden with no explicit height.
