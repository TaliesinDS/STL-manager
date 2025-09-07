# STL Manager UI — Action Matrix and Step Budgets

This document standardizes how we decide what needs a button, where it lives, and how many steps it should take to reach. It’s lightweight, repeatable, and grounded in common UX practices.

## Workflow (repeatable loop)
1) Action inventory: list all actions as verb + object (+ context).
2) Wireflows: sketch the shortest path for frequent actions and count steps.
3) Control placement: map each action to control type and location.
4) Step budgets: enforce max steps per action class (primary/secondary/rare).
5) Heuristics + effort: quick pass with Nielsen’s 10; sanity-check time/effort with KLM/Fitts/Hick when needed.

## Scoring rubric
Use these columns in the matrix to prioritize and place controls:
- Frequency: High | Medium | Low
- Importance/Impact: High | Medium | Low (user value + task criticality)
- Risk: None | Undo | Confirm | Destructive
- Scope: Global | Item | Bulk (multi-select)
- Discoverability: Must be visible | Okay in overflow | Hidden is okay (expert)

## Step budgets (targets)
- Primary, frequent: 1–2 steps, no scroll, in-viewport, keyboard reachable.
- Secondary: ≤3 steps, discoverable via toolbar or overflow.
- Rare/advanced: 3–5 steps; put in drawer/overflow; allow search/command-palette later.
- Power-user path: provide a faster route (shortcut, context menu) when feasible.

## Placement guidance (quick rules)
- Global/multi-select actions → Workbench toolbar (persistent).
- Item-specific actions → On card/row (primary visible; secondary in overflow “⋮”).
- Binary setting → Toggle/switch; one-off command → Button.
- Rare/destructive → Overflow + confirm; provide undo if possible.
- Direct manipulation (e.g., click a pill to toggle) is ideal when affordance is clear and safe.

---

## Current UI — Pre-filled Action Matrix
These reflect controls visible in `docs/ui/demo/workbench_layout_mock_4px_20major_48bar.html` and intended behaviors.

| Action | Object | Scope | Frequency | Risk | Placement | Control | Step budget | Shortcut |
|---|---|---|---|---|---|---|---|---|
| Search results | results | Global | High | None | Top bar | Search field | 1–2 | Ctrl/Cmd+F (app) |
| Toggle theme | app | Global | Medium | None | Top bar | Toggle | 1 | T |
| Select domain | dataset scope | Global | High | None | Top bar (row 1) | Segmented buttons | 1 | 1–5 keys |
| Select system | dataset scope | Global | High | None | Top bar (row 2) | Segmented buttons | 1 | 6–0 keys |
| Refresh results | results | Global | Medium | None | Workbench toolbar | Button | 1–2 | F5 / R |
| Toggle grid/list | view mode | Global | High | None | Workbench toolbar | Segmented buttons | 1 | G / L |
| Toggle sidecar | sidecar panel | Global | Medium | None | Workbench toolbar | Button | 1 | S |
| Change sort | results | Global | Medium | None | Workbench toolbar | Menu/segmented | ≤2 | Alt+S |
| Open filters drawer | filters | Global | High | None | Drawer tabs (left/right) | Tab button | 1 | F |
| Apply filters | filters | Global | High | None | Drawer footer | Button | ≤2 | Enter |
| Clear filters | filters | Global | Medium | None | Drawer footer | Button | ≤2 | Shift+Del |
| Pin drawer | drawer | Global | Low | None | Drawer header | Toggle | 1 | P |
| Report mismatch | variant | Item | Medium | Undo/Confirm | Card/row primary | Button | 1–2 | R |
| Open preview/details | variant | Item | Medium | None | Card/row | Button/link | 1 | Enter |
| Overflow actions (open in folder, queue/export) | variant | Item | Low/Medium | Varies | Card/row overflow | Menu | ≤3 | Context menu |
| Delete variant | variant | Item/Bulk | Low | Confirm | Overflow | Menu + confirm | ≤3 | Del |

Notes:
- “Shortcut” suggestions are placeholders; we’ll finalize once we implement a command palette or keyboard map.
- Bulk actions (e.g., assign base, tag) will appear in the workbench toolbar when selection is active.

---

## Checklist — Primary flows must be ≤ 2 steps
- Change domain/system: directly clickable (1 step); keyboard nav possible.
- Search: focus search (1), type (2). Keep always visible.
- Toggle grid/list: single click or key.
- Open filters: click tab (1); apply (2). If already open/pinned, apply in 1.
- Report mismatch: visible on card/row or on hover/focus; reachable in 1–2.
- Refresh: single click or F5/R.

## Heuristic pass (Nielsen’s 10, condensed)
- Visibility: show active domain/system, filter counts on tabs, sort state.
- Match: labels use domain language (e.g., “Heresy”, “Base profile”).
- Control & freedom: undo/restore for destructive edits; visible Clear/Apply; ESC closes drawer.
- Consistency: buttons, segment toggles, overflow menus behave the same across views.
- Error prevention: confirms for delete; context-aware actions only where valid.
- Recognition over recall: put frequent actions in persistent toolbars; show tooltips.

## Effort sanity checks
- Fitts’s law: large click targets in top/toolbar; adequate spacing.
- Hick’s law: keep segmented choices short; put extras in overflow.
- KLM (rough): primary actions should average under ~1.5–2.0s with mouse; power path faster with shortcuts.

---

## Reusable Action Matrix Template
Paste this table for new features. Keep it in this file or create a per-feature copy.

| Action | Object | Scope (Global/Item/Bulk) | Frequency (H/M/L) | Importance (H/M/L) | Risk (None/Undo/Confirm) | Placement (Topbar/Toolbar/Card/Overflow/Drawer) | Control (Button/Toggle/Menu/Context) | Step budget (1–2/≤3/≤5) | Shortcut |
|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |  |

### Example row syntax
- Assign base profile | selection | Bulk | M | H | Undo | Toolbar/Drawer | Button + Drawer | ≤3 | —

---

## How to use this doc
- When adding a new control, add a row to the matrix and check step budget and placement.
- For frequent tasks creeping past 2 steps, either promote to toolbar or add a shortcut.
- Re-run the Checklist and Heuristic pass after UI changes.

## Next steps
- Wire keyboard shortcuts to the mock and add a “?” help panel listing them.
- Add a simple command palette later (Ctrl/Cmd+K) for power users.
