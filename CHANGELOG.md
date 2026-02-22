# Changelog

All notable changes to the STL Manager project.

---

## 2025-09-02

- Collections SSOT and matcher implemented. Per-designer YAML lives under `vocab/collections/*.yaml` and `scripts/30_normalize_match/match_collections.py` fills `variant.collection_*`.
- Added a YAML validator: `scripts/maintenance/validate_collections_yaml.py`.
- Printable Scenery: consolidated "Time Warp Europe - ..." sub-lines into one `Time Warp Europe` collection id.

## 2025-08-31

- Shared alias rules extracted to `scripts/lib/alias_rules.py` and reused by both the normalizer and the franchise matcher.
- Normalizer now performs conservative bigram character aliasing and prefers multi-token aliases (e.g., `poison_ivy` from "poison ivy") over shorter ambiguous tokens.
- Short/numeric and ambiguous alias gating unified between normalizer and matcher (prevents `002 -> zero_two` without clear franchise evidence).
- Deprecated `scripts/common` — old helpers were removed; shared helpers live under `scripts/lib/`.

## 2025-08-29

- Tabletop vocab ingestion for Units (40K/AoS/Heresy) and Parts (40K wargear + bodies).
- DB schema supports `game_system`, `faction`, `unit` (+aliases), and `part` (+aliases), with association tables to link Variants ↔ Units and Variants/Units ↔ Parts.
- See `docs/SCHEMA_codex_and_linking.md` for the schema, and `docs/API_SPEC.md` for endpoints including `GET /units/{id}/bundle` (dual return: full models + parts).
- Loader supports nested YAML schemas under `codex_units.<system>` including AoS grand alliances and Heresy legions, plus AoS faction-level and shared special sections (endless spells, invocations, terrain, regiments of renown).
