# Proposal: Tokenization + Entity Linking Enhancements and Vocab Strategy

Status: Draft for review
Owner: STL Manager
Date: 2025-08-25

## Objectives
- Improve recognition of full names and glued/camelCase tokens (e.g., `RyukoMatoi`, `multiplewordstogetherlikethis`).
- Reduce false positives from ambiguous single-word aliases (e.g., `angel`).
- Keep franchise vs tabletop strictly separated; avoid assigning franchises in terrain/scenery contexts.
- Outline a pragmatic path for vocab management now and for a future GUI.
- Allow optional, low-cost enrichment (Wikidata, small local models) without making them core.

## Scope (Phase 1)
- Tokenizer upgrades (read-only behavior change; no schema changes needed).
- Matcher guardrails (alias ambiguity, tabletop gating).
- Keep file-based vocab as source of truth; DB as runtime index/cache.
- No GUI coding yet; define integration points.

## Proposed Changes

### 1) Tokenization Enhancements
Add pre-matching expansions so the matcher can see more realistic mentions:
- Mixed-case/alpha–digit splitting: split `RyukoMatoiV2` → `ryuko`, `matoi`, `v2`.
- Bigrams (adjacent two-token n-grams): from base tokens create `ryuko matoi`, `ryuko_matoi`, and `ryukomatoi` forms for alias matching.
- Optional vocab-driven segmentation for glued lowercase tokens: greedy longest-prefix split using known aliases/tokens (only when candidates exist) to handle `multiplewordstogether`.

Implementation notes:
- Wire regex-based splitting into `scripts/quick_scan.tokenize` (shared behavior) and/or generate expansions within the matcher right before comparing to vocab.
- Keep expansions bounded: only adjacent bigrams by default; trigrams can be added later if needed.

### 2) Matcher Guardrails (already partially implemented)
- Ambiguous aliases list: treat tokens like `angel` as ambiguous. They do not count as alias evidence and are ignored unless there is independent franchise evidence for the same franchise. This prevents terrain décor like “angel” from linking to KOF’s Angel.
- Short/numeric alias suppression: keep existing rule (e.g., `002`, `2b`) requiring independent franchise evidence.
- Tabletop/terrain gating: consider items with terrain/scenery hints (“terrain”, “scenery”, “base”, plus newly added `church`, `decor`) as tabletop context; do not auto-assign franchises unless strong counter-evidence exists.

### 3) Vocab Strategy (Hybrid)
- Continue authoring vocab in `vocab/` JSON/Markdown (Git-reviewed source of truth).
- Sync into normalized DB tables at runtime for fast lookups and to enforce constraints (unique alias, FK franchise→character). Maintain `vocab_version` and per-file `content_hash` to enable idempotent sync and drift detection.
- Optional: add a minimal admin endpoint or CLI to dump current DB vocab back to files (“Publish”), preserving Git review.

### 4) GUI Integration Path (Future)
- Phase A (read-only): browse/search vocab from DB, list collisions, and diff against files.
- Phase B (edit): CRUD with constraints (unique alias, strength flags), plus “Publish to files” (PR or commit).
- Phase C (workflow): draft/review states, batch edits, changelog, and audit trail.

### 5) Optional Enrichment (Non-core)
- Wikidata/Wikipedia: store `wikidata_qid` per franchise/character; periodically fetch additional labels/aliases and cache locally as suggestions. Do not auto-apply.
- Fuzzy/phonetic helpers: `rapidfuzz`, `unidecode`, `jellyfish` for tolerant matching behind thresholds, still gated by franchise evidence.
- Small local embeddings (optional): a tiny `sentence-transformers` model with `sqlite-vec`/FAISS for “sounds like” suggestions only.
- spaCy KB (optional): create a small KnowledgeBase from entities+aliases and use rule-driven linking; no heavy models required.

## Data Model (DB)
Minimal tables if/when syncing vocab to DB:
- `franchise(id, key, display_name, wikidata_qid, ...)`
- `franchise_alias(franchise_id, alias, strength)` with unique(alias)
- `character(id, franchise_id, canonical, wikidata_qid, ...)` FK→franchise
- `character_alias(character_id, alias, strength)` with unique(alias)
- `franchise_token(franchise_id, token, kind)` where kind ∈ {strong, weak}
- `vocab_meta(source, version, content_hash, updated_at)` for sync bookkeeping

## Rollout Plan
1) Implement tokenizer expansions (split mixed-case/digits, bigrams) behind a feature flag or as part of matcher-only expansion to limit global impact initially.
2) Keep ambiguous-alias handling (current: includes `angel`) and tabletop gating (`church`, `decor` added) in place.
3) Dry-run the matcher, export JSON report, and spot-check a handful of known cases for regressions and improved recall.
4) If positive, enable expansions in the shared tokenizer so downstream scans benefit consistently.

## Testing & Validation
- Unit tests for splitting: `RyukoMatoiV2` → ["ryuko","matoi","v2"], `multiplewordstogether` → segmented when vocabulary supports it.
- Matcher tests: ensure ambiguous `angel` in terrain context yields no franchise/character; full names (e.g., `ryuko matoi`) resolve when franchise evidence exists.
- Smoke tests: run `match_franchise_characters.py --out` and compare counts (top franchises/characters) before/after.
- DB verification: confirm specific Variant IDs retain/receive correct franchise/character assignments.

## Edge Cases & Safeguards
- Avoid creating n-grams across stopwords; filter out stopwords before bigram generation.
- Don’t over-segment glued tokens unless there is vocab support; otherwise keep the original token.
- Maintain short/numeric alias suppression; keep ambiguous aliases list configurable.
- Preserve tabletop gating—only override when strong franchise/character evidence exists.

## Acceptance Criteria
- Multi-word names and glued/camelCase tokens are recognized in dry-run without increasing false positives.
- Ambiguous tokens (e.g., `angel`) no longer cause incorrect franchise/character assignment in terrain/scenery contexts.
- Dry-run JSON shows expected proposals on known-good samples; apply path persists correctly (as verified previously for 304/305).

## Operational Notes
- PowerShell-safe commands (examples):
  - `setx STLMGR_DB_URL "sqlite:///./data/stl_manager_v1.db"`
  - `$env:STLMGR_DB_URL="sqlite:///./data/stl_manager_v1.db"; .\\.venv\\Scripts\\python.exe .\\scripts\\30_normalize_match\\match_franchise_characters.py --out .\\reports\\match_franchise_dryrun.json`
  - `$env:STLMGR_DB_URL="sqlite:///./data/stl_manager_v1.db"; .\\.venv\\Scripts\\python.exe .\\scripts\\30_normalize_match\\match_franchise_characters.py --apply`

## Decision
- Review this proposal. If approved, we’ll implement tokenizer expansions in the matcher first (safer), validate via dry-run, then promote to shared tokenizer.
