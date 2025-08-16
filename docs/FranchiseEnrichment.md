# Franchise Enrichment Workflow (Draft)

Purpose: Automate population of minimal character linkage (just name + aliases) when a new franchise is added, while preserving conservative, auditable normalization principles.

## Goals
- Keep DB schema minimal: character_id, franchise_id, canonical_name, display_name (optional), aliases[].
- No bios, descriptions, backstory, images, importance tiers.
- Allow manifest to supply detection hints without persisting extra fields.
- Surface high-signal tokens as suggestions instead of auto-promoting ambiguous names.
- Avoid false positives from short / generic tokens.
- Record only a simple provenance source per character/alias.

## Data Sources (Priority Order)
1. Local Manifest (if present) `vocab/franchises/<franchise>.json`.
2. Heuristic Co-occurrence Mining (scan paths for token clusters after franchise creation).
3. External Adapters (optional, gated) returning only canonical names + alias candidates.
4. User Manual Additions via API/UI.

## Manifest JSON Schema (v1 minimal)
```
{
  "franchise": "powerpuff_girls",              // snake_case canonical
  "display_name": "The Powerpuff Girls",
  "source_version": 1,                          // increments when manifest updated
  "aliases": ["powerpuff_girls", "powerpuff"],
  "characters": [
    {"canonical": "blossom", "aliases": []},
    {"canonical": "mojo_jojo", "aliases": ["mojojojo"]}
  ],
  "tokens": {
    "strong_signals": ["powerpuff", "mojojojo"],
    "weak_signals": ["blossom", "bubbles"],
    "stop_conflicts": ["him"],                  // ambiguous tokens blocked unless paired
    "notes": "'him' requires co-occurrence with strong signal."
  },
  "provenance": { "source": "manual_seed" }
}
```

## Heuristic Mining
1. Collect candidate tokens from residual_tokens for variants where franchise manually set or alias matched.
2. Filter out existing canonical + aliases.
3. Compute co-occurrence graph (tokens appearing within same path or file stem sets) and frequency stats.
4. Score = frequency_weight * co_occurrence_factor * distinct_directory_factor.
5. Promote to suggestion if:
   - Score >= threshold_primary, OR
   - Appears with >=2 strong_signals tokens AND distinct_directory_factor >= min_dirs.
6. Apply disambiguation rules:
   - Block tokens <=3 chars unless in strong_signals manifest.
   - Block generic English stopwords unless manifest strong_signals.
   - Ambiguous tokens in stop_conflicts require at least one strong_signal in same set.

## External Adapter (Concept)
Adapter interface returns list of { canonical, aliases[], evidence_source }.
Entries become suggestions with provenance external_<adapter> unless already present.

## Enrichment Job Flow
```
Trigger: POST /api/v1/vocab/franchise (new) OR POST /api/v1/franchises/{id}/enrich

1. Load manifest if file exists.
2. Upsert franchise aliases (skip existing; record additions in audit).
3. Upsert character records from manifest (canonical -> character entity), attach aliases.
4. Run heuristic mining over recent scan slice (limited to N directories for performance) to build suggestions.
5. (Optional) Invoke external adapters (if enabled flag & network allowed).
6. Write suggestions to suggestions table (franchise_character domain or reuse franchise domain with subtype=character).
7. Produce coverage summary: { total_candidates, promoted_from_manifest, suggestions_created, blocked_ambiguous }.
8. If dry_run=true, skip steps 2–3–6 and just return prospective diff.
```

## API Additions (Draft)
- POST /api/v1/franchises/{id}/enrich?dry_run=true|false
  - Body: { "sources": ["manifest", "heuristic", "external_wikidata"], "limit": 500 }
  - Response: coverage summary + suggestions preview + any conflicts.
- GET /api/v1/franchises/{id}/coverage
  - Returns counts: characters_known, characters_suggested, strong_signals_count, weak_signals_count, last_enriched_at.

## Provenance & Audit
Store per character/alias: provenance_source (manual_seed | heuristic | external_<adapter>) and optional evidence_tokens[] (small list). Nothing else.

## Conflict Handling
- If manifest introduces alias already claimed by different franchise → mark conflict, do not auto-attach, surface in normalization_warnings.
- If external adapter suggests token that is a known designer/faction token, require manual confirm.

## Future Extensions
- Popularity weighting (ranking) – still outputs only name + aliases.
- ML disambiguation (Phase 4).
- Automatic backfill of residual token to character linkage once character promoted.

## Rationale
Keeps core token map lean while enabling gradual, auditable enrichment of franchise ecosystems; leverages existing residual mining loop and suggestion promotion workflow for consistency.
