#!/usr/bin/env python3
"""Set `Variant.franchise` for specific variant IDs in a conservative way.

Dry-run by default; use `--apply` to write. Will only set the field when
empty unless `--force` is supplied. Adds a normalization warning
`franchise_assigned_manual` when applied.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant


def process(ids: list[int], franchise: str, apply: bool, force: bool) -> int:
    changed: list[int] = []
    with get_session() as session:
        for vid in ids:
            v = session.query(Variant).filter_by(id=vid).one_or_none()
            if not v:
                print(f"Variant {vid} not found; skipping")
                continue
            cur = v.franchise
            will_set = False
            if cur in (None, "") or force:
                will_set = True
            if not will_set:
                print(f"Variant {vid} already has franchise='{cur}'; use --force to overwrite")
                continue

            print(f"Proposed: set Variant {vid} franchise -> '{franchise}' (current: {cur})")
            print(f"  rel_path: {v.rel_path}")
            if apply:
                v.franchise = franchise
                curw = v.normalization_warnings or []
                if 'franchise_assigned_manual' not in curw:
                    curw = list(curw) + ['franchise_assigned_manual']
                v.normalization_warnings = curw
                session.commit()
                print(f"Applied: Variant {vid} franchise set to '{franchise}'")
                changed.append(vid)

    print(f"Done. Applied to {len(changed)} variants.")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description='Set franchise on variant ids')
    ap.add_argument('--ids', nargs='+', type=int, required=True, help='Variant IDs to update')
    ap.add_argument('--franchise', required=True, help='Franchise key to set')
    ap.add_argument('--apply', action='store_true', help='Write changes to DB')
    ap.add_argument('--force', action='store_true', help='Overwrite existing franchise')
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    return process(ids=args.ids, franchise=args.franchise, apply=args.apply, force=args.force)


if __name__ == '__main__':
    import sys as _sys
    raise SystemExit(main(_sys.argv[1:]))
