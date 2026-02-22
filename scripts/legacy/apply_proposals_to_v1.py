"""Apply folder-path-derived franchise proposals into data/stl_manager_v1.db (guarded).

Behavior:
- Reads `match_proposals_v3.json` (expected in repo root).
- For each proposal, if `proposed.franchise` is present and `proposed.franchise_token` is a substring
  of the Variant.rel_path (case-insensitive), and the Variant.franchise is empty/null in v1 DB,
  then set Variant.franchise to the proposed value and write an AuditLog row.
- Skips proposals where the variant already has a franchise (records as conflict).
- Makes no other changes.

Run from repo root with the project venv active (the script sets the DB URL to v1 before importing
project session/models so it connects to the correct SQLite file).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Dict, Any

# Ensure we point at the canonical DB before importing project modules
os.environ["STLMGR_DB_URL"] = os.environ.get("STLMGR_DB_URL", "sqlite:///./data/stl_manager_v1.db")

# Import project DB helpers
try:
    from db.session import get_session
    from db.models import Variant, AuditLog
except Exception as e:
    print("Failed to import project modules. Are you running from the repo root with venv active?", file=sys.stderr)
    raise

ROOT = os.path.abspath(os.path.dirname(__file__) + "\..")
PROPOSAL_FILE = os.path.join(ROOT, "match_proposals_v3.json")


def load_json_robust(path: str) -> Dict[str, Any]:
    text = open(path, "r", encoding="utf-8").read()
    # Try normal parse first
    try:
        return json.loads(text)
    except Exception:
        # Fallback: extract first {...} block
        first = text.find("{")
        last = text.rfind("}")
        if first == -1 or last == -1 or last <= first:
            raise
        return json.loads(text[first:last + 1])


if __name__ == "__main__":
    if not os.path.exists(PROPOSAL_FILE):
        print(f"Proposals file not found: {PROPOSAL_FILE}")
        sys.exit(2)

    data = load_json_robust(PROPOSAL_FILE)
    proposals = data.get("proposals", [])

    applied = []
    skipped_no_variant = []
    skipped_has_franchise = []
    skipped_token_mismatch = []

    with get_session() as session:
        for p in proposals:
            vid = p.get("variant_id")
            proposed = p.get("proposed", {})
            prop_fr = proposed.get("franchise")
            token = proposed.get("franchise_token")

            if not prop_fr or not token:
                # Nothing relevant to apply
                skipped_token_mismatch.append((vid, "no_proposed_fr_or_token"))
                continue

            v: Variant = session.get(Variant, vid)
            if not v:
                skipped_no_variant.append(vid)
                continue

            # Heuristic: only apply if the franchise_token appears in the rel_path (folder path)
            rel = (v.rel_path or "").lower()
            if token.lower() not in rel:
                skipped_token_mismatch.append((vid, token, v.rel_path))
                continue

            current = (v.franchise or "").strip()
            if current:
                # Do not overwrite existing franchise
                skipped_has_franchise.append((vid, current, prop_fr))
                continue

            # Apply change
            old_value = None
            v.franchise = prop_fr
            # Create audit log entry
            log = AuditLog(
                resource_type="variant",
                resource_id=vid,
                field="franchise",
                old_value=None,
                new_value=prop_fr,
                actor="apply_proposals_to_v1",
            )
            session.add(log)
            applied.append((vid, prop_fr, token, v.rel_path))

        # Commit once at end
        session.commit()

    # Report
    print(f"Proposals processed: {len(proposals)}")
    print(f"Applied: {len(applied)}")
    if applied:
        for a in applied:
            print(f"  - variant {a[0]} -> franchise={a[1]} (token={a[2]}) path={a[3]}")
    if skipped_no_variant:
        print(f"Skipped (missing variant): {len(skipped_no_variant)}")
    if skipped_has_franchise:
        print(f"Skipped (already has franchise): {len(skipped_has_franchise)}")
    if skipped_token_mismatch:
        print(f"Skipped (token not in rel_path or missing): {len(skipped_token_mismatch)}")

    print("Done.")
