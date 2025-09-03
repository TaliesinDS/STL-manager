# Normalization Flow (v0.1 Draft)

Moved from repository root to `docs/` on 2025-08-16 (repository restructure) – content unchanged.

Purpose: Define deterministic steps turning raw filesystem artifacts into normalized metadata fields (see `MetadataFields.md`) using vocab in `tokenmap.md`.

Status update (2025-09-03)
- Implemented passes: structural extraction (scale ratio/height/version/pose), designer aliases, conservative faction/system hints, variant axes (segmentation/internal_volume/support_state/part_pack_type), coarse NSFW cues, intended_use_bucket, pc_candidate_flag (proto), residual capture, and warnings.
- Matchers integrated: unit and franchise matchers run after normalization and support dry‑run/apply; kit handling collapses or expands children based on flags.
- Token outputs persist to Variant fields and residuals; `token_version` increments on vocab changes to enable selective re‑normalize.

Status update (2025-09-03)
- Implemented passes: structural extraction (scale ratio/height/version/pose), designer aliases, conservative faction/system hints, variant axes (segmentation/internal_volume/support_state/part_pack_type), coarse NSFW cues, intended_use_bucket, pc_candidate_flag (proto), residual capture, and warnings.
- Matchers integrated: unit and franchise matchers run after normalization and support dry‑run/apply; kit handling collapses or expands children based on flags.
- Token outputs persist to Variant fields and residuals; `token_version` increments on vocab changes to enable selective re‑normalize.

Scope (Phase 1): Designers, game_system (implicit via faction?), codex_faction, lineage_family, variant axes (segmentation/internal_volume/support_state/part_pack_type), scale basics, intended_use_bucket, pc_candidate_flag (proto), content_flag (coarse NSFW), residual capture, warnings.

Out-of-Scope (Phase 1): lineage_primary activation, actor likeness, advanced NSFW (level/exposure/acts), human_subtype, loadout variants, pose semantic grouping beyond simple token pattern, geometry hashing.

---
## 1. Inputs
For each model archive or directory leaf (candidate record):
- absolute_path
- relative_path (from collection root)
- path_segments (split on path separators)
- filename(s) (top-level STL files within leaf) — Phase 1 may ignore internals beyond folder name unless leaf has no subfolders.
- file_extension summary (counts per extension)
- size_bytes (aggregate) [optional Phase 1]
- last_modified (for audit only, not classification)

Token source string: join of relevant path segments plus (optionally) filename stems (without extension) if leaf folder name is overly generic (e.g., "files"). Phase 1: folder names only.

YAML SSOT (Tabletop Units & Parts):
- External vocab under `vocab/` defines canonical Units (40K/AoS/Heresy) and Parts (wargear, bodies) using a nested schema.
- A dedicated loader (`scripts/load_codex_from_yaml.py`) ingests those manifests into normalized tables (`game_system`, `faction`, `unit`, `unit_alias`, `part`, `part_alias`) and preserves full-fidelity `raw_data`.
- The normalization/matching passes may use these tables as authoritative lookup for tabletop context and to create `variant_unit_link` / `variant_part_link` associations.

---
## 2. Preprocessing
1. Lowercase.
2. Replace split chars (`split_on` in token map) with space.
3. Strip punctuation listed in `strip_chars` from ends.
4. Collapse multiple spaces -> single.
5. Split on spaces -> raw tokens.
6. Preserve `raw_path_tokens` (full list, including stopwords, duplicates, order index).
7. Filter tokens with length < min_token_length -> excluded from classification passes (still in raw list).
8. Build `dedup_tokens` maintaining first occurrence index for stable ordering.

---
## 3. Pass Ordering (Deterministic)
1. Structural patterns (scale ratio, mm, version, pose) — regex from token map.
2. Designer aliases.
3. Game system inference (if explicit system token list exists later; Phase 1: may infer from faction cluster heuristics, else null).
4. Faction lookup (only if system known; else note potential faction tokens for possible warning).
5. Lineage family lookup (skip tokens already consumed by deterministic faction implying lineage if future rule added).
6. Variant axes (segmentation, internal_volume, support_state, part_pack_type, bust indicator).
	- Implementation detail: in addition to canonical token lists in `tokenmap.md`, the normalizer applies conservative heuristics to catch common concatenated or multi-token phrases (e.g., `cut + version`, `splitversion`, `uncutversion`, `non + split + version`, and `presupported*` prefixes). These do not expand the canonical alias sets but improve recall on real-world folder/file names. Conflicts add warnings (e.g., `support_state_conflict`).
7. NSFW strong cues.
8. Intended use bucket (top-level directory names only; not deeper segments).
9. Role cues (pc_candidate_flag proto).
10. NSFW weak cues (only if not flagged NSFW yet).
11. Residual token collection (unmatched non-stopword tokens excluding structural pattern matches).

---
## 4. Matching & Field Setting Rules
General:
- First high-confidence assignment stands unless a later conflicting match has strictly higher confidence weight.
- Each match yields (field, value, confidence_delta, notes[]?). Maintain `confidence_accumulator` (integer) for potential later thresholding (Phase 1 may only store raw value + warnings; accumulator mainly future-proof).

Confidence Weights (initial suggestion):
- Designer: +5
- Faction: +5
- Lineage family: +4
- Variant axis single token: +2 (per axis)
- Strong NSFW cue: +4
- Weak NSFW cue: +2
- Intended use bucket: +3
- Role pc_positive set: +2
- Structural scale detection: +3
- Structural pose/version: +1 each

Conflicts subtract 50% of smaller side (e.g., segmentation both split & merged => subtract 1 and add warning).

### 4.1 Structural
- scale_ratio_den if ratio regex matches; record multiple? keep first; if second differs -> warning `scale_mm_ratio_conflict` or `uncommon_scale_ratio` as appropriate.
- height_mm (direct from mm_pattern). If both ratio & mm mismatch expected mapping (not resolved in Phase 1) -> warning.
- version_num from version pattern.
- pose_variant from pose pattern (store raw code portion group 2).

### 4.2 Designers
- Single alias match sets `designer_canonical`.
- Second different alias mapping -> `designer_alias_collision` warning; unset designer (or keep first + warning) — choose keep first for reproducibility.

### 4.3 Faction & System
- If token matches a faction alias and system unknown: stage candidate; if ≥2 staged candidates share a system, infer that system and promote faction with highest frequency. Else leave system null and add warning `faction_without_system` per unique candidate string.
- If system known, first faction match sets `codex_faction`. Additional different faction tokens -> ignore + residual (could be multi-faction kit; Phase 2 may allow multi-value).

### 4.4 Lineage Family
- Simple alias map; stop after first family hit unless a second different family appears -> add `ambiguous_lineage_token` warning; keep null for lineage_family in that case.

### 4.5 Variant Axes
- For each axis maintain a bitmask of seen classes; if bitmask cardinality >1 -> set value=unknown + axis conflict warning name.

### 4.6 NSFW
- Strong: set `content_flag=nsfw` immediately.
- Weak: if not already nsfw and no safe-context override, set nsfw + warning `nsfw_weak_confidence`.

### 4.7 Intended Use
- Only evaluate top-level segment (or first two if one is generic like "models"). Conflict => warning + leave field null.

### 4.8 Role (pc_candidate_flag)
- If any pc_positive and none of pc_negative or monster_terms -> true.
- If both positive and negative/monster present -> warning `pc_candidate_conflict` and leave null.

### 4.9 Residual Tokens
- All tokens not consumed by successful matches or defined stopwords.
- Store ordered list `residual_tokens` for later vocab expansion triage.

### 4.10 Franchise/Character Guardrails (Matcher)
These rules harden franchise/character inference to prevent false positives from generic words and ambiguous names.

- Stop-conflicts (per franchise): Any token listed under `tokens.stop_conflicts` in a franchise manifest is not allowed to map to that franchise (e.g., generic nouns like `gate`).
- Ambiguous aliases (global): Common names like `angel`, `sakura` are ignored unless there is independent franchise evidence (another alias/token) or a strong character/full-name hit. Ambiguous aliases never count as strong by themselves.
- Strong-or-supporting-only assignment: The matcher sets `franchise` only if at least one of the following holds:
	- The token is in that franchise’s `strong_signals`, or
	- There is strong character evidence for that franchise, or
	- There is additional independent franchise evidence besides the triggering token (alias + token, two aliases, etc.). A single weak alias is not enough.
- Tabletop context: Tabletop hints suppress weak assignments; strong evidence still assigns. Weak matches in tabletop context emit hints/warnings only.
- Token expansion awareness: The matcher may split camelCase/glued tokens and use bigrams; prefer putting full names and surnames in `strong_signals`, and short/generic pieces in `weak_signals` to steer this.
- Curation tips: Put generic words that also serve as franchise names into that franchise’s `stop_conflicts`. For cross-franchise common given names, consider adding them to the matcher's ambiguous alias list and rely on supporting evidence.

---
## 5. Warnings Assembly
Aggregate deduplicated list of warning codes in `normalization_warnings` (preserve first occurrence order). Codes documented in token map.

---
## 6. Idempotency & Re-runs
- Store alongside each record the `token_map_version` used.
- On rerun with same version: skip normalization unless raw path changed (hash of joined path segments).
- On version bump: identify changed vocab segments (diff alias sets). Only re-normalize records whose raw tokens intersect the changed alias/token sets OR which lacked a previously introduced field now required.

---
## 7. Data Output Schema (Phase 1 subset)
- raw_path_tokens (array)
- residual_tokens (array)
- designer_canonical (string|null)
- game_system (string|null)
- codex_faction (string|null)
- lineage_family (string|null)
- segmentation (enum split|merged|unknown|null)
- internal_volume (enum hollowed|solid|null)
- support_state (enum presupported|supported|unsupported|null)
- part_pack_type (enum bust_only|base_only|accessory|null)
Note on modular kits:
- When a variant is identified as a kit child (via immediate child folder under a parent), the backfill normalizer sets child `part_pack_type` to a normalized label (e.g., `bodies`, `helmets`, `weapons`, `arms`, `accessories`). Parents are marked with `is_kit_container=true` and aggregate `kit_child_types`. Reports collapse kit children by default; enabling `--include-kit-children` shows `kit_child_label` per child.
- has_bust_variant (bool|null) [derived if bust_indicators present]
- height_mm (int|null)
- scale_ratio_den (int|null)
- version_num (int|null)
- pose_variant (string|null)
- intended_use_bucket (enum tabletop_intent|display_large|mixed|null)
- pc_candidate_flag (bool|null)
- content_flag (enum nsfw|sfw|null) — default null -> treat as sfw at display time.
- normalization_warnings (array of codes)
- token_map_version (int)
- normalization_confidence (int) [accumulator]

---
## 8. Edge Cases
- Empty folder name or all stopwords -> no classification; produce warning `empty_signal` (future) and rely on parent context later.
- Extremely long token (>64 chars) -> truncate for logging but keep full original in raw list; skip classification on truncated part.
- Duplicate identical tokens: count occurrences but treat as one for alias mapping (could increase confidence in Phase 2).
- Unicode/Accents: Normalize to NFC then lowercase; accents retained for now (Phase 2 may strip for comparisons).

---
## 9. Performance Considerations
- Single scan over `dedup_tokens` applying deterministic pass order; maintain sets for quick membership (designer_alias_set, faction_alias_set, etc.).
- Regex patterns compiled once per run.
- Warnings appended via small static map lookups.

---
## 10. Future Hooks (Placeholders)
- lineage_primary resolution (after family) with conflict scoring.
- Actor likeness detection pass (between NSFW and role cues, because may influence filtering).
- Advanced NSFW breakdown (exposure, acts) after weak cue handling.
- Multi-faction/ally detection (store array instead of single codex_faction).

---
## 11. Test Strategy (When Implemented)
Minimal unit tests per pass:
- Designer collision.
- Faction without system.
- Segmentation conflict (split + merged).
- Strong vs weak NSFW.
- Intended use conflict.
- Scale ratio + mm mismatch.
- Residual capture of unknown faction token.

---
## 12. Change Log
v0.1: Initial draft aligned with token map v2.

---
## 13. Summary
Flow defines reproducible ordering separating *vocabulary data* (token map) from *process logic* (this doc). Allows safe token map evolution with minimized unintended downstream changes.
