#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant
import json

def show(ids: list[int]):
    with get_session() as session:
        for vid in ids:
            v = session.query(Variant).get(vid)
            if not v:
                print(f"Variant id={vid} not found")
                continue
            raw = {c.name: getattr(v, c.name) for c in v.__table__.columns}
            data = {}
            for k, val in raw.items():
                try:
                    json.dumps(val)
                    data[k] = val
                except Exception:
                    data[k] = str(val)
            print(json.dumps({"variant_id": vid, "data": data}, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/show_variant.py <id> [id2 ...]")
        raise SystemExit(2)
    ids = [int(x) for x in sys.argv[1:]]
    show(ids)
