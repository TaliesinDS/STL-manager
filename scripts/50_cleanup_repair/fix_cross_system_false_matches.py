from __future__ import annotations

import argparse
import re
from typing import Optional

from db.models import Variant  # type: ignore
from db.session import get_session  # type: ignore

WORD_SEP_RE = re.compile(r"[\W_]+", re.UNICODE)

def norm_text(s: str) -> str:
    t = s.lower()
    t = t.replace("warhammer 40,000", "w40k").replace("warhammer 40k", "w40k")
    t = t.replace("age of sigmar", "aos").replace("horus heresy", "heresy").replace("30k", "heresy")
    t = WORD_SEP_RE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def system_hint(text: str) -> Optional[str]:
    t = text.lower()
    if any(k in t for k in ["w40k", "40k", "wh40k", "warhammer 40"]):
        return "w40k"
    if any(k in t for k in ["aos", "age of sigmar", "sigmar", "freeguild", "cities of sigmar"]):
        return "aos"
    if any(k in t for k in ["heresy", "30k", "horus heresy"]):
        return "heresy"
    return None


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Repair cross-system false matches by clearing codex fields when path system conflicts.")
    # DB URL is taken from STLMGR_DB_URL env var per project convention
    ap.add_argument("--ids", nargs="*", type=int, help="Variant IDs to check/fix; omit to scan all")
    ap.add_argument("--apply", action="store_true", help="Apply fixes; default is dry-run")
    args = ap.parse_args(argv)
    with get_session() as session:
        q = session.query(Variant)
        if args.ids:
            q = q.filter(Variant.id.in_(args.ids))
        count = 0
        fixed = 0
        for v in q.yield_per(200):
            count += 1
            v_text = f"{v.rel_path or ''} {v.filename or ''}"
            sys_h = system_hint(norm_text(v_text))
            vsys = (v.game_system or '').lower() if v.game_system else None
            if sys_h and vsys and sys_h != vsys:
                # Cross-system conflict: clear codex assignment conservatively
                print(f"Variant {v.id}: path suggests {sys_h} but stored system is {vsys}; clearing codex fields")
                if args.apply:
                    v.codex_unit_name = None
                    v.codex_faction = None
                    v.faction_general = None
                    v.faction_path = []
                    fixed += 1
        if args.apply:
            session.commit()
        print(f"Checked {count}; fixed {fixed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
