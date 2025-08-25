#!/usr/bin/env python3
"""Clear the `franchise` field for specified Variant IDs.

Usage:
    python scripts/clear_variant_franchise.py 66 330 331
    python scripts/clear_variant_franchise.py 66 330 331 --apply
    python scripts/clear_variant_franchise.py 309 --apply --also-character
"""
from __future__ import annotations
from pathlib import Path
import sys
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant


def main():
    import argparse
    p = argparse.ArgumentParser(description="Clear franchise on specified Variant IDs")
    p.add_argument('ids', nargs='+', type=int, help='Variant IDs to clear franchise on')
    p.add_argument('--apply', action='store_true', help='Apply changes to DB')
    p.add_argument('--also-character', action='store_true', help='Also clear character_name and character_aliases')
    args = p.parse_args()

    ids = args.ids
    results = []
    with get_session() as session:
        for vid in ids:
            v = session.query(Variant).filter_by(id=vid).one_or_none()
            if not v:
                results.append({"id": vid, "found": False})
                continue
            results.append({
                "id": vid,
                "found": True,
                "franchise": v.franchise,
                "character_name": getattr(v, 'character_name', None),
                "character_aliases": getattr(v, 'character_aliases', None),
            })

        print(json.dumps({"dry_run": not args.apply, "results": results}, indent=2, ensure_ascii=False))

        if not args.apply:
            print("Dry-run: no changes made. Rerun with --apply to clear franchise fields.")
            return 0

        # apply changes
        for vid in ids:
            v = session.query(Variant).filter_by(id=vid).one_or_none()
            if not v:
                continue
            v.franchise = None
            if args.also_character:
                v.character_name = None
                v.character_aliases = None
        # Commit with simple retry to mitigate transient 'database is locked' errors
        import time
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                session.commit()
                print("Applied: franchise cleared for specified variants.")
                break
            except Exception as e:
                if attempt == max_retries:
                    print(f"Failed to commit changes after {max_retries} attempts: {e}")
                    raise
                else:
                    print(f"Commit attempt {attempt} failed (will retry): {e}")
                    time.sleep(0.5 * attempt)


if __name__ == '__main__':
    raise SystemExit(main())
