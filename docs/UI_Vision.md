# UI Vision and Interaction Design

A fun, game‑inspired interface (Europa Universalis vibe) that still surfaces dense data clearly, with safe actions and explainability — across tabletop wargames, display models (anime/figurines), scale models (tanks/cars/aircraft), and terrain/diorama assets.

## Goals
- Make complex metadata scannable without feeling like a spreadsheet.
- Default to non‑destructive actions; expose “why” behind matches and edits.
- Provide fast triage loops (report mismatches, review, apply).
- Support multiple domains beyond Warhammer: Display Models (franchise/character, pose/outfit), Scale Models (brand/kit code/scale ratio), and Terrain/Diorama (category, dimensions, gauge compatibility) in addition to Wargames (system/faction/unit).
- Within Wargames, support both exhaustive systems (Warhammer) and lighter “Other Systems” (e.g., Trench Crusade, OPR, Frostgrave) without requiring full codex coverage; also support an Agnostic Tabletop library (RPG monsters/PCs, generic proxies).

## Global Layout & Navigation
- Top bar: domain selector (Wargames • Display • Scale Models • Terrain/Diorama) and, when in Wargames, a campaign sub‑selector (`40K`, `AoS`, `Heresy`, `Other Systems`, `Agnostic`). Quick filters (intended use, scale/ratio), search.
- Left sidebar adapts by domain:
  - Wargames: “Factions Atlas” with coverage rings and open‑issue badges.
    - Other Systems: simplified “Systems Browser” tile list (e.g., Trench Crusade) with basic tags (no exhaustive faction trees required).
    - Agnostic: lineage/family filters (undead, orcs, demons, soldiers), unit roles (hero/monster/troops), base size/shape chips.
  - Display: “Franchise Gallery” with franchise tiles and character counts.
  - Scale Models: “Garage/Hangar” filters (brand, era, vehicle type) and scale ratio chips (1/6, 1/12, 1/24, 1/35, 1/72…).
  - Terrain/Diorama: terrain categories (buildings, foliage, roads/bridges, scatter), optional rail gauge filters (HO, N, O) and scale compatibility.
- Main content mode toggle: Strategy view (cards/tiles) ↔ Ledger view (table) in all domains.

## Visual Theme & Accessibility
- Palette: deep blues/golds with light parchment accents; keep high contrast (WCAG AA+).
- Typography: serif for headings (e.g., Cinzel/Spectral), sans for UI text (e.g., Inter). Small‑caps for section labels.
- Iconography: unit role (HQ/Troops/Elite/etc.), base shape/size, segmentation/support state.

## Key Screens
- Dashboard (domain‑aware)
  - KPIs: total variants, matched %, coverage per domain; trend sparklines.
  - Widgets: “Top misses,” “Recently fixed,” “Pending mismatch reports,” “Largest franchises/brands,” “Popular scales/ratios.”
- Wargames: Faction Browser
  - Grid of faction tiles with coverage rings; click through to drilldowns.
- Wargames: Systems Browser (Other Systems)
  - Tile grid of lighter systems (e.g., Trench Crusade) with basic stats (variants count, coverage %); inside, use tags and simple categories instead of exhaustive faction trees.
- Wargames: Agnostic Tabletop Library
  - Filters for lineage/family (undead, orcs, elves, soldiers), role (PC/NPC/monster), base profile, and intended use (RPG/proxy); card tiles show lineage and base badges.
- Display: Franchise Browser
  - Grid of franchise tiles (e.g., Attack on Titan, The Boys) with character counts and coverage rings; character drilldown pages.
- Scale Models: Garage/Hangar
  - Filters and tiles by brand (Tamiya, Revell…), vehicle class (tank, car, aircraft, ship), era/theater; scale ratio facets.
- Terrain/Diorama: Terrain Library
  - Category tiles (buildings, foliage, roads/bridges, scatter, bases) with compatibility tags (tabletop/rail gauges).
- Variant Explorer (all domains)
  - Strategy view: domain‑aware card grid; filters as chips (designer/brand, franchise/system, faction/character/vehicle type, scale or ratio, intended use, confidence).
  - Ledger view: virtualized table; user‑selectable columns; bulk actions.
- Variant Detail (Tabbed; domain‑aware fields)
  - Overview: core fields, badges, coverage ring, quick actions.
  - Files: file list, previews (future), archive pointers.
  - Domain‑specific tab:
    - Wargames: Parts/wargear, unit role, base profile.
      - Other Systems: minimal structure (system name, tags, optional factions/categories) without requiring full codex taxonomy.
      - Agnostic: lineage/family, role (PC/NPC/monster), base profile; optional "proxy for" link(s).
    - Display: Franchise, character, pose/outfit, collection/release.
    - Scale Models: Brand/manufacturer, kit name/code, scale ratio (1/35), vehicle type/class, era/theater.
    - Terrain/Diorama: Category/subtype, dimensions/footprint, scale compatibility and rail gauge.
  - Provenance & Tokens: token trace, rules triggered, score breakdown, alias provenance.
  - History: audit timeline, manual overrides.
- Admin: Mismatch Inbox
  - Queue with filters (status, domain, faction/brand/franchise), bulk accept/deny, export triage JSON.

## Reusable Components
- Variant Card (Strategy view)
  - Header: inferred label (Unit/Character/Kit name) + confidence pill.
  - Badges (domain‑aware):
    - Wargames: base profile icon, support_state, segmentation.
      - Other Systems: system badge + simple category/tag badges.
      - Agnostic: lineage/family badge + base size/shape; optional “proxy” tag.
    - Display: franchise/character badges, collection/cycle (if known).
    - Scale Models: brand logo/text, scale ratio (1/24, 1/35), vehicle class icon.
    - Terrain/Diorama: terrain category icon, scale/gauge compatibility.
  - Coverage ring: matched vs unknown fields.
  - Footer: Open • Report mismatch • Pin.
- Filters as Chips
  - Click to add/remove; keyboard `/` focuses search; quick clear.
- Ledger (Power Users)
  - Virtualized rows, pinned columns, CSV/JSON export, selection/bulk bar.

## Explainability & Safety
- “Why matched” drawer on cards/detail: tokens used, rules triggered, score breakdown, alias provenance, file path hints.
- Safe by default: dry‑run first; only fill empty fields unless `--overwrite` is enabled; `--min-confidence` gates.
 - Domain‑specific rule tracing: show which rule sets fired (e.g., brand/kit code vs franchise/character vs unit/faction) to make cross‑domain logic understandable.

## Mismatch Reporting Loop
- Report CTA on Variant detail (“Report mismatch”).
- Capture: `variant_id`, current fields (domain‑aware: system/faction/unit or franchise/character or brand/kit/ratio or terrain category/scale), filenames/paths, token trace, optional comment.
- Store in `mismatch_reports` table (status: new/reviewed/fixed; timestamps; resolution notes).
- Admin inbox: filter/sort, accept/deny; export triage JSON for fixer scripts; apply with dry‑run gates.

## First Implementation Slice (MVP)
- Build Variant Explorer (Strategy view) with a domain selector and domain‑aware filters, plus Variant Detail (Overview + Tokens tabs).
- Wire filters per domain (e.g., Wargames: system/faction/unit/base; Display: franchise/character/collection; Scale Models: brand/vehicle type/ratio; Terrain: category/scale/gauge) and a mode toggle to a simple Ledger.
- Implement “Report mismatch” posting to `mismatch_reports` (stub OK initially) with domain tagging.

## Future Enhancements
- Thumbnail previews; archive peeking.
- Saved searches/views; pins/collections.
- User‑managed ignore/negatives overlays to quiet noisy folders.
- Offline‑first caching; background refresh.
 - Brand/manufacturer dictionaries and kit code recognition for scale models.
 - Rail gauge and scenic compatibility helpers for terrain/railroad use.
 - Pose/outfit tagging helpers for display models; optional sensitive content hiding.

## Tech Notes (optional)
- Desktop: Tauri + React + Tailwind (or Electron) with `react-virtual` for lists.
- Web: FastAPI/Flask backend + React frontend; `phosphor-icons`/`heroicons` for icons.
- Performance: skeleton loaders, request de‑dup, client‑side cache; db pagination.
 - Styling reference and demo: see `docs/ui/UI_Styling_OrnateFrames.md` and open `docs/ui/demo/ornate_frame_demo.html` in a browser for a working CSS example.
