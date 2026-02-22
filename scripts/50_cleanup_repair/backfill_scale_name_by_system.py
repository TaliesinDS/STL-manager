from __future__ import annotations

import argparse
from typing import Dict, Optional

from db.models import GameSystem, Variant  # type: ignore
from db.session import get_session  # type: ignore

SYSTEM_DEFAULT_SCALE_DEN: Dict[str, int] = {"w40k": 56, "aos": 56, "heresy": 56, "old_world": 56}
SYSTEM_DEFAULT_SCALE_NAME: Dict[str, str] = {"w40k": "28mm heroic", "aos": "28mm heroic", "heresy": "28mm heroic", "old_world": "28mm heroic"}

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Backfill scale fields (den and name) on Variants by system.")
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
            sys_key = getattr(v, 'game_system', None)
            if not sys_key:
                continue
            gs = session.query(GameSystem).filter(GameSystem.key == sys_key).first()
            den = (getattr(gs, 'default_scale_den', None) if gs else None) or SYSTEM_DEFAULT_SCALE_DEN.get(sys_key)
            sname = (getattr(gs, 'default_scale_name', None) if gs else None) or SYSTEM_DEFAULT_SCALE_NAME.get(sys_key)
            will = False
            if den and not getattr(v, 'scale_ratio_den', None):
                print(f"Variant {v.id}: scale_ratio_den -> {den}")
                if args.apply:
                    v.scale_ratio_den = den
                    will = True
            if sname and not getattr(v, 'scale_name', None):
                print(f"Variant {v.id}: scale_name -> {sname}")
                if args.apply:
                    v.scale_name = sname
                    will = True
            if will:
                changed += 1
        if args.apply and changed:
            session.commit()
        print(f"Checked {total}; updated {changed}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
