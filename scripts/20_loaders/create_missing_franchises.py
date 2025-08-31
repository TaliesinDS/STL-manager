#!/usr/bin/env python3
"""Create VocabEntry rows for franchise keys present on Variants but missing
from the `vocab_entry` table (domain='franchise').

Dry-run by default; use `--apply` to insert missing rows.
"""
from __future__ import annotations

from pathlib import Path
import sys
import argparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import VocabEntry, Variant


def find_missing_franchises(session):
    # collect distinct non-null franchise keys from variants
    rows = session.query(Variant.franchise).distinct().all()
    variant_keys = {r[0] for r in rows if r and isinstance(r[0], str) and r[0].strip()}

    # collect existing vocab franchise keys
    vrows = session.query(VocabEntry).filter_by(domain='franchise').all()
    existing = {v.key for v in vrows}

    missing = sorted(k for k in variant_keys if k not in existing)
    return missing, existing


def process(apply: bool):
    with get_session() as session:
        missing, _ = find_missing_franchises(session)
        print(f"Found {len(missing)} missing franchise keys (variants reference them but no VocabEntry exists).")
        if missing:
            print("Missing keys:")
            for k in missing:
                print(f"  - {k}")

        if apply and missing:
            created = []
            for k in missing:
                ve = VocabEntry(domain='franchise', key=k, aliases=[], meta={'auto_created_from': 'variant'})
                session.add(ve)
                created.append(k)
            session.commit()
            print(f"Created {len(created)} VocabEntry rows for franchises.")
        elif not apply:
            print("Dry-run: no changes made. Use --apply to create VocabEntry rows.")


def parse_args(argv):
    ap = argparse.ArgumentParser(description='Create missing franchise VocabEntry rows')
    ap.add_argument('--apply', action='store_true', help='Create missing VocabEntry rows')
    return ap.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    process(apply=args.apply)


if __name__ == '__main__':
    import sys as _sys
    raise SystemExit(main(_sys.argv[1:]))
