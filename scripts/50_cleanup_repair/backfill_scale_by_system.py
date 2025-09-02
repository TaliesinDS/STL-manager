from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Dict
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session  # type: ignore
from db.models import Variant  # type: ignore

SYSTEM_DEFAULT_SCALE_DEN: Dict[str, int] = {
    "w40k": 56,
    "aos": 56,
    "heresy": 56,
    "old_world": 56,
}

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Backfill scale_ratio_den by system (1:den). Defaults AoS/W40K/Heresy/Old World to 56.")
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
            if getattr(v, 'scale_ratio_den', None):
                continue
            sys_key = getattr(v, 'game_system', None)
            den = SYSTEM_DEFAULT_SCALE_DEN.get(sys_key or "") if sys_key else None
            if den:
                print(f"Variant {v.id}: backfill scale_ratio_den -> {den} (system={sys_key})")
                if args.apply:
                    v.scale_ratio_den = den
                    changed += 1
        if args.apply and changed:
            session.commit()
        print(f"Checked {total}; updated {changed}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
