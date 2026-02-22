#!/usr/bin/env python3
from __future__ import annotations

"""Find and optionally fix mistaken 'skarix' designer entries.

Dry-run by default; pass --apply to commit. Use --db-url to target a DB.
"""

import argparse
import json
import os


def normalize_alias(a: str) -> str:
    return a.strip().lower()


def find_designer_vocab_matches(session, target: str = "skarix"):
    from db.models import VocabEntry
    rows = session.query(VocabEntry).filter_by(domain="designer").all()
    return [
        r
        for r in rows
        if normalize_alias(r.key or "") == target
        or target in [normalize_alias(x) for x in (r.aliases or [])]
    ]


def find_variants_with_designer(session, target: str = "skarix"):
    from db.models import Variant
    return [
        v
        for v in session.query(Variant).filter(Variant.designer.isnot(None)).all()
        if normalize_alias(str(v.designer)) == target
    ]


def pretty_variant(v):
    return {
        "id": v.id,
        "rel_path": v.rel_path,
        "designer": v.designer,
        "residual_tokens": v.residual_tokens,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Find and optionally fix 'skarix' designer entries")
    ap.add_argument("--db-url", help="Database URL (overrides STLMGR_DB_URL)")
    ap.add_argument("--apply", action="store_true", help="Apply fixes: delete vocab entries and clear designer on variants")
    args = ap.parse_args(argv)

    if args.db_url:
        os.environ["STLMGR_DB_URL"] = args.db_url

    from db.session import get_session  # late import to honor --db-url

    target = "skarix"
    with get_session() as session:
        ve_matches = find_designer_vocab_matches(session, target=target)
        var_matches = find_variants_with_designer(session, target=target)

        print(
            json.dumps(
                {
                    "vocab_matches": [{"id": ve.id, "key": ve.key, "aliases": ve.aliases} for ve in ve_matches],
                    "variant_matches_count": len(var_matches),
                    "variant_matches_sample": [pretty_variant(v) for v in var_matches[:20]],
                },
                indent=2,
                ensure_ascii=False,
            )
        )

        if not args.apply:
            print(
                "Dry-run: no changes made. Rerun with --apply to remove the bad vocab entries and clear variant.designer for matches."
            )
            return 0

        # Apply fixes
        if not ve_matches and not var_matches:
            print("Nothing to do.")
            return 0

        print("Applying fixes: deleting vocab entries and clearing designer on matching variants...")
        for v in var_matches:
            v.designer = None
        for ve in ve_matches:
            session.delete(ve)
        session.commit()
        print("Apply complete. Deleted entries and cleared designer on matched variants.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
