#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path for imports
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_IDS = [66, 69, 77, 78, 79, 80, 82, 84, 85, 86, 87, 88, 89, 142, 146, 149, 150, 153, 154]


def _parse_ids(arg: str | None) -> list[int]:
    if not arg:
        return list(DEFAULT_IDS)
    out: list[int] = []
    for part in arg.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            print(f"[warn] ignoring non-integer id: {part}", file=sys.stderr)
    return out or list(DEFAULT_IDS)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify migration output by dumping selected Variants as JSON")
    ap.add_argument("--db-url", help="Database URL (overrides STLMGR_DB_URL)")
    ap.add_argument("--ids", help="Comma-separated variant IDs to dump (default: built-in selection)")
    ap.add_argument("--indent", type=int, default=2, help="JSON indent (default: 2)")
    args = ap.parse_args(argv)

    if args.db_url:
        os.environ["STLMGR_DB_URL"] = args.db_url

    from db.session import get_session  # late import to honor --db-url
    from db.models import Variant

    ids = _parse_ids(args.ids)
    out: list[dict] = []
    with get_session() as s:
        rows = s.query(Variant).filter(Variant.id.in_(ids)).all()
        for v in rows:
            out.append({
                'variant_id': v.id,
                'rel_path': v.rel_path,
                'codex_unit_name': v.codex_unit_name,
                'character_name': v.character_name,
                'character_aliases': v.character_aliases,
            })
    print(json.dumps(out, ensure_ascii=False, indent=args.indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
