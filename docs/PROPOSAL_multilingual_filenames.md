# Proposal: Language tag + English tokens backfill (non‑destructive)

This document defines a single, focused plan to handle multilingual filenames for matching and UI: detect language during normalize, then backfill an English tokens column and have matchers prefer those tokens. Originals are preserved; no files are renamed on disk.

## Status and restart pointers (2025‑09‑03)

- [x] Schema columns added: `variant.token_locale`, `variant.english_tokens` (Alembic: `alembic/versions/20250902_multilingual_tokens.py`; models in `db/models.py`).
- [x] Normalize tags `token_locale` during inventory normalize (`scripts/30_normalize_match/normalize_inventory.py`).
- [x] Backfill `english_tokens` implemented and passing tests: `scripts/30_normalize_match/backfill_english_tokens.py`; green test: `tests/workflow/test_multilingual_backfill_workflow.py`.
- [x] Matchers prefer `english_tokens` when present (`scripts/30_normalize_match/match_variants_to_units.py`).
- [x] Tests for end‑to‑end backfill/idempotency are green.
- [ ] Optional: `ui_display_en` materialization (deferred).

Resume here when continuing:
- Optional next: add lightweight `ui_display_en` materialization in backfill (string join of `english_tokens` or curated breadcrumb) and wire to UI if needed.
- For a quick smoke in your real DB (dry‑run): `\.venv\Scripts\python.exe scripts/30_normalize_match/backfill_english_tokens.py --db-url sqlite:///./data/stl_manager_v1.db --batch 50 --limit 5 --out reports/backfill_dryrun_smoke.json`.

## Goals

- Preserve originals (paths/tokens) exactly as scanned; no destructive renames.
- Reliable matching using English tokens aligned with our English vocab.
- Deterministic, offline, and fast: curated YAML glossaries + simple heuristics.
- Auditable and idempotent: dry‑run by default; timestamped reports.

## Data model

- `variant.token_locale` (String, nullable): best‑effort language code for scanned tokens (e.g., `en`, `es`, `fr`, `zh`, `ja`).
- `variant.english_tokens` (JSON, nullable): list[str] of English‑normalized tokens used by matchers and UI.
- Optional: `variant.ui_display_en` (Text) for a ready‑made breadcrumb/label (can be added later if needed).

## Normalize (lightweight language tagging)

Detect `token_locale` only:
- If all ASCII → `en`.
- If CJK codepoints present: detect `ja` when hiragana/katakana found; otherwise `zh`.
- Else (non‑ASCII Latin): optionally call a tiny detector (e.g., `langid`) only for non‑ASCII cases.
Persist `token_locale`. Do not compute English at this stage.

## Backfill english_tokens (batch, idempotent)

Script: `scripts/30_normalize_match/backfill_english_tokens.py`
- Select Variants where `english_tokens IS NULL` (or when `--force`).
- For each row:
  1) Unicode NFKC → lowercase
  2) Longest‑phrase‑first dictionary match using `vocab/i18n/*.yaml` (generic + domain)
  3) Fallback to romanization (e.g., Unidecode) for unknown tokens
  4) Write `english_tokens` (and optionally `ui_display_en`)

Flags: `--db-url`, `--batch`, `--limit`, `--ids`, `--apply`, `--out` (timestamped JSON report). Default is dry‑run.

PowerShell examples:

```powershell
# Dry-run
.\.venv\Scripts\python.exe .\scripts\30_normalize_match\backfill_english_tokens.py `
  --db-url sqlite:///./data/stl_manager_v1.db `
  --batch 500 `
  --out ("reports/backfill_english_tokens_dryrun_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")

# Apply
.\.venv\Scripts\python.exe .\scripts\30_normalize_match\backfill_english_tokens.py `
  --db-url sqlite:///./data/stl_manager_v1.db `
  --batch 500 `
  --apply `
  --out ("reports/backfill_english_tokens_apply_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
```

## Matchers (preference order)

- Use `variant.english_tokens` for alias lookup (designer/franchise/character/units/parts).
- Fall back to `variant.raw_path_tokens` only for edge heuristics.

## Glossaries (source of truth)

- `vocab/i18n/generic.yaml` — common modeling terms and abbreviations (e.g., `piernaDRCH` → `right leg`, `conejo` → `rabbit`).
- `vocab/i18n/warhammer.yaml` — scoped proper nouns (e.g., `jardin de morr` → `Garden of Morr`).
- Keys are matched after Unicode NFKC + lowercase; prefer multi‑token/phrase entries; keep domain lists conservative to avoid false positives.

## Efficiency & safety

- Language tagging is O(1) per path (mostly heuristic); backfill is dictionary lookups + romanization with an in‑process cache.
- Idempotent: skip populated rows unless `--force`; write timestamped reports under `reports/`.
- When glossaries change, re‑run backfill with `--force` to refresh outputs.

## Tests

- Phrase‑priority and Unicode normalization tests (e.g., `PiernaDRCH` → `right leg`).
- CJK phrase mapping (e.g., `分件` → `split parts`), with romanization fallback when unknown.
- Locale heuristics correctness (ASCII→`en`, CJK script splits `ja` vs `zh`).
- Idempotency: backfill re‑run makes no changes without `--force`.

## Rollout

1) Add columns: `variant.token_locale`, `variant.english_tokens` (optional: `variant.ui_display_en`).
2) Add locale detection in normalize to populate `token_locale`.
3) Implement backfill script for `english_tokens` using `vocab/i18n/`.
4) Switch matchers to prefer `english_tokens` (fallback to originals).
5) Add tests (phrases, CJK, locale heuristics, idempotency).
6) Optional later: materialize `ui_display_en` for UI performance.

## Examples

- `sample_store/JARDIN DE MORR/...` → English token includes `Garden of Morr`.
- `sample_store/瑟瑟妹子/分件/...` → `split parts` (CJK phrase mapping; first segment can romanize/curate later).
- `.../PiernaDRCH.stl` → `right leg`; `.../PiernaIZQ.stl` → `left leg`.

This plan keeps files untouched, makes matching reliable with English tokens, and remains fast, auditable, and easy to maintain.
