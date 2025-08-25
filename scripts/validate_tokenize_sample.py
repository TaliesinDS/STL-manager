#!/usr/bin/env python3
"""Validate tokenizer behavior for sample paths.

Usage:
  .venv\Scripts\python.exe scripts\validate_tokenize_sample.py
  .venv\Scripts\python.exe scripts\validate_tokenize_sample.py "path1" "path2"

This script imports `tokenize` from `scripts.quick_scan` and prints token lists
for one or more sample paths so you can verify directory components are
included in tokenization (e.g., artist/store names, character names).
"""
from __future__ import annotations
import sys
from pathlib import Path
import sys
from pathlib import Path as _P
# Ensure project root is on sys.path so 'scripts' package is importable when run from repo root
PROJECT_ROOT = _P(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from scripts.quick_scan import tokenize


def main(argv: list[str]) -> int:
    samples = argv[1:] if len(argv) > 1 else [r"sample_store\[Gaz minis] Ryuko Matoi +NSFW\KLK\model.stl"]
    for s in samples:
        p = Path(s)
        toks = tokenize(p)
        print(f"Path: {s}")
        print("Tokens:", toks)
        print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
