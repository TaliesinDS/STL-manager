#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session
from db.models import Variant
from scripts.30_normalize_match.normalize_inventory import classify_tokens, build_designer_alias_map  # type: ignore[attr-defined]
from scripts.quick_scan import tokenize


def inspect(vids: list[int]) -> None:
    with get_session() as session:
        designer_map = build_designer_alias_map(session)
        for vid in vids:
            v = session.query(Variant).get(vid)
            if not v:
                print(f"Variant {vid} not found")
                continue
            toks: list[str] = []
            try:
                toks += tokenize(Path(v.rel_path))
            except Exception:
                pass
            if v.filename:
                toks += tokenize(Path(v.filename))
            for f in getattr(v, 'files', []) or []:
                toks += tokenize(Path(f.filename or ''))
                toks += tokenize(Path(f.rel_path or ''))
            seen = set(); uniq: list[str] = []
            for t in toks:
                if t in seen:
                    continue
                seen.add(t); uniq.append(t)
            inferred = classify_tokens(uniq, designer_map)
            print(json.dumps({"variant_id": vid, "tokens": uniq, "inferred": inferred}, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    argv = argv or []
    if not argv:
        print('Usage: inspect_inference.py <variant_id> [ids..]')
        return 2
    ids = [int(x) for x in argv]
    inspect(ids)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
