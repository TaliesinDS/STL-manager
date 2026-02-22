# Frontend Rebuild Plan — STL Manager

**Date**: 2026-02-21
**Status**: Draft
**Scope**: Replace the monolithic HTML mockup with a maintainable React + TypeScript + Tailwind application that talks to the existing FastAPI backend.

---

## 1. Current State Assessment

### What exists

The entire UI lives in a single 3,185-line HTML file ([docs/ui/demo/workbench_layout_mock_4px_20major_48bar.html](docs/ui/demo/workbench_layout_mock_4px_20major_48bar.html)) containing:

- ~1,700 lines of CSS (inline `<style>`)
- ~900 lines of JavaScript (6 `<script>` blocks, all IIFEs)
- ~585 lines of HTML structure

Five older demo files sit alongside it; all are superseded. The `/assistant` feature is deprecated and excluded.

### What the mockup proves

The mockup has already validated the complete visual design language and interaction model:

| Aspect | Status | Notes |
|--------|--------|-------|
| **Layout** | Proven | Topbar + left drawer + workbench + right inspector |
| **Ornate theme** | Proven | 9-slice frames, ornate tabs, banner menus, breadcrumbs |
| **Domain navigation** | Proven | 8 domains (Tabletop, Display, D&D, Terrain, Scale, Other, Favorites, Bookmarks) |
| **Breadcrumb drilldown** | Proven | System → Faction → Subfaction with animated chip builder |
| **Filter drawer** | Proven | 5 tabs (Lineage, Base, NSFW, More, Saved), pin/unpin, resize |
| **Tools drawer** | Proven | Right-docked, 5 tabs (DB, Scan, Match, Backfill, Vocab) |
| **Inspector** | Proven | Name banner, preview, action squares, metadata grid, files, notes/license footer |
| **Banner dropdown menus** | Proven | Animated slide-in with scroll hints, scroll clamping, configurable gaps |
| **Bookmark system** | Proven | Save/delete/toggle bookmarks, hanging banner strip |
| **Grid/List toggle** | Proven | Cards view + table rows view + sidecar files panel |
| **Theme toggle** | Proven | Dark/light with full variable swap |
| **Responsive breakpoints** | Proven | Desktop (1800+), tablet (1200–1800), mobile (<1200) |

### Image assets (44 PNGs + 1 SVG)

All in `docs/ui/img/`. These will be copied as-is to `frontend/public/img/`. Key assets:

- **9-slice frames**: `9sFrame3.png`, `gold_frame_9slice.svg`
- **Topbar buttons**: `BtnTopbarActive.png`, `BtnTopbarInactive.png`
- **Tabs**: `Tab2.png`, `Tab2inactive.png`
- **Banners/ribbons**: `menubanner1.png`, `NameBannerRightBody.png`, `NameBannerRightPointing.png`, `namebannerdoublepoint2.png`, `NameBannerSmall.png`, `NameFrame.png`
- **Buttons**: `squarebuttonbg.png`, `rectanglebuttonbg.png`, `3button.png`, `greenroundbutton.png`
- **Icons**: `ArrowUp.png`, `ArrowDown.png`, `arrowright.png`, `Pushpin.png`, `PushpinLocked.png`, `CloseWindow.png`, `Bookmark1.png`, `bookmarksmall.png`
- **Inspector art**: `inspectorpreviewbg.png`, `inspectorpreviewdefault.png`, `pinupimg.png`, `Supportedbg.png`, `SegmentParts.png`, `SegmentWhole.png`
- **Scale icons**: `scale4.png`, `scale6.png`, `scale9.png`, `scale12.png`, `scaletbt.png`, `scaletrain.png`
- **Theme backgrounds**: `ComfyUI_14363_.png`, `ComfyUI_14835_.png`

---

## 2. Technology Choices

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Framework** | React 18+ | Already noted in vision docs; component model fits the inspector/drawer/workbench split |
| **Language** | TypeScript (strict) | Catch shape mismatches against API early; IDE support |
| **Styling** | Tailwind CSS 4 + CSS Modules for ornate theme | Utility-first for layout; CSS modules for the ornate 9-slice/banner system that needs custom properties |
| **Build tool** | Vite | Fast HMR, native ESM, tiny config, TS out of the box |
| **Routing** | React Router v7 (or TanStack Router) | URL-driven state for deep links, saved views |
| **State management** | Zustand (lightweight) | Small footprint, no boilerplate; app state is modest |
| **Data fetching** | TanStack Query (React Query) | Caching, deduplication, background refresh, pagination helpers |
| **Virtualization** | TanStack Virtual | For ledger/list view and long filter lists |
| **Icons** | Custom PNG/SVG assets | All graphical assets including icons are custom-made; no icon library |
| **Testing** | Vitest + React Testing Library + Playwright (E2E) | Vitest is Vite-native; RTL for components; Playwright for real browser |
| **Linting** | ESLint + Prettier + eslint-plugin-react-hooks | Standard React/TS linting |

### Not using (with rationale)

- **Phosphor / Heroicons / any icon library**: All icons and graphical assets are custom-made for the ornate theme. No generic icon packs.
- **Tauri/Electron**: Deferred for now. The UI is a standard web app first; desktop wrapping can be added later with no architecture changes.
- **Redux**: Overkill for the state complexity here. Zustand covers it.
- **Sass/Less**: Tailwind + CSS Modules covers 100% of needs without a preprocessor.
- **Next.js/Remix**: This is a local-first single-page app, not a server-rendered website.

---

## 3. Folder Structure

```
frontend/
├── index.html                          # Vite entry point
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── vite.config.ts
├── .eslintrc.cjs
├── .prettierrc
│
├── public/
│   └── img/                            # Copied from docs/ui/img/ (all 45 assets)
│       ├── 9sFrame3.png
│       ├── BtnTopbarActive.png
│       ├── ...
│       └── Tab2inactive.png
│
├── src/
│   ├── main.tsx                        # React root + providers
│   ├── App.tsx                         # Router + shell layout
│   ├── vite-env.d.ts
│   │
│   ├── api/                            # API client layer
│   │   ├── client.ts                   # Axios/fetch wrapper, base URL, error handling
│   │   ├── variants.ts                 # getVariants(), getVariant(id), searchVariants()
│   │   ├── units.ts                    # getUnits(), getUnit(id) (future)
│   │   ├── mismatch.ts                 # reportMismatch(), getMismatches() (future)
│   │   └── types.ts                    # API response types (mirrors Pydantic models)
│   │
│   ├── stores/                         # Zustand stores
│   │   ├── domainStore.ts              # Active domain, system, faction, subfaction
│   │   ├── filterStore.ts              # Drawer filter state (lineage, base, NSFW, etc.)
│   │   ├── viewStore.ts                # Grid/list mode, sidecar open, sort order
│   │   ├── selectionStore.ts           # Selected variant(s), multi-select
│   │   ├── bookmarkStore.ts            # Saved bookmarks (localStorage-backed)
│   │   └── themeStore.ts               # Dark/light theme
│   │
│   ├── hooks/                          # Custom React hooks
│   │   ├── useVariants.ts              # TanStack Query wrapper for variant list
│   │   ├── useVariant.ts               # TanStack Query wrapper for variant detail
│   │   ├── useKeyboard.ts              # Global keyboard shortcut handler
│   │   ├── useBreakpoint.ts            # Responsive breakpoint detection
│   │   └── useScrollHints.ts           # Scroll-hint arrow visibility logic
│   │
│   ├── theme/                          # Ornate theme system
│   │   ├── tokens.css                  # CSS custom properties (from :root in mockup)
│   │   ├── ornate.module.css           # 9-slice frames, banner menus, tab art
│   │   ├── light.css                   # Light theme overrides
│   │   ├── typography.css              # Cinzel/Inter font imports, heading styles
│   │   └── animations.css              # Slide-in, banner glide, chip transitions
│   │
│   ├── components/                     # Reusable UI building blocks
│   │   ├── Frame/
│   │   │   ├── Frame.tsx               # Ornate 9-slice frame wrapper
│   │   │   └── Frame.module.css
│   │   ├── Button/
│   │   │   ├── Button.tsx              # Generic button (framed, ghost, icon variants)
│   │   │   ├── SquareButton.tsx        # Inspector square action button (NSFW, Scale, etc.)
│   │   │   └── RectButton.tsx          # Inspector rectangle action button (Favorite, Report)
│   │   ├── Badge/
│   │   │   └── Badge.tsx               # Chip/badge/pill component
│   │   ├── ScrollHints/
│   │   │   └── ScrollHints.tsx         # Arrow overlay for scrollable containers
│   │   ├── BannerMenu/
│   │   │   ├── BannerMenu.tsx          # Animated dropdown with banner skin
│   │   │   └── BannerMenu.module.css
│   │   ├── Chip/
│   │   │   └── Chip.tsx                # Filter chip / breadcrumb segment
│   │   ├── SearchBox/
│   │   │   └── SearchBox.tsx           # Framed search input
│   │   └── CollectionList/
│   │       └── CollectionList.tsx       # Selectable list (used in Saved panel)
│   │
│   ├── layout/                         # Shell layout components
│   │   ├── Shell.tsx                   # Top-level layout: topbar + app grid
│   │   ├── Topbar/
│   │   │   ├── Topbar.tsx              # Meta card + domain bar + search + theme
│   │   │   ├── DomainBar.tsx           # Row-1 domain buttons with active art
│   │   │   ├── BreadcrumbRow.tsx       # Row-2 breadcrumb chip + bookmark strip
│   │   │   ├── BookmarkStrip.tsx       # Hanging bookmark banners
│   │   │   └── Topbar.module.css
│   │   ├── Drawer/
│   │   │   ├── Drawer.tsx              # Generic sliding drawer (left or right)
│   │   │   ├── DrawerTabs.tsx          # Dual-layer tab sidebar (visual + hit)
│   │   │   ├── FilterDrawer.tsx        # Left drawer: Lineage/Base/NSFW/More/Saved panels
│   │   │   ├── ToolsDrawer.tsx         # Right drawer: DB/Scan/Match/Backfill/Vocab panels
│   │   │   ├── panels/
│   │   │   │   ├── LineagePanel.tsx
│   │   │   │   ├── BasePanel.tsx
│   │   │   │   ├── NsfwPanel.tsx
│   │   │   │   ├── MorePanel.tsx
│   │   │   │   ├── SavedPanel.tsx
│   │   │   │   ├── ToolsDbPanel.tsx
│   │   │   │   ├── ToolsScanPanel.tsx
│   │   │   │   ├── ToolsMatchPanel.tsx
│   │   │   │   ├── ToolsBackfillPanel.tsx
│   │   │   │   └── ToolsVocabPanel.tsx
│   │   │   └── Drawer.module.css
│   │   └── AmbientInfo.tsx             # Background workspace stats panel
│   │
│   ├── features/                       # Feature-level composed views
│   │   ├── workbench/
│   │   │   ├── Workbench.tsx           # Toolbar + cards/rows + sidecar container
│   │   │   ├── WorkbenchToolbar.tsx    # Grid/List toggle, sidecar, sort, refresh
│   │   │   ├── CardGrid.tsx            # Strategy view: grid of variant cards
│   │   │   ├── VariantCard.tsx         # Individual card with badges, actions
│   │   │   ├── RowList.tsx             # Ledger view: virtualized table rows
│   │   │   ├── VariantRow.tsx          # Individual table row
│   │   │   ├── Sidecar.tsx             # Files sidecar panel
│   │   │   └── Workbench.module.css
│   │   ├── inspector/
│   │   │   ├── Inspector.tsx           # Right-side detail panel
│   │   │   ├── InspectorName.tsx       # Name banner box
│   │   │   ├── InspectorPreview.tsx    # Preview with arrow overlays + 3-button rail
│   │   │   ├── InspectorMidGrid.tsx    # Side columns (NSFW, Scale, Support, Segment)
│   │   │   ├── InspectorMetaGrid.tsx   # 6 metadata boxes
│   │   │   ├── InspectorFiles.tsx      # Files inventory box
│   │   │   ├── InspectorFooter.tsx     # Notes + license footer
│   │   │   └── Inspector.module.css
│   │   └── mismatch/
│   │       ├── MismatchForm.tsx        # Report mismatch modal/drawer
│   │       └── MismatchInbox.tsx       # Admin inbox (future)
│   │
│   ├── pages/                          # Route-level page components
│   │   ├── WorkbenchPage.tsx           # Main view: workbench + inspector
│   │   ├── DashboardPage.tsx           # KPI dashboard (future)
│   │   └── AdminPage.tsx               # Mismatch inbox + tools (future)
│   │
│   └── utils/                          # Pure utility functions
│       ├── cn.ts                       # clsx/twMerge className helper
│       ├── formatters.ts               # Date, file size, display name formatters
│       ├── url.ts                      # URL state sync helpers
│       └── constants.ts                # Domain/system/faction data, sort options
```

---

## 4. Component Decomposition

The monolithic HTML maps to these React components, grouped by responsibility:

### Shell (always rendered)

```
<Shell>
  <Topbar>
    <MetaCard />                 ← App title + DB info
    <DomainBar />                ← 8 domain buttons (Tabletop, Display, ...)
    <SearchBox />                ← Global framed search
    <ThemeToggle />              ← Dark/light switch
    <BreadcrumbRow>
      <BreadcrumbChip />         ← System → Faction → Subfaction drill
      <BookmarkStrip />          ← Hanging bookmark banners
    </BreadcrumbRow>
    <BannerMenu />               ← Animated dropdown for domain/crumb menus
  </Topbar>

  <FilterDrawer>                 ← Left-docked, uses <Drawer> base
    <DrawerTabs />               ← Lineage | Base | NSFW | More | Saved
    <LineagePanel />
    <BasePanel />
    <NsfwPanel />
    <MorePanel />
    <SavedPanel />
  </FilterDrawer>

  <AmbientInfo />                ← Background workspace stats

  <AppGrid>
    <Workbench />                ← Main content area
    <Inspector />                ← Right detail panel
  </AppGrid>

  <ToolsDrawer>                  ← Right-docked
    <DrawerTabs />               ← DB | Scan | Match | Backfill | Vocab
    ...panels...
  </ToolsDrawer>
</Shell>
```

### Workbench (center column)

```
<Workbench>
  <WorkbenchToolbar>
    <ViewToggle />               ← Grid / List
    <SidecarToggle />
    <SortBadge />
    <RefreshButton />
  </WorkbenchToolbar>

  <WorkbenchInner>
    <!-- Grid mode -->
    <CardGrid>
      <VariantCard />            ← Ornate frame card
      <VariantCard />
      ...
    </CardGrid>

    <!-- OR List mode -->
    <RowList>                    ← Virtualized via TanStack Virtual
      <VariantRow />
      ...
    </RowList>

    <!-- Optional sidecar -->
    <Sidecar>
      <FileEntry />
      ...
    </Sidecar>
  </WorkbenchInner>
</Workbench>
```

### Inspector (right column)

```
<Inspector>
  <Frame>
    <InspectorName />            ← Banner overlay with variant name
    <InspectorMidGrid>
      <SquareButton type="nsfw" />
      <SquareButton type="scale" />
      <RectButton type="favorite" />
      <InspectorPreview />       ← Tall preview with arrow overlays
      <SquareButton type="support" />
      <SquareButton type="segmented" />
      <RectButton type="report" />
    </InspectorMidGrid>
    <InspectorMetaGrid />        ← 6 metadata boxes (system, factions, unit, designer, collection)
    <InspectorFiles />           ← Files list with grid background
  </Frame>
  <InspectorFooter>
    <NotesBox />                 ← Textarea + checklist (printed/prepped/primed/painted)
    <LicenseInline />            ← Link + owner
  </InspectorFooter>
</Inspector>
```

---

## 5. State Architecture

### Zustand Stores

```
domainStore
  ├── domain: string              # "wargames" | "display" | "dnd" | "terrain" | "scale" | "unsorted" | "savedcollections" | "bookmarks"
  ├── system: string | null       # e.g., "w40k", "aos"
  ├── faction: string | null      # e.g., "Space Marines"
  ├── subfaction: string | null   # e.g., "Dark Angels"
  └── actions: setDomain(), setSystem(), setFaction(), setSubfaction(), reset()

filterStore
  ├── lineages: string[]          # Selected lineage families
  ├── baseProfiles: string[]      # Selected base sizes
  ├── nsfwMode: "hide" | "blur" | "show"
  ├── moreFilters: Record<string, boolean>
  ├── savedFilters: Record<string, boolean>
  ├── searchQuery: string
  └── actions: setLineages(), toggleBase(), setNsfwMode(), clearAll(), applyCount()

viewStore
  ├── mode: "grid" | "list"
  ├── sidecarOpen: boolean
  ├── sortBy: "updated" | "name" | "designer" | "confidence"
  ├── sortDir: "asc" | "desc"
  └── actions: toggleMode(), toggleSidecar(), setSort()

selectionStore
  ├── selectedIds: Set<number>
  ├── focusedId: number | null    # Inspector shows this variant
  └── actions: select(), toggleSelect(), clearSelection(), setFocused()

bookmarkStore                     # Persisted to localStorage
  ├── bookmarks: Array<{ id: string, label: string, checked: boolean }>
  └── actions: add(), remove(), toggle(), load(), save()

themeStore                        # Persisted to localStorage
  ├── theme: "dark" | "light"
  └── actions: toggle()
```

### URL State Sync

The following state is synced to URL query parameters so views are shareable/bookmarkable:

```
?domain=wargames&system=w40k&faction=Space+Marines&subfaction=Dark+Angels
&q=infernus
&view=grid
&sort=updated
&lineage=undead,demons
&nsfw=hide
```

This is implemented via React Router's `useSearchParams()` and synced on navigation.

---

## 6. API Integration

### Current API Surface (implemented in `api/main.py`)

| Endpoint | Method | Status |
|----------|--------|--------|
| `/health` | GET | Implemented |
| `/variants` | GET | Implemented — paginated with `q`, `system`, `faction`, `limit`, `offset` |
| `/variants/{id}` | GET | Implemented — includes files |

### API Extensions Needed for MVP

The existing 3 endpoints cover the core data flow. These additions are recommended for MVP:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/variants` | GET | **Extend**: Add `designer`, `lineage_family`, `base_size_mm`, `sort_by`, `sort_dir` filter params |
| `/facets` | GET | Return distinct values for filter dropdowns: systems, factions, designers, lineages, base sizes |
| `/variants/{id}/mismatch` | POST | Accept mismatch report (variant_id, fields, comment) |

### TanStack Query Integration

```typescript
// hooks/useVariants.ts
export function useVariants() {
  const filters = useFilterStore();
  const domain = useDomainStore();

  return useQuery({
    queryKey: ['variants', domain, filters],
    queryFn: () => api.getVariants({
      q: filters.searchQuery,
      system: domain.system,
      faction: domain.subfaction || domain.faction,
      limit: 50,
      offset: 0,
    }),
    staleTime: 30_000,
  });
}
```

---

## 7. CSS Architecture

### Approach: Tailwind + CSS Modules for ornate theme

The mockup's CSS falls into two distinct categories:

1. **Layout + responsive** (~40% of CSS): Straightforward flex/grid/spacing → **Tailwind utility classes**.
2. **Ornate visual theme** (~60% of CSS): 9-slice borders, pseudo-element overlays, banner skins, tab art → **CSS Modules** with custom properties.

### CSS Custom Properties (extracted from mockup `:root`)

All ~80 CSS variables from the mockup's `:root` will live in `src/theme/tokens.css`, organized by category:

```css
/* src/theme/tokens.css */

/* === Spacing & Grid === */
--frame-border: 18px;
--grid-u: 4px;
--grid-major: 5;
--bar-row-h: 48px;
/* ... etc ... */

/* === Colors (Dark) === */
--bg-0: #0b0a07;
--bg-1: #0f0e0a;
--ink: #0c0a05;
--text: #e8e4d8;
--muted: #bdb7a5;
--accent: #d8b85a;
/* ... etc ... */

/* === Assets === */
--topbtn-img-inactive: url('/img/BtnTopbarInactive.png');
--topbtn-img-active: url('/img/BtnTopbarActive.png');
--tab-img-inactive: url('/img/Tab2inactive.png');
--tab-img-active: url('/img/Tab2.png');
/* ... etc ... */
```

### Light Theme

Light theme overrides from the mockup (`[data-theme="light"]`) will live in `src/theme/light.css`, applied via `data-theme` attribute on `<html>`.

### Key CSS Patterns to Extract

| Pattern | Mockup Location | Target Module |
|---------|----------------|---------------|
| `.frame` (9-slice border) | Lines 89–100 | `Frame.module.css` |
| `.btn9` (framed buttons) | Lines 128–148 | `Button.module.css` |
| `.banner-menu` (animated dropdown) | Lines 188–260 | `BannerMenu.module.css` |
| `.drawer` / `.drawer-tab` | Lines 610–750 | `Drawer.module.css` |
| `.inspector` / `.ibox` | Lines 440–600 | `Inspector.module.css` |
| `.row-crumb .chip` (breadcrumb) | Lines 263–330 | `Topbar.module.css` |
| Topbar button skins (`::after`) | Lines 155–178 | `Topbar.module.css` |
| Inspector squares (NSFW/Scale/Support/Segment overlays) | Lines 500–590 | `Inspector.module.css` |

---

## 8. Implementation Phases

### Phase 1: Scaffold + Shell (Foundation)

**Goal**: Empty app running with router, providers, layout skeleton, and theme system.

- [ ] Initialize Vite + React + TypeScript project in `frontend/`
- [ ] Install dependencies: Tailwind, React Router, Zustand, TanStack Query, Phosphor Icons
- [ ] Copy image assets from `docs/ui/img/` to `frontend/public/img/`
- [ ] Extract CSS custom properties into `src/theme/tokens.css`
- [ ] Build `<Frame>` component (9-slice ornate frame — the foundational visual element)
- [ ] Build `<Shell>` with app grid layout (topbar area + workbench column + inspector column)
- [ ] Build `<Topbar>` with static domain buttons (no interaction yet)
- [ ] Implement dark/light theme toggle (themeStore + `data-theme` attribute)
- [ ] Verify responsive breakpoints (desktop/tablet/mobile)

**Exit criteria**: App renders the ornate shell layout at all 3 breakpoints with dark/light theme switching.

### Phase 2: Domain Navigation + Breadcrumbs

**Goal**: Domain selection, system drilldown, and breadcrumb navigation working with animated banner menus.

- [ ] Build `<DomainBar>` with active button art (`::after` overhang pattern)
- [ ] Build `<BannerMenu>` with slide animation, scroll hints, and configurable gaps
- [ ] Build `<BreadcrumbRow>` with chip builder (System → Faction → Subfaction)
- [ ] Wire `domainStore` to URL params
- [ ] Build `<BookmarkStrip>` with localStorage persistence (bookmarkStore)
- [ ] Implement `<BtnOverhang>` overlay for active domain button

**Exit criteria**: Can select domain, drill into system/faction/subfaction, create/delete bookmarks, and see banner menus animate.

### Phase 3: Workbench + Data

**Goal**: Variant cards/list fetched from real API and displayed in grid and list views.

- [ ] Build API client (`src/api/client.ts`, `src/api/variants.ts`)
- [ ] Build `useVariants()` hook with TanStack Query
- [ ] Build `<Workbench>` with toolbar (grid/list toggle, sort badge, refresh)
- [ ] Build `<VariantCard>` in ornate frame
- [ ] Build `<RowList>` with TanStack Virtual for virtualized scrolling
- [ ] Build `<VariantRow>` with gold-separator table styling
- [ ] Build `<Sidecar>` files panel with toggle
- [ ] Build `<SearchBox>` with debounced API calls (filterStore)
- [ ] Wire sort order to API params

**Exit criteria**: Real variant data loads from the FastAPI backend, renders in both grid and list views, search works, pagination loads.

### Phase 4: Inspector

**Goal**: Clicking a variant shows its details in the inspector panel.

- [ ] Build `<Inspector>` with fixed viewport positioning (matching mockup behavior)
- [ ] Build `<InspectorName>` with banner overlay art
- [ ] Build `<InspectorPreview>` with 3-button rail and arrow overlays
- [ ] Build `<InspectorMidGrid>` with `<SquareButton>` variants (NSFW, Scale, Support, Segmented)
- [ ] Build `<InspectorMetaGrid>` (6 metadata boxes)
- [ ] Build `<InspectorFiles>` with grid background
- [ ] Build `<InspectorFooter>` (Notes textarea + checklist + license inline)
- [ ] Wire `selectionStore.focusedId` → `useVariant(id)` → inspector display
- [ ] Build API endpoint: extend `/variants/{id}` response with all needed fields

**Exit criteria**: Clicking a variant card/row populates the inspector with real data from the API.

### Phase 5: Filter Drawer

**Goal**: Left-docked filter drawer with all 5 panels operational.

- [ ] Build generic `<Drawer>` component (slide-in, backdrop, pin, resize, close)
- [ ] Build `<DrawerTabs>` with dual-layer tab pattern (visual + hit)
- [ ] Build `<FilterDrawer>` with 5 panels:
  - `<LineagePanel>` — searchable checkbox list
  - `<BasePanel>` — base size checkboxes (moved to More)
  - `<NsfwPanel>` — radio group (hide/blur/show)
  - `<MorePanel>` — support, segmentation, multi-part, base profiles
  - `<SavedPanel>` — collections list, workflow checkboxes, notes search
- [ ] Wire filter state to API queries
- [ ] Implement Apply/Clear with badge counts on tabs
- [ ] Add `/facets` API endpoint for dynamic filter values

**Exit criteria**: Filters modify the workbench results; badge counts reflect active filters; drawer pins, resizes, and animates correctly.

### Phase 6: Tools Drawer + Polish

**Goal**: Right-docked tools drawer, keyboard shortcuts, and visual polish.

- [ ] Build `<ToolsDrawer>` with 5 panels (DB, Scan, Match, Backfill, Vocab)
- [ ] Implement mutual exclusion (opening one drawer closes the other)
- [ ] Add mismatch report form (modal or inline)
- [ ] Implement keyboard shortcuts (`/` search, `G` grid/list, `I` inspector, `Esc` close)
- [ ] Add `<AmbientInfo>` panel
- [ ] Add loading skeletons for cards and inspector
- [ ] Add error states and empty states
- [ ] Implement debug grid overlay (dev-only, toggle with `G`)
- [ ] Final responsive testing and polish

**Exit criteria**: Full feature parity with the HTML mockup, running against real API data.

---

## 9. Backend Changes Required

### Immediate (for MVP)

1. **Extend `GET /variants`**: Add filter params: `designer`, `lineage_family`, `base_size_mm`, `sort_by`, `sort_dir`.

2. **Add `GET /facets`**: Return distinct values for filter dropdowns:
   ```json
   {
     "game_systems": ["w40k", "aos", "heresy"],
     "factions": ["Space Marines", "Necrons", ...],
     "designers": ["ghamak", "dm_stash", ...],
     "lineage_families": ["undead", "demons", ...],
     "base_sizes": [25, 28, 32, 40, 50, ...]
   }
   ```

3. **Add `POST /variants/{id}/mismatch`**: Accept mismatch reports.

4. **CORS**: Already configured (`allow_origins=["*"]`). Tighten to `localhost:5173` (Vite dev server) for development.

### Later (post-MVP)

- Full API spec implementation (see `docs/API_SPEC.md`)
- Unit/parts/linking endpoints
- Bulk operations
- Admin/job endpoints for tools drawer

---

## 10. Migration from Mockup

### What to preserve verbatim

- All 45 image assets (copy directory)
- All CSS custom properties (extract from `:root`)
- All ornate CSS patterns (9-slice, banner skins, tab art, button overlays) → CSS modules
- Light theme variable overrides
- Responsive breakpoints and media queries
- Animation timings (`.22s cubic-bezier(.2,.8,.2,1)`)
- ARIA roles, labels, and keyboard patterns
- Domain/system data structure (`SYSTEMS` object in JS)
- Banner menu sizing algorithm (scroll clamping, gap configuration)

### What to discard

- All IIFE script blocks → replaced by React components + stores
- Inline DOM manipulation (`innerHTML = ...`) → replaced by React rendering
- `localStorage` direct access in IIFEs → replaced by Zustand persist middleware
- Duplicate drawer wiring (Filters and Tools are near-identical code) → single `<Drawer>` component
- Debug grid overlay controls (keep as dev-only utility, simplify)
- `docs/ui/demo/` older mockup files (archive or delete after migration)
- `docs/ui/assistant/` directory (deprecated feature, excluded)

### What to refactor

- Banner menu JS (120+ lines of sizing/positioning) → `useBannerMenu()` hook with ResizeObserver
- Breadcrumb state machine (segment builder) → `useBreadcrumb()` hook driven by `domainStore`
- Inspector positioning (manual `getBoundingClientRect` sync) → `position: fixed` with CSS custom properties for bounds, synced via `ResizeObserver` hook
- Inline `fetch()` calls → TanStack Query with proper caching

---

## 11. Testing Strategy

| Layer | Tool | Coverage Target |
|-------|------|----------------|
| Unit (components) | Vitest + RTL | Frame, Button, Badge, SearchBox, Chip — render & props |
| Unit (stores) | Vitest | All Zustand stores — state transitions |
| Unit (hooks) | Vitest + RTL renderHook | useVariants, useKeyboard, useScrollHints |
| Integration | Vitest + RTL | Workbench with mocked API, FilterDrawer panel interactions |
| E2E | Playwright | Happy paths: search, filter, select variant, view inspector, toggle theme |
| Visual regression | Playwright screenshots | Ornate theme consistency across dark/light |

---

## 12. Files to Clean Up After Migration

Once the React frontend is stable and replaces the mockup:

| Path | Action |
|------|--------|
| `docs/ui/demo/bg_parquet_oak_test.html` | Delete |
| `docs/ui/demo/front_page_mock.html` | Delete |
| `docs/ui/demo/ornate_frame_demo.html` | Archive (CSS reference) or delete |
| `docs/ui/demo/workbench_layout_mock.html` | Delete |
| `docs/ui/demo/workbench_nav_patterns_demo.html` | Delete |
| `docs/ui/demo/workbench_layout_mock_4px_20major_48bar.html` | Archive → `docs/ui/archive/` |
| `docs/ui/assistant/` | Delete (deprecated feature) |

The design docs (`UI_Vision.md`, `UI_Layout.md`, `UI_Elements_Spec.md`, `UI_Styling_OrnateFrames.md`, `UI_Action_Catalog.md`, `UI_Action_Matrix.md`, `ASSETS_SPEC.md`) remain as living documentation.

---

## 13. Decisions Log

| # | Question | Decision |
|---|----------|----------|
| 1 | Package manager | TBD — will evaluate `pnpm` vs `npm` at scaffold time |
| 2 | Desktop wrapper (Tauri) | Deferred — build as web app first; add Tauri later if needed |
| 3 | Font hosting | TBD — will decide at scaffold time (bundle locally vs CDN) |
| 4 | Inspector position | **Fixed** — viewport-fixed overlay, matching the mockup. Not a grid column. |
| 5 | Monorepo | **Yes** — `frontend/` lives inside the existing `STL-manager` repo |
| 6 | Icon library | **None** — all graphical assets including icons are custom-made for the ornate theme |
| 7 | Page scrolling | **App/game UI model** — the page itself never scrolls; only the workbench content area scrolls internally. `<html>` and `<body>` are `overflow: hidden`. |

---

*Plan created 2026-02-21. UI mockup (`docs/ui/demo/`) and design docs (`docs/ui/`) are the authoritative visual reference throughout implementation.*
