# API Specification (Draft v0)
Status update (2025-09-03)
- Spec reflects implemented domain models: Variants, Units, Parts, Factions, Game Systems, Characters, and linking tables.
- Unit bundle concept (variants + parts) is documented for a future endpoint; loaders and links exist to support it.
- Normalization/matcher flows and bulk operations align with current scripts; auth remains single-user key (future work).


Moved from repository root to `docs/` on 2025-08-16 (repository restructure) – content unchanged.

Purpose: Define initial REST/JSON contract for the STL Manager application so schema + normalization design remain aligned with future UI/editor workflows. This draft focuses on read/write of metadata, dynamic vocab management, normalization re-runs, overrides, and bulk operations.

Principles:
- Stateless JSON over HTTP; versioned under /api/v1/.
- All responses include { "success": bool, "data": <payload|null>, "error": <object|null>, "meta": <object|null> }.
- ISO8601 UTC timestamps.
- Snake_case field names externally (match DB / spec).
- ETags or version integers for optimistic concurrency on mutable resources.
- Pagination: cursor based (preferred) plus optional page/limit fallback.
- Filter syntax: simple key=value + key__op=value (ops: eq (default), in, contains, icontains, lt, lte, gt, gte, isnull, overlap (arrays), any (arrays)).
- Bulk edits are asynchronous jobs with status tracking.
- Derived fields never overwritten by normalization when manual override present.

Scope additions (2025-08-29):
- Add Units and Parts resources to support tabletop browsing and dual return types (full models + parts/mods)
- Add linking endpoints: Variant↔Unit, Variant↔Part, Unit↔Part
- Add combined unit detail endpoint that returns both linked variants and parts

Auth (Future):
- Initial single-user mode: static API key header X-API-Key.
- Later: OAuth2 / JWT; roles (admin, curator, viewer).

Error Format:
```
{
	"success": false,
	"error": {
		"code": "validation_error",
		"message": "Field value invalid",
		"details": { "field": "lineage_family", "reason": "unknown value" }
	}
}
```

## 1. Field Catalog
Expose machine-readable schema for dynamic forms.

GET /api/v1/schema/fields
Response data example:
```
{
	"fields": [
		{
			"name": "designer",
			"type": "string",
			"phase": "P1",
			"editable": true,
			"auto": true,
			"override_allowed": true,
			"enum": null
		},
		{
			"name": "scale_ratio_den",
			"type": "int",
			"phase": "P1",
			"editable": false,
			"auto": true,
			"override_allowed": true,
			"enum": null
		}
	],
	"token_map_version": 9,
	"designers_map_version": 1
}
```

## 2. Variant Resources
Represents a single file/model variant (post-scan granular unit).

GET /api/v1/variants?filters&cursor=...
- Filters: designer=ghamak, game_system=warhammer_40k, lineage_family=elf, asset_category=terrain, content_flag=nsfw, residual_tokens__contains=wizard.
- Returns page of variants plus next_cursor (or null).

Sample response:
```
{
	"success": true,
	"data": {
		"results": [{
			"id": "uuid-1",
			"designer": "ghamak",
			"franchise": null,
			"asset_category": "miniature",
			"lineage_family": "elf",
			"residual_tokens": ["archer", "forest"],
			"overrides": ["lineage_family"],
			"updated_at": "2025-08-16T10:10:10Z"
		}],
		"next_cursor": null
	}
}
```

GET /api/v1/variants/{id}
- Returns full detail (all metadata fields + override map + warnings + audit summary counts).
- Includes `characters` array when linked: each { character_id, name, aliases, franchise, info_url }.

Kit container fields (if present on this variant):
- `parent_id` (number|null), `is_kit_container` (bool), `kit_child_types` (array of strings), and child `part_pack_type` (string) are exposed on the Variant resource.
The API treats these as read-only except via dedicated normalization/backfill jobs.

GET /api/v1/variants/{id}/units
- Lists Units linked to this Variant (via `variant_unit_link`).
Response data example:
```
{
	"success": true,
	"data": {
		"variant_id": "uuid-1",
		"units": [
			{ "unit_id": "u-abc", "unit_key": "intercessors", "name": "Intercessors", "game_system": "w40k", "faction": "adeptus_astartes", "is_primary": true }
		]
	}
}
```

GET /api/v1/variants/{id}/proxy-candidates
- Returns list of units the variant can proxy (directly or via loadout kits), with summary of completeness.
Response:
```
{
	"success": true,
	"data": {
		"variant_id": "uuid-1",
		"units": [
			{
				"unit_id": "u-abc",
				"unit_name": "Intercessors",
				"game_system": "warhammer_40k",
				"faction": "adeptus_astartes",
				"rules_url": "https://www.warhammer-community.com/downloads/40k_datasheets/intercessors.pdf",
				"proxy_type": "stylized_proxy",
				"multi_unit_proxy_flag": true,
				"loadout_coverage": {
					"bolt_rifle": { "status": "complete" },
					"auto_bolt_rifle": { "status": "partial", "missing_components": ["left_auto_arm"] },
					"stalker_bolt_rifle": { "status": "missing" }
				},
				"coverage_score": 0.67
			}
		]
	}
}
```

GET /api/v1/variants/{id}/loadout-coverage?unit_id=... (optional unit filter)
- Detailed matrix of loadout requirements vs supplied components.

GET /api/v1/variants/{id}/component-compatibility
- Lists explicit compatibility assertions for component-providing variant (arms, weapons, backpacks).
Response:
```
{
	"success": true,
	"data": {
		"component_variant_id": "uuid-comp",
		"compatibility": [
			{ "target_type": "model_group", "target_id": "mg-123", "fit_type": "exact", "confidence": "certain" },
			{ "target_type": "variant", "target_id": "v-shell1", "fit_type": "near", "confidence": "probable" }
		]
	}
}
```

POST /api/v1/variants/{id}/component-compatibility
```
{
	"assertions": [
		{ "target_type": "model_group", "target_id": "mg-123", "fit_type": "exact", "confidence": "certain", "evidence_tokens": ["titan_forge", "intercessor" ] }
	]
}
```

DELETE /api/v1/variants/{id}/component-compatibility/{assertion_id}
- Soft deletes assertion.

POST /api/v1/variants/{id}/proxy-assertions
```
{
	"assertions": [
		{
			"unit_id": "u-abc",
			"proxy_type": "counts_as",
			"loadout_code": "bolt_rifle",
			"evidence_tokens": ["intercessor", "bolt", "primaris"],
			"confidence": "probable"
		}
	]
}
```
Response returns created rows (id, normalized fields).

DELETE /api/v1/variants/{id}/proxy-assertions/{assertion_id}
- Removes granular proxy assertion (soft delete with audit).

POST /api/v1/variants/{id}/unit-links
```
{
	"links": [
		{ "unit_id": "u-abc", "is_primary": true, "match_method": "manual", "match_confidence": 0.95, "notes": "confirmed" }
	]
}
```
Response returns created rows (id, normalized fields).

DELETE /api/v1/variants/{id}/unit-links/{link_id}
- Removes a Variant↔Unit link (soft delete with audit).

PATCH /api/v1/variants/{id}
Request:
```
{
	"changes": [
		{ "field": "franchise", "value": "lotr" },
		{ "field": "lineage_family", "value": "elf", "override": true },
		{ "field": "user_tags", "op": "add_to_array", "values": ["archer", "woodland"] }
	],
	"expected_version": 12
}
```
Response includes new version.

DELETE /api/v1/variants/{id}/overrides/{field}
- Clears override; field recomputed next normalization pass or immediately if on-demand recompute requested.

POST /api/v1/variants/normalize (optional immediate re-run)
Request: { "variant_ids": ["uuid-1", "uuid-2"], "force": false }
- Skips fields with overrides.

## 2A. Unit Resources
Represents a tabletop unit entry normalized from codex YAML (40K/AoS/Heresy).

GET /api/v1/units?filters&cursor=...
- Filters: system_key=w40k, faction_key=grey_knights, role=troops, category=unit, legal_in_editions__any=10e.
Response:
```
{
	"success": true,
	"data": {
		"results": [ { "id": "u-abc", "key": "intercessors", "name": "Intercessors", "system_key": "w40k", "faction_key": "adeptus_astartes", "role": "troops" } ],
		"next_cursor": null
	}
}
```

GET /api/v1/units/{id}
- Returns full unit record including attributes, raw_data, and provenance.

GET /api/v1/units/{id}/variants
- Lists linked Variants (via `variant_unit_link`). Optional `primary_only=true`.

GET /api/v1/units/{id}/parts
- Lists explicitly linked compatible/recommended/required Parts (via `unit_part_link`). Optional filters: relation_type, required_slot.

GET /api/v1/units/{id}/bundle
- Returns a combined view for the Unit: linked variants and parts in one payload.
Response:
```
{
	"success": true,
	"data": {
		"unit": { "id": "u-abc", "key": "intercessors", "name": "Intercessors" },
		"variants": [ { "id": "v-1", "rel_path": "...", "filename": "...", "is_primary": true } ],
		"parts": [ { "id": "p-1", "key": "bolt_rifle", "name": "Bolt Rifle", "relation_type": "compatible", "required_slot": "right_hand" } ]
	}
}
```

POST /api/v1/units/{id}/parts
```
{
	"links": [ { "part_id": "p-1", "relation_type": "compatible", "required_slot": "right_hand", "notes": "SM Primaris" } ]
}
```
Response returns created link rows.

DELETE /api/v1/units/{id}/parts/{link_id}
- Removes a Unit↔Part link (soft delete with audit).

GET /api/v1/factions?system_key=w40k&parent_id=null
- Lists factions (optionally scoped by system and parent).

GET /api/v1/game-systems
- Lists available game systems and display names.

## 2B. Part Resources
Represents modular parts (wargear, bodies, decor) ingested from YAML.

GET /api/v1/parts?filters&cursor=...
- Filters: system_key=w40k, faction_key=adeptus_astartes, part_type=wargear, category=weapon_ranged, slot=right_hand, available_to__any=space_marines.
Response:
```
{
	"success": true,
	"data": {
		"results": [ { "id": "p-1", "key": "bolt_rifle", "name": "Bolt Rifle", "part_type": "wargear", "slot": "right_hand" } ],
		"next_cursor": null
	}
}
```

GET /api/v1/parts/{id}
- Returns full part record including attributes, raw_data, and provenance.
	- Connector metadata (optional) is returned under `attributes.connectors` with the shape documented in `SCHEMA_codex_and_linking.md`.

GET /api/v1/parts/{id}/variants
- Lists Variants linked to this Part (via `variant_part_link`).

POST /api/v1/variants/{id}/parts
```
{
	"links": [ { "part_id": "p-1", "match_method": "token", "match_confidence": 0.9, "notes": "shoulder pad set" } ]
}
```
Response returns created `variant_part_link` rows.

DELETE /api/v1/variants/{id}/parts/{link_id}
- Removes a Variant↔Part link (soft delete with audit).

## 3. Bulk Operations
POST /api/v1/bulk/variants/update
```
{
	"filter": { "designer": "ghamak", "lineage_family": "elf" },
	"operations": [
		{ "field": "base_theme", "value": "forest" },
		{ "field": "user_tags", "op": "add_to_array", "values": ["legacy"] }
	],
	"dry_run": true
}
```
Response (dry_run): counts only.
Real run returns job_id.

GET /api/v1/jobs/{id}
```
{
	"success": true,
	"data": {
		"id": "job-123",
		"type": "bulk_update",
		"status": "running",
		"progress": { "processed": 150, "total": 1200 },
		"started_at": "...",
		"completed_at": null,
		"result_summary": null
	}
}
```

POST /api/v1/jobs/{id}/cancel (best-effort)

## 4. Vocabulary Management
Domains: designer, franchise, lineage_family, lineage_primary, faction, vehicle_type, vehicle_era, terrain_subtype, base_theme, asset_category (rare), addon_type, style_primary.
Upcoming domains (Phase 2+): component_type, weapon_profile_code, loadout_code.

GET /api/v1/vocab/{domain}?q=partial&limit=20

POST /api/v1/vocab/{domain}
```
{
	"canonical_name": "middle_earth_alliance",
	"display_name": "Middle-Earth Alliance",
	"aliases": ["middle earth alliance"],
	"notes": "Created from August 2025 scan residuals"
}
```

PATCH /api/v1/vocab/{domain}/{id}
- Fields: display_name, deprecate=true|false, add_alias, remove_alias.

DELETE /api/v1/vocab/{domain}/{id}
- Soft delete (sets deprecated flag). Variants retain foreign key until remapped.

GET /api/v1/vocab/changes?since=timestamp
- Audit feed for replication or UI update.

## 5. Suggestions (Candidate Vocab)
GET /api/v1/suggestions
Query params: domain=franchise|designer|lineage, min_frequency=2
Response entries:
```
{
	"success": true,
	"data": {
		"candidates": [
			{
				"id": "cand-1",
				"domain": "franchise",
				"suggested_name": "attack_on_titan",
				"evidence_tokens": ["aot", "mikasa"],
				"variant_count": 37,
				"first_seen": "2025-08-15T...Z",
				"last_seen": "2025-08-16T...Z"
			}
		]
	}
}
```

POST /api/v1/suggestions/{id}/promote
```
{
	"canonical_name": "attack_on_titan",
	"display_name": "Attack on Titan",
	"aliases": ["aot"],
	"assign_variants": true
}
```
- Creates vocab entry, assigns variants (unless assign_variants=false), removes candidate, queues normalization re-run.

DELETE /api/v1/suggestions/{id}
- Dismiss candidate (records suppression so it doesn’t reappear until new evidence threshold).

## 6. Audit
GET /api/v1/audit/variant/{id}?limit=100&cursor=...
GET /api/v1/audit/vocab/{domain}/{id}

Revert endpoint:
POST /api/v1/audit/revert
```
{ "audit_id": "aud-1234" }
```
- Creates inverse change (if still applicable) and logs new audit row referencing original.

## 7. Overrides
GET /api/v1/variants/{id}/overrides
Response: list of { field, manual_value, original_auto_value, applied_at, applied_by }

POST /api/v1/variants/{id}/overrides
```
{
	"field": "lineage_family",
	"manual_value": "elf",
	"expected_auto_value": "unknown"
}
```
- Fails if current auto value mismatches expected_auto_value (stale client guard) unless force=true.

DELETE /api/v1/variants/{id}/overrides/{field}
- Clears override (same as earlier DELETE convenience).

## 8. Normalization & Recompute
POST /api/v1/normalize/run
```
{
	"scope": "all|filter|variants",
	"filter": { "designer": "ghamak" },
	"variant_ids": ["uuid-1"],
	"fields": ["lineage_family", "game_system"],
	"force": false
}
```
- Creates job; job type normalization_run.

GET /api/v1/normalize/status/{job_id}

## 9. Search (Full-Text / Token)
GET /api/v1/search?q=archer+forest&limit=50
- Unified search across canonical names, aliases, residual_tokens, user_tags.
- Types covered: variant, unit, part, franchise, designer.
Response includes hits by type with score.

## 10. Jobs Endpoint (Unified)
GET /api/v1/jobs?types=bulk_update,normalization_run&status=running

## 11. System / Versions
GET /api/v1/system/versions
```
{
	"success": true,
	"data": {
		"api_version": "1.0.0",
		"token_map_version": 9,
		"designers_map_version": 1,
		"codex_units_version": { "w40k": "<hash-or-date>", "aos": "<hash-or-date>", "heresy": "<hash-or-date>" },
		"parts_vocab_version": { "wargear_w40k": "<hash-or-date>", "bodies_w40k": "<hash-or-date>" },
		"schema_hash": "abc123def",
		"build_commit": "<git sha>"
	}
}
```

## 12. WebSocket / SSE (Future)
- Channel for job progress updates, candidate suggestions stream, audit tail.
- Endpoint: /api/v1/events (SSE) or /ws.

## 13. Rate Limiting (Future)
- Soft limits per key (requests/minute) with 429 response including retry_after.

## 14. Security & Validation
- Strict allowlist of editable fields; server cross-checks field catalog.
- Enum values validated against vocab tables or static sets.
- Unknown fields -> 400 invalid_field.
- Bulk operation size caps (e.g., max 50k targeted variants per job unless admin).

## 15. Versioning & Deprecation
- Path versioning (/api/v1/...).
- Backwards-compatible additions (new fields) do not increment major.
- Deprecated endpoints return Deprecation header with sunset date.
- Changes to normalization semantics -> reflected in token_map_version; clients can re-fetch schema/versions and decide to refresh caches.

## 16. Performance Notes
- GZIP compression.
- Use projection param (fields=designer,franchise,asset_category) to limit payload size.
- ETag/If-None-Match on GET variant(s) for caching.

## 17. Open API Questions
- Do we expose a batch endpoint to compute coverage for an arbitrary selection of variants to help plan an army list print queue?
- Should loadout completeness scoring weight required vs optional components differently (e.g., optional omitted still counts as complete)?
- Policy for cross-designer component compatibility (e.g., allow linking third-party weapon arms to official kit base body) — need explicit user opt-in? 
 - GraphQL overlay needed? (Maybe later for complex querying.)

---

## 2C. Variant Files & Thumbnails
Provide files associated with a variant (for the Files Sidecar/Inspector) and optional thumbnail access.

GET /api/v1/variants/{id}/files
Response example:
```
{
	"success": true,
	"data": {
		"variant_id": "uuid-1",
		"files": [
			{
				"id": "f-1",
				"rel_path": "sets/astartes/helm.stl",
				"filename": "helm.stl",
				"mime": "model/stl",
				"size_bytes": 1234567,
				"modified_at": "2025-08-16T10:10:10Z",
				"thumbnail_url": null,
				"is_primary": true
			},
			{
				"id": "f-2",
				"rel_path": "sets/astartes/readme.png",
				"filename": "readme.png",
				"mime": "image/png",
				"size_bytes": 45678,
				"modified_at": "2025-08-16T10:11:10Z",
				"thumbnail_url": "/api/v1/files/f-2/thumbnail",
				"is_primary": false
			}
		]
	}
}
```

GET /api/v1/files/{file_id}/thumbnail
- Returns a small PNG/JPEG preview if available; otherwise 404.

Notes:
- Thumbnails may be generated offline; API exposes URLs when present.
- For performance, clients can request projections (e.g., `fields=id,filename,thumbnail_url`).

## 2D. Variant Explainability
Expose tokenization and rule provenance used to produce current metadata/match decisions (for the Inspector Explain tab).

GET /api/v1/variants/{id}/explain
Response example:
```
{
	"success": true,
	"data": {
		"variant_id": "uuid-1",
		"tokens": ["intercessor", "bolt", "primaris"],
		"rules_fired": [
			{ "rule": "w40k_unit_detect", "weight": 0.6, "evidence": ["intercessor"] },
			{ "rule": "faction_astartes_alias", "weight": 0.4, "evidence": ["sm", "astartes"] }
		],
		"scores": { "unit": 0.92, "faction": 0.81 },
		"alias_provenance": [
			{ "domain": "faction", "alias": "sm", "canonical": "adeptus_astartes", "source": "token_map_v9" }
		]
	}
}
```

## 5A. Mismatch Reports
Endpoints to capture and triage user-submitted mismatches from the Inspector and process them in an Admin Inbox.

POST /api/v1/mismatch-reports
```
{
	"variant_id": "uuid-1",
	"domain": "wargames", // or display|scale_models|terrain
	"current_fields": { "system_key": "w40k", "faction_key": "adeptus_astartes" },
	"message": "Should be Grey Knights",
	"evidence_tokens": ["gk", "storm_bolter"],
	"attachments": null
}
```
Response: created report with `id`, `status` (new), timestamps.

GET /api/v1/mismatch-reports?status=new|reviewed|fixed&domain=wargames&cursor=...
Response:
```
{
	"success": true,
	"data": { "results": [ { "id": "mr-1", "variant_id": "uuid-1", "status": "new", "message": "...", "created_at": "..." } ], "next_cursor": null }
}
```

GET /api/v1/mismatch-reports/{id}
- Returns full report including snapshots and audit links.

PATCH /api/v1/mismatch-reports/{id}
```
{ "status": "reviewed", "resolution_notes": "Confirmed; will relink faction", "assigned_to": "admin" }
```

DELETE /api/v1/mismatch-reports/{id}
- Dismiss report (soft delete with audit; retains reference on variant).
- Multi-tenant isolation? (Not in scope now.)
- Delta feed for synchronization beyond audit (e.g., change stream).
- How should inferred unit↔part compatibility be exposed vs explicit `unit_part_link`? Separate endpoint (`/units/{id}/compatible-parts?inferred=true`) or flag in results?
- Do we need a `PUT /units/{id}/bundle` edit endpoint to allow atomic link updates for variants and parts in one transaction?

## 18. Sample OpenAPI Skeleton (Abbreviated)
```
openapi: 3.0.3
info:
	title: STL Manager API
	version: 1.0.0
paths:
	/api/v1/variants:
		get:
			summary: List variants
			parameters:
				- name: cursor
					in: query
					schema: { type: string }
			responses:
				'200': { description: OK }
```

---
This spec will evolve; keep business logic (normalization) internally versioned so API surface remains stable while vocab grows. Pending additions: authentication flows, full OpenAPI doc generation, SSE event schema.
