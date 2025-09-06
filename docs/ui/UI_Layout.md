# UI Layout Specification (Workbench + Facets + Inspector)

This document defines the core layout pattern for STL Manager UI: a central workbench (results) surrounded by controls — scope on top, filters on the left (drawer), inspector/details on the right.

## Layout Overview
- Top scope bar: domain/campaign selectors, quick filters, search.
- Left: filter drawer with tabbed quick-filters (facets). Pin/unpin and resizable.
- Center: primary workbench — result grid/list with density toggle and sorting.
- Right: inspector — metadata/details for the current selection; batch toolbar appears on multi-select.

Visual map (desktop)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Top scope bar: Domain • Campaign • Quick filters • Search • Theme            │
├───────────┬───────────────────────────────────────────────┬─────────────────┤
│ Left      │                   Workbench                   │    Inspector    │
│ Drawer    │  Grid/List of Variants (cards or rows)       │  Selected item  │
│ (Filters) │  • Sort • Density toggle • Selection          │  metadata,      │
│           │  • Empty/loading/error states                 │  actions        │
└───────────┴───────────────────────────────────────────────┴─────────────────┘
```

Responsive behavior
- ≥ 1200px: 3-column grid (Left drawer can float/overlay; inspector sticky).
- 960–1199px: 2 columns (drawer overlays; inspector stacks under results or toggles via button).
- < 960px: single column; filters and inspector are slide-in panels.

## Regions & Responsibilities

### 1) Top Scope Bar
- Domain selector (Wargames • Display • Scale Models • Terrain/Diorama).
- Campaign selector when in Wargames (40K • AoS • Heresy • Other • Agnostic).
- Quick chips (Intended use, Scale/Ratio) and global search.
- Persist state in URL/query so views are shareable.

### 2) Left Drawer (Filters)
- Faceted filters by domain (system/faction/unit/base; franchise/character; brand/vehicle/ratio; terrain category/scale/gauge).
- Tabbed quick-filters (Lineage, Base, NSFW, More). Count badges on tabs; Clear/Apply.
- Pin/unpin; resizable; keyboard: `[` and `]` cycle tabs.
- Accessibility: toolbar role for tabs; drawer `role="dialog"` when overlaying.

### 3) Center Workbench (Results)
- Strategy view (cards) ↔ Ledger view (virtualized table). Density toggle.
- Sorting: Relevance • Updated • Designer/Brand • Confidence.
- Selection model: single-select opens inspector; multi-select shows batch bar (Tag, Move, Re-link...).
- Empty/loading/error: skeletons; friendly empty-state with suggested filters; toast on errors.

### 4) Right Inspector (Details)
- Single-select: full metadata pane; domain-aware tabs (Overview, Files, Domain specifics, Tokens, History).
- Multi-select: collapse inspector; show batch toolbar at top of workbench.
- Sticky positioning on desktop; toggle button on smaller screens.

## Interaction & Keyboard
- `/` focus search; `G` Grid/List toggle; `I` toggle Inspector; `[` `]` cycle drawer tabs; `Esc` closes overlays.
- Focus management: return focus to originating control; maintain ARIA roles for tabs/dialogs.

## State, Presets, and Deep Links
- Sync filters/sort/selection to URL (e.g., `?domain=wargames&system=40k&faction=necrons&base=32mm`).
- Saved views: allow naming and loading presets; show modified badge on tabs when filters differ from preset.

## CSS Grid Scaffold (desktop)

```css
.app {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 3fr minmax(280px, 360px);
  gap: 16px;
  max-width: 1440px;
  margin: 0 auto;
  padding: 0 16px 24px;
}
.results { min-height: 60vh; }
.inspector { position: sticky; top: calc(var(--drawer-top) + 8px); align-self: start; }
@media (max-width: 1200px) {
  .app { grid-template-columns: 1fr; }
  .inspector { position: static; order: 3; }
}
```

Notes
- Left drawer may remain as an overlay attached to the app frame (current implementation) — no need to occupy a grid column.
- Right inspector is a normal frame card that can be sticky.

## Mapping to Current Demos
- See `docs/ui/demo/front_page_mock.html` for:
  - Top scope bars, filter drawer with tabbed quick-filters, sizing tuner.
  - Drawer pin/unpin + resize; tab imagery and hover/active behavior.
- Styling reference: `docs/ui/UI_Styling_OrnateFrames.md` and `docs/ui/demo/ornate_frame_demo.html` for frame borders.

## Tech Notes
- Desktop: Tauri + React + Tailwind (or Electron) with `react-virtual` for lists.
- Web: FastAPI/Flask backend + React frontend; `phosphor-icons`/`heroicons` for icons.
- Performance: skeleton loaders, request de-dup, client-side cache; DB pagination.

## Open Questions
- Inspector default tabs per domain; which fields surface in Overview.
- Batch toolbar actions for MVP vs later.
- Saved views UX (where to surface; how to sync with URL).

---

## Admin & Reporting
- Report mismatch: primary action in the Inspector header (and on Variant Detail). Opens a compact form with prefilled context (variant_id, current fields snapshot, optional comment). Submits to a Mismatch Inbox without navigating away from the workbench.
- Admin entry point: top-bar "Admin" button (menu: Inbox, Jobs), or optionally a bottom-right floating button styled like a strategy-game menu. Opens in a modal/route that preserves workbench state.
- Mismatch Inbox: table with filters/status and bulk accept/deny; exports triage JSON for fixer scripts.

## Files Sidecar Viewer
- Goal: preview a variant’s files without losing focus while scanning.
- Behavior:
  - Toggle "Sidecar Files" from the workbench toolbar or Inspector. The sidecar attaches to the right side of the workbench (not the Inspector) so selection remains active.
  - In Ledger (list) mode, rows align left; the sidecar occupies a right slice of the workbench. Up/Down (or J/K) cycles selection and updates the sidecar.
  - In Strategy (card) mode, the sidecar can be a detachable floating panel.
- Layout sketch: when enabled, workbench uses `grid-template-columns: 1fr minmax(320px, 560px)`; otherwise a single column.
- Contents: file list with icons, sizes, quick actions (open-in-folder future), and thumbnail/preview when available.

## Explainability (Provenance & Tokens)
- Inspector tab that surfaces tokenization, rules fired, scores, and alias provenance for the selected variant—read-only justification of current metadata/matcher outcome.
- Provides links to safe overrides; pairs with the Report action for quick triage.

## Saved Views & Pins
- Saved Views list appears in the Filter Drawer with actions: Load, Rename, Delete, Pin/Unpin.
- Pins Bar: pinned views render as small decorative banners right under the top scope bar (inspiration: EU4 bookmarks). Hotkeys 1–9 jump to pinned views.
- Deep links: filters/sort/selection sync to the URL; saved views store the same state JSON for recall.

## Thumbnails & Previews (First Cut)
- Grid cards show placeholder thumbnails initially (file-type glyph + category color). When available, consume `thumbnail_url` from API; otherwise show initials/icon.
- Sidecar tries preview for common formats (PNG/JPG; STL static render later) and shows metadata when preview isn’t available.

## Live Updates Strategy
- Single-user assumption: no background SSE/WS required. Views refresh on user-triggered actions (filters applied, edits saved, view loaded). Provide a small Refresh button in the workbench toolbar.

## Tools Dock/Menu
- Define a small set of tools accessible globally: Proxy Manager, Variant Editor, Vocab Editor, Batch Update, Mismatch Inbox.
- Entry points: a top-bar "Tools" menu for desktop and/or a bottom-right ornate tools strip for quick access. Tools open as overlays/routes and preserve workbench selection on close.
