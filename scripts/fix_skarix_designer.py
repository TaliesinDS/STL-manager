#!/usr/bin/env python3
"""Find and optionally fix mistaken 'skarix' designer entries.

Usage:
  python scripts/fix_skarix_designer.py       # dry-run, shows matches
  python scripts/fix_skarix_designer.py --apply  # delete vocab entries and clear variant.designer
"""
from __future__ import annotations
from pathlib import Path
import sys
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import VocabEntry, Variant


def normalize_alias(a: str) -> str:
    return a.strip().lower()


def find_designer_vocab_matches(session, target: str = "skarix") -> list[VocabEntry]:
    rows = session.query(VocabEntry).filter_by(domain="designer").all()
    return [
        r
        for r in rows
        if normalize_alias(r.key or "") == target
        or target in [normalize_alias(x) for x in (r.aliases or [])]
    ]


def find_variants_with_designer(session, target: str = "skarix") -> list[Variant]:
    return [
        v
        for v in session.query(Variant).filter(Variant.designer.isnot(None)).all()
        if normalize_alias(str(v.designer)) == target
    ]


def pretty_variant(v: Variant) -> dict:
    return {
        "id": v.id,
        "rel_path": v.rel_path,
        "designer": v.designer,
        "residual_tokens": v.residual_tokens,
    }


def main():
    import argparse
    p = argparse.ArgumentParser(description="Find and optionally fix 'skarix' designer entries")
    p.add_argument("--apply", action="store_true", help="Apply fixes: delete vocab entries and clear designer on variants")
    args = p.parse_args()

    target = "skarix"
    with get_session() as session:
        ve_matches = find_designer_vocab_matches(session, target=target)
        var_matches = find_variants_with_designer(session, target=target)

        print(json.dumps({
            "vocab_matches": [{"id": ve.id, "key": ve.key, "aliases": ve.aliases} for ve in ve_matches],
            "variant_matches_count": len(var_matches),
            "variant_matches_sample": [pretty_variant(v) for v in var_matches[:20]]
        }, indent=2, ensure_ascii=False))

        if not args.apply:
            print("Dry-run: no changes made. Rerun with --apply to remove the bad vocab entries and clear variant.designer for matches.")
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


if __name__ == '__main__':
    raise SystemExit(main())
