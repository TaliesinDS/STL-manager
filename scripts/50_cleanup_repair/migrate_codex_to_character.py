#!/usr/bin/env python3
from __future__ import annotations

"""Migrate legacy codex_unit_name to character fields (conservative).

Dry-run by default; pass --apply to commit. Use --db-url to target a DB.
"""

import argparse
import json
import os


def find_candidates(session):
    from db.models import Variant
    return (
        session.query(Variant)
        .filter(
            Variant.codex_unit_name.isnot(None),
            Variant.codex_unit_name != "",
            (Variant.character_name.is_(None) | (Variant.character_name == "")),
        )
        .all()
    )


def apply_migration(apply: bool, force: bool):
    from db.models import Variant
    from db.session import get_session

    proposals = []
    with get_session() as session:
        rows = find_candidates(session)
        for v in rows:
            prop = {
                "variant_id": v.id,
                "rel_path": v.rel_path,
                "from_codex_unit_name": v.codex_unit_name,
                "proposed": {"character_name": v.codex_unit_name, "character_aliases": []},
            }
            proposals.append(prop)

        print(f"Found {len(proposals)} variants with non-empty codex_unit_name and empty character_name.")
        for p in proposals[:200]:
            print(json.dumps(p, ensure_ascii=False))

        if apply and proposals:
            print("Applying migration...")
            any_changed = False
            for p in proposals:
                v = session.query(Variant).filter_by(id=p["variant_id"]).one_or_none()
                if not v:
                    continue
                if (v.character_name in (None, "")) or force:
                    v.character_name = p["proposed"]["character_name"]
                    v.character_aliases = p["proposed"]["character_aliases"]
                    any_changed = True
            if any_changed:
                session.commit()
                print(f"Applied migration to {len(proposals)} variants.")
            else:
                print("No changes applied (nothing met criteria).")
    return proposals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-url", help="Database URL (overrides STLMGR_DB_URL)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    if args.db_url:
        os.environ["STLMGR_DB_URL"] = args.db_url

    apply_migration(apply=args.apply, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
