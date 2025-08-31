#!/usr/bin/env python3
from __future__ import annotations

"""Repair Cities of Sigmar variants (targeted, idempotent).

Dry-run by default; pass --apply to commit. Use --db-url to target a DB.
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TARGET_IDS = [232, 233, 235, 236, 259, 260, 261, 263, 264, 265, 269]
CORRECT_FRANCHISE = "warhammer_age_of_sigmar"
CORRECT_FACTION = "cities_of_sigmar"


def process(ids, apply: bool):
    from db.session import get_session
    from db.models import Variant

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

            if orig_fr != to_set_franchise or orig_faction != to_set_faction or orig_codex == "zero_two":
                print(
                    f"Proposed fix Variant {vid}: franchise {orig_fr} -> {to_set_franchise}, faction {orig_faction} -> {to_set_faction}"
                )
                if apply:
                    v.franchise = to_set_franchise
                    v.faction_general = to_set_faction
                    if v.codex_unit_name == "zero_two":
                        v.codex_unit_name = None
                    curw = v.normalization_warnings or []
                    if "franchise_corrected_manual" not in curw:
                        curw = list(curw) + ["franchise_corrected_manual"]
                    v.normalization_warnings = curw
                    session.commit()
                    print(f"Applied fix to Variant {vid}")
                    changed.append(vid)
            else:
                print(f"Variant {vid} already appears correct; skipping")

    print(f"Done. Applied to {len(changed)} variants.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Repair Cities of Sigmar variants")
    ap.add_argument("--db-url", help="Database URL (overrides STLMGR_DB_URL)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--ids", nargs="+", type=int, help="Override target ids")
    args = ap.parse_args(argv)

    if args.db_url:
        os.environ["STLMGR_DB_URL"] = args.db_url

    ids = args.ids or TARGET_IDS
    process(ids, apply=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
