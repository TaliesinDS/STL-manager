Planning Log
Dataset Snapshot (2025-08-15)
Unprocessed archives: ~5k (RAR/ZIP), ~2 TB
Extracted & partially ordered: ~96k files, ~2.6 TB
Formats: STL, OBJ, other meshes, presupported slicer project files, preview images, marketing extras
Deep nesting (some >260 char paths), nested archives
Stored on dedicated HDD
Guiding Principles
Inventory before mutation.
Sample before bulk extraction.
Keep raw model binaries outside Git (for now).
Small, verifiable steps.
Ask before increasing complexity.
Upcoming Steps
Step 1: Baseline repository files (this commit).
Step 2: Define inventory script specification.
Step 3: Implement scan (no hashes).
Step 4: Add hashing (SHA256).
Step 5: Add basic extension classification and mesh flag.
Open Questions

Exact directory roots naming.
Whether to store relative or absolute paths in inventory.
CSV vs JSON primary artifact.
DECISIONS.md

---
## Future Application UI Requirements (Draft)

Purpose: Capture early high-level requirements for the eventual interactive app so current schema / vocab design stays compatible.

Core Capabilities:
- Global faceted browse: filter by designer, franchise, lineage_family, asset_category, game_system, codex_faction, content_flag, nsfw_level (later), scale, style_primary, addon flags.
- Full-text / token search across canonical names, aliases, residual_tokens (indexed).
- Sorting: name, designer, franchise, updated_at, size, scale, confidence_score (later), recently added.
- Incremental ingestion: new download folder scan inserts variants (unclassified fields NULL) without blocking UI.
- Residual token surfacing: panel for high-frequency unknown tokens (suggest new vocab values).

Editable Metadata (All Fields):
- Every metadata field in `MetadataFields.md` editable via UI unless explicitly derived-only.
- Derived-but-overridable pattern: store manual override separately (variant_field_override) preserving original auto value.
- Bulk edit wizard: multi-step (filter -> preview -> operations -> confirm) with batch audit entry.
- Inline quick edit for common scalars (designer, franchise, game_system).
- Tag-style editors for arrays (compatible_units, auto_tags, lineage_aliases (display only), user_tags).

Dynamic Vocabulary Management:
- Add new vocab entries (franchise, lineage_primary, faction, vehicle_era, terrain_subtype, base_theme, designer) directly from filter inputs when missing.
- Franchise/Designer add modal auto-suggests canonical snake_case & seeds initial alias.
- Candidate suggestions table (e.g., unknown tokens clustered) -> one-click promote to vocab.
- Alias collision validator warns if new alias already maps elsewhere.

Audit & History:
- Audit log per variant & vocab entry (field, old_value, new_value, user, timestamp, source=auto|manual|backfill).
- Revert single change or entire bulk batch.
- Show override badge + tooltip with original auto-derived value.

Bulk Operations:
- Operations: set, clear, add_to_array, remove_from_array.
- Dry-run count before execution; queue asynchronous job with progress indicator for large sets.

Normalization Re-run:
- After vocab addition or alias edit: enqueue light re-normalization for impacted variants only (based on residual token index).
- Skip overwriting any field that has a manual override.

Performance / Indexing:
- B-tree indexes on high-selectivity scalar filters (designer_id, franchise_id, lineage_family, asset_category, game_system, content_flag, scale_ratio_den, style_primary).
- GIN indexes for array / token fields (residual_tokens, user_tags, auto_tags).

Permissions (Future-Proofing):
- Roles: admin (all), curator (edit + vocab), viewer (read-only).
- Field catalog (machine-readable) drives UI form generation + access control.

API Endpoint Sketch:
- GET /schema/fields -> field metadata (type, phase, editable, overrideAllowed).
- GET /variants?q=...&filters=... -> paginated browse.
- GET /variants/{id}
- PATCH /variants/{id}
- POST /bulk/variants/update
- GET /vocab/{domain}?q=...
- POST /vocab/{domain}
- PATCH /vocab/{domain}/{id}
- GET /suggestions (candidate vocab tokens)
- POST /overrides/clear (remove override for field(s)).
- GET /audit/variant/{id}

UI Components (Planned):
- FacetSidebar, VariantGrid/Table Toggle, VariantDetailDrawer, EditFieldModal, BulkEditWizard, VocabAddModal, SuggestionsPanel, AuditTimeline, OverrideBadge, TokenDiffView, ProgressJobToast.

Open UI Questions:
- Conflict visualization strategy (e.g., lineage vs faction mismatch) – inline badges vs side panel.
- Batch undo granularity: single large transaction vs per-row revert loop.
- Threshold for auto-suggesting candidate franchise (min frequency?).
- Strategy for ephemeral experimental vocab (mark as provisional?).

---

Decisions
2025-08-15: Created separate repo (STL-manager) to isolate code/planning from blog and avoid large binary history. 2025-08-15: Phase 0 limited to read-only inventory of already extracted files; archives untouched. (Add each new decision with date + rationale.)

.gitignore pycache/ .pyc .env .env. .vscode/ .idea/ .venv/ build/ dist/ notes/

Optional future patterns (uncomment if you choose to exclude)
*.stl
*.obj
*.zip
*.rar
scripts/ Add an empty scripts folder (you can drop a .gitkeep file inside if needed).