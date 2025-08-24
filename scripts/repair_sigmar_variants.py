#!/usr/bin/env python3
"""Repair a set of variants to correct franchise/faction metadata for
Cities of Sigmar (Warhammer Age of Sigmar).

This script is targeted and idempotent: it updates only the specified
variant ids and records a normalization warning. Dry-run by default; use
`--apply` to commit changes.
"""
from __future__ import annotations

from pathlib import Path
import sys
import argparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant


TARGET_IDS = [232,233,235,236,259,260,261,263,264,265,269]
CORRECT_FRANCHISE = 'warhammer_age_of_sigmar'
CORRECT_FACTION = 'cities_of_sigmar'


def process(ids, apply: bool):
    changed = []
    with get_session() as session:
        for vid in ids:
            v = session.query(Variant).filter_by(id=vid).one_or_none()
            if not v:
                print(f"Variant {vid} not found; skipping")
                continue
            orig_fr = v.franchise
            orig_faction = v.faction_general
            orig_codex = v.codex_unit_name

            to_set_franchise = CORRECT_FRANCHISE
            to_set_faction = CORRECT_FACTION

            # Decide whether to change: change if current franchise looks wrong
            if orig_fr != to_set_franchise or orig_faction != to_set_faction or orig_codex == 'zero_two':
                print(f"Proposed fix Variant {vid}: franchise {orig_fr} -> {to_set_franchise}, faction {orig_faction} -> {to_set_faction}")
                if apply:
                    v.franchise = to_set_franchise
                    v.faction_general = to_set_faction
                    # remove incorrect codex_unit_name if it was zero_two
                    if v.codex_unit_name == 'zero_two':
                        v.codex_unit_name = None
                    curw = v.normalization_warnings or []
                    if 'franchise_corrected_manual' not in curw:
                        curw = list(curw) + ['franchise_corrected_manual']
                    v.normalization_warnings = curw
                    session.commit()
                    print(f"Applied fix to Variant {vid}")
                    changed.append(vid)
            else:
                print(f"Variant {vid} already appears correct; skipping")

    print(f"Done. Applied to {len(changed)} variants.")


def parse_args(argv):
    ap = argparse.ArgumentParser(description='Repair Cities of Sigmar variants')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--ids', nargs='+', type=int, help='Override target ids')
    return ap.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    ids = args.ids or TARGET_IDS
    process(ids, apply=args.apply)


if __name__ == '__main__':
    import sys as _sys
    raise SystemExit(main(_sys.argv[1:]))
