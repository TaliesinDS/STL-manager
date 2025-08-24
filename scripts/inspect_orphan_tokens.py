#!/usr/bin/env python3
"""Inspect token frequencies for files attached to a Variant.

Usage:
  .venv\Scripts\python.exe scripts\inspect_orphan_tokens.py 492

Prints JSON with total file count and top token frequencies from filenames and rel_paths.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant, File
from scripts.quick_scan import tokenize


def inspect_variant(variant_id: int):
    with get_session() as session:
        v = session.query(Variant).get(variant_id)
        if not v:
            raise SystemExit(f"Variant {variant_id} not found")

        files = list(v.files or [])
        total = len(files)
        tok_counter = Counter()
        for f in files:
            # prefer rel_path then filename
            src = (f.rel_path or '') or (f.filename or '')
            try:
                toks = tokenize(Path(src))
            except Exception:
                toks = []
            tok_counter.update(toks)

        most_common = tok_counter.most_common(60)
        out = {
            'variant_id': variant_id,
            'rel_path': v.rel_path,
            'file_count': total,
            'top_tokens': most_common,
        }
        print(json.dumps(out, indent=2))


def main(argv):
    if not argv:
        raise SystemExit('Usage: inspect_orphan_tokens.py <variant_id>')
    vid = int(argv[0])
    inspect_variant(vid)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
