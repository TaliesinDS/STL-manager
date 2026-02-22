#!/usr/bin/env python3
"""Inspect token frequencies for files attached to a Variant and print a JSON summary."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from db.models import Variant
from db.session import get_session
from scripts.quick_scan import tokenize


def inspect_variant(variant_id: int) -> dict:
    with get_session() as session:
        v = session.query(Variant).get(variant_id)
        if not v:
            raise SystemExit(f"Variant {variant_id} not found")

        files = list(v.files or [])
        tok_counter = Counter()
        for f in files:
            src = (f.rel_path or "") or (f.filename or "")
            try:
                toks = tokenize(Path(src))
            except Exception:
                toks = []
            tok_counter.update(toks)

        most_common = tok_counter.most_common(60)
        return {
            "variant_id": variant_id,
            "rel_path": v.rel_path,
            "file_count": len(files),
            "top_tokens": most_common,
        }


def main(argv: list[str] | None = None) -> int:
    argv = argv or []
    if not argv:
        print("Usage: inspect_orphan_tokens.py <variant_id>")
        return 2
    vid = int(argv[0])
    out = inspect_variant(vid)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
