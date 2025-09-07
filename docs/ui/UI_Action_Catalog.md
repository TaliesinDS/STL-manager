# STL Manager UI — Action Catalogue (Simple Hierarchy)

This is a concise, hierarchical list of what the UI needs to expose, where it likely lives, and how to handle long lists (use scrollable, searchable selectors like a country picker).

## 1) Navigation scope
- Domain (top bar)
  - Tabletop
    - Systems (row 2): 40K, AoS, Heresy, Other, Agnostic
      - 40K
        - Faction → scrollable + search
          - Subfaction/Chapter/Forge World/Regiment → scrollable + search (if applicable)
        - Unit type (HQ/Troops/Elites/Fast/Heavy/Transport/Flyer/Monster/Titanic) → chips
        - Unit → scrollable + search; mark unique/Legends where relevant
        - Base profile → dropdown/chips (size + shape)
        - Parts: Bodies/Wargear → multi‑select filters (chips)
      - AoS
        - Grand Alliance (Order/Chaos/Death/Destruction) → segmented
        - Faction → scrollable + search
          - Subfaction/Temple/Stormhost (if applicable) → scrollable + search
        - Unit type (Leader/Battleline/Behemoth/Artillery/Other) → chips
        - Unit → scrollable + search (mark unique/Legends)
        - Base profile → dropdown/chips
      - Heresy (30K)
        - Allegiance (Loyalist/Traitor/Mechanicum/etc.) → segmented
        - Legion/Army → scrollable + search
        - Rite/Detachment (optional) → selector
        - Unit category (HQ/Elites/Troops/Fast/Heavy/Lords of War) → chips
        - Unit → scrollable + search
        - Base profile → dropdown/chips
  - Display
    - Genre (Studio/Fantasy/Sci‑Fi) → segmented
    - Designer → scrollable + search
    - Franchise/Character (if known) → scrollable + search
    - Scale (1/6, 1/7, etc.) → chips
    - Segmentation/Support state → chips
    - NSFW visibility → radio (Hide/Blur/Show)
  - D&D
    - Role (Characters/Monsters/Props) → segmented
    - Lineage (races/species) → scrollable + search + multi‑select (country‑selector pattern)
    - CR/Size/Type filters → chips/range
    - Base profile → dropdown/chips
  - Terrain
    - Type (Battlefield/Scenery/Buildings) → segmented
    - Theme/Biome/Setting → chips
    - Footprint/Scale (28–32mm, 1:35, etc.) → chips

## 2) Global controls (always available)
- Search (top bar)
- Theme toggle (top bar)
- Refresh (workbench toolbar)
- Sort (workbench toolbar)
- View: Grid/List (workbench toolbar)
- Sidecar toggle (workbench toolbar)
- Drawer tabs for filters (Lineage, Base, NSFW, More) with Apply/Clear/Pin

## 3) Item (variant) actions
- Open/Preview (primary)
- Report mismatch (primary)
- Tagging: lineage, intended use (chips/modal)
- Assign base profile (picker)
- Open in folder (system action)
- Queue/Export (e.g., to slicer list)
- Delete (with confirm) / Restore (if soft‑delete)
- Pin/favorite

## 4) Selection & bulk actions (appear when items are selected)
- Assign base profile to selection
- Tag selection (lineage, intended use)
- Designer override (if misdetected)
- Re‑run match (dry‑run/apply) for selection
- Export CSV / Create report

## 5) Long‑list selector pattern
- Use a scrollable, searchable list (like a country picker) with:
  - Type‑to‑filter, A–Z jump, sticky letter headers (optional)
  - Multi‑select for filter contexts (e.g., Lineage)
  - Clear/Select‑all affordances and keyboard navigation

## 6) End‑user database tools (safe by default)
- Switch target DB (file picker) & show current DB info
- Backup database (create timestamped copy)
- Validate migrations ("is at head?")
- Run integrity tests (basing/schema) and show pass/fail summary
- Load vocab (dry‑run):
  - 40K/AoS/Heresy units; Wargear; Bodies
- Apply vocab loads (confirm)
- Match variants to units (dry‑run) → save timestamped report
- Backfill english_tokens (dry‑run) → save report
- Sync franchise tokens to vocab (dry‑run/apply)
- Audit variant coverage → save report
- Cleanup utilities (dry‑run): remove __MACOSX duplicates, etc.
- Optimize DB (VACUUM/ANALYZE)

## 7) Admin/destructive tools (guard with confirms; optional admin mode)
- Delete variants (single/bulk)
- Repair orphan variants
- Remove loose files from variant
- Prune invalid variants
- Rebuild indexes

## 8) Diagnostics & tests (UI surface)
- Run all tests
- Run focused tests (e.g., codex basing integrity)
- Browse latest reports (timestamped JSON/summary)
- Download artifacts

## 9) Keyboard shortcuts (planned)
- Search: Ctrl/Cmd+F (in‑app)
- View: G (Grid), L (List)
- Refresh: R / F5
- Open Filters: F (tab focus)
- Sidecar: S
- Report mismatch: R (while item focused)

---

Notes
- "Scrollable selector" = a list with built‑in filter + keyboard nav, sized to ~10–14 rows with virtualized scrolling for long data.
- Place frequent actions in persistent toolbars; put rare/destructive in overflow/drawer.
- For discoverability, keep one visible primary action on cards/rows; move others to overflow (⋮).