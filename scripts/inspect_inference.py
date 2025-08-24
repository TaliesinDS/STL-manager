#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant
from scripts.quick_scan import tokenize, load_tokenmap
from scripts.normalize_inventory import classify_tokens, build_designer_alias_map

def inspect(vids: list[int]):
    with get_session() as session:
        designer_map = build_designer_alias_map(session)
        for vid in vids:
            v = session.query(Variant).get(vid)
            if not v:
                print(f"Variant {vid} not found")
                continue
            toks = []
            try:
                toks += tokenize(Path(v.rel_path))
            except Exception:
                pass
            if v.filename:
                toks += tokenize(Path(v.filename))
            for f in getattr(v, 'files', []):
                toks += tokenize(Path(f.filename or ''))
                toks += tokenize(Path(f.rel_path or ''))
            # dedupe
            seen = set(); uniq = []
            for t in toks:
                if t in seen: continue
                seen.add(t); uniq.append(t)
            inferred = classify_tokens(uniq, designer_map)
            print(json.dumps({"variant_id": vid, "tokens": uniq, "inferred": inferred}, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python scripts/inspect_inference.py <variant_id> [ids..]')
        raise SystemExit(2)
    ids = [int(x) for x in sys.argv[1:]]
    inspect(ids)
