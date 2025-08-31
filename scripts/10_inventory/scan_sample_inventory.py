#!/usr/bin/env python3
"""Scan sample inventory JSON and report tokens captured only when tokenizing
directory components (i.e., tokens that were previously omitted when only
tokenizing Path.stem).

Usage:
  .venv\Scripts\python.exe scripts\10_inventory\scan_sample_inventory.py
"""
from __future__ import annotations
import sys
import json
from pathlib import Path

# Ensure project root importability
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # repo root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.quick_scan import tokenize


def tokenize_stem(path: str) -> list[str]:
    """Emulate the old behavior that only tokenized Path.stem."""
    p = Path(path)
    stem = p.stem.lower()
    # reuse split logic from quick_scan but simplified
    import re
    SPLIT_CHARS = re.compile(r"[\s_\-]+")
    parts = SPLIT_CHARS.split(stem)
    out: list[str] = []
    for part in parts:
        part = part.strip()
        if not part or len(part) < 2:
            continue
        part = part.strip("()[]{}+")
        if part.startswith('@'):
            part = part[1:]
        if part.endswith('.stl'):
            part = part[:-4]
        if not part or len(part) < 2:
            continue
        out.append(part)
    return out


def main(argv: list[str]) -> int:
    fixture = PROJECT_ROOT / 'tests' / 'fixtures' / 'sample_inventory.json'
    if not fixture.exists():
        print("sample_inventory.json not found at tests/fixtures; nothing to scan.")
        return 2
    data = json.loads(fixture.read_text(encoding='utf-8'))
    rels = [r.get('rel_path') for r in data if r.get('rel_path')]

    full_tokens = set()
    stem_tokens = set()
    per_row_new = []
    for rp in rels:
        toks_full = set(tokenize(Path(rp)))
        toks_stem = set(tokenize_stem(rp))
        full_tokens.update(toks_full)
        stem_tokens.update(toks_stem)
        new = sorted(toks_full - toks_stem)
        if new:
            per_row_new.append({'rel_path': rp, 'new_tokens': new})

    only_in_full = sorted(full_tokens - stem_tokens)

    print(f"Total rel_path rows scanned: {len(rels)}")
    print(f"Unique tokens (full path): {len(full_tokens)}")
    print(f"Unique tokens (stem-only): {len(stem_tokens)}")
    print("\nTokens captured only when tokenizing full path (directory components):")
    for t in only_in_full:
        print(f"  {t}")

    print("\nSample rows with newly-captured tokens (first 50):")
    for r in per_row_new[:50]:
        print(f"- {r['rel_path']}")
        print(f"  new: {r['new_tokens']}")

    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
