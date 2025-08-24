#!/usr/bin/env python3
"""Migrate legacy codex_unit_name values into the new character fields.

Conservative default: dry-run (prints proposals). Use `--apply` to commit.
Only copies when `character_name` is empty unless `--force` is used.
"""
from __future__ import annotations
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session
from db.models import Variant


def find_candidates(session):
    # Variants with a codex_unit_name but no character_name
    rows = session.query(Variant).filter(Variant.codex_unit_name.isnot(None), Variant.codex_unit_name != '', (Variant.character_name.is_(None) | (Variant.character_name == ''))).all()
    return rows


def apply_migration(apply: bool, force: bool):
    proposals = []
    with get_session() as session:
        rows = find_candidates(session)
        for v in rows:
            prop = {'variant_id': v.id, 'rel_path': v.rel_path, 'from_codex_unit_name': v.codex_unit_name}
            # propose copying codex_unit_name to character_name
            prop['proposed'] = {'character_name': v.codex_unit_name, 'character_aliases': []}
            proposals.append(prop)

        print(f"Found {len(proposals)} variants with non-empty codex_unit_name and empty character_name.")
        for p in proposals[:200]:
            print(json.dumps(p, ensure_ascii=False))

        if apply and proposals:
            print('Applying migration...')
            any_changed = False
            for p in proposals:
                v = session.query(Variant).filter_by(id=p['variant_id']).one_or_none()
                if not v:
                    continue
                # only set if empty or force
                if (v.character_name in (None, '')) or force:
                    v.character_name = p['proposed']['character_name']
                    v.character_aliases = p['proposed']['character_aliases']
                    any_changed = True
            if any_changed:
                session.commit()
                print(f'Applied migration to {len(proposals)} variants.')
            else:
                print('No changes applied (nothing met criteria).')

    return proposals


def parse_args(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--force', action='store_true')
    return ap.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    apply_migration(apply=args.apply, force=args.force)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
