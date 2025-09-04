# UI Vision and Interaction Design

A fun, game‑inspired interface (Europa Universalis vibe) that still surfaces dense data clearly, with safe actions and explainability.

## Goals
- Make complex metadata scannable without feeling like a spreadsheet.
- Default to non‑destructive actions; expose “why” behind matches and edits.
- Provide fast triage loops (report mismatches, review, apply).

## Global Layout & Navigation
- Top bar: campaign selector (`40K`, `AoS`, `Heresy`), quick filters (scale, intended use), search.
- Left sidebar (“Factions Atlas”): faction icons with coverage rings and open‑issue badges.
- Main content mode toggle: Strategy view (cards/tiles) ↔ Ledger view (table).

## Visual Theme & Accessibility
- Palette: deep blues/golds with light parchment accents; keep high contrast (WCAG AA+).
- Typography: serif for headings (e.g., Cinzel/Spectral), sans for UI text (e.g., Inter). Small‑caps for section labels.
- Iconography: unit role (HQ/Troops/Elite/etc.), base shape/size, segmentation/support state.

## Key Screens
- Campaign Overview
  - KPIs: total variants, matched %, parts coverage; trend sparklines.
  - Widgets: “Top misses,” “Recently fixed,” “Pending mismatch reports.”
- Faction Browser
  - Grid of faction tiles with coverage rings; click through to drilldowns.
- Variant Explorer
  - Strategy view: card grid with filters as chips (designer, system, faction, scale, intended use, confidence).
  - Ledger view: virtualized table; user‑selectable columns; bulk actions.
- Variant Detail (Tabbed)
  - Overview: core fields, badges, coverage ring, quick actions.
  - Files: file list, previews (future), archive pointers.
  - Parts: linked parts/wargear, compatibility hints.
  - Provenance & Tokens: token trace, rules triggered, score breakdown, alias provenance.
  - History: audit timeline, manual overrides.
- Admin: Mismatch Inbox
  - Queue with filters (status, faction, designer); bulk accept/deny; export triage JSON.

## Reusable Components
- Variant Card (Strategy view)
  - Header: inferred unit/designer + confidence pill.
  - Badges: scale, base profile (icon), support_state, segmentation.
  - Coverage ring: matched vs unknown fields.
  - Footer: Open • Report mismatch • Pin.
- Filters as Chips
  - Click to add/remove; keyboard `/` focuses search; quick clear.
- Ledger (Power Users)
  - Virtualized rows, pinned columns, CSV/JSON export, selection/bulk bar.

## Explainability & Safety
- “Why matched” drawer on cards/detail: tokens used, rules triggered, score breakdown, alias provenance, file path hints.
- Safe by default: dry‑run first; only fill empty fields unless `--overwrite` is enabled; `--min-confidence` gates.

## Mismatch Reporting Loop
- Report CTA on Variant detail (“Report mismatch”).
- Capture: `variant_id`, current fields (system/faction/franchise/character), filenames/paths, token trace, optional comment.
- Store in `mismatch_reports` table (status: new/reviewed/fixed; timestamps; resolution notes).
- Admin inbox: filter/sort, accept/deny; export triage JSON for fixer scripts; apply with dry‑run gates.

## First Implementation Slice (MVP)
- Build Variant Explorer (Strategy view) and Variant Detail (Overview + Tokens tabs).
- Wire filters (designer/system/faction/scale/intended use) and a mode toggle to a simple Ledger.
- Implement “Report mismatch” posting to `mismatch_reports` (stub OK initially).

## Future Enhancements
- Thumbnail previews; archive peeking.
- Saved searches/views; pins/collections.
- User‑managed ignore/negatives overlays to quiet noisy folders.
- Offline‑first caching; background refresh.

## Tech Notes (optional)
- Desktop: Tauri + React + Tailwind (or Electron) with `react-virtual` for lists.
- Web: FastAPI/Flask backend + React frontend; `phosphor-icons`/`heroicons` for icons.
- Performance: skeleton loaders, request de‑dup, client‑side cache; db pagination.
