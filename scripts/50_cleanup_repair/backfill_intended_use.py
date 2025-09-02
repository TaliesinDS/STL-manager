from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session  # type: ignore
from db.models import Variant  # type: ignore


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Backfill intended_use_bucket to 'tabletop_intent' where system/faction exists but intended_use is NULL.")
    ap.add_argument("--ids", nargs="*", type=int, help="Variant IDs to check/fix; omit to scan all")
    ap.add_argument("--apply", action="store_true", help="Apply fixes; default is dry-run")
    args = ap.parse_args(argv)

    with get_session() as session:
        q = session.query(Variant)
        if args.ids:
            q = q.filter(Variant.id.in_(args.ids))
        total = 0
        changed = 0
        for v in q.yield_per(200):
            total += 1
            if getattr(v, 'intended_use_bucket', None):
                continue
            has_tabletop_signal = bool(
                getattr(v, 'game_system', None)
                or getattr(v, 'codex_faction', None)
                or getattr(v, 'faction_general', None)
            )
            if has_tabletop_signal:
                print(f"Variant {v.id}: backfill intended_use_bucket -> tabletop_intent")
                if args.apply:
                    v.intended_use_bucket = 'tabletop_intent'
                    changed += 1
        if args.apply and changed:
            session.commit()
        print(f"Checked {total}; updated {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
