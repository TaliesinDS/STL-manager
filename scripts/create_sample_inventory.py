"""Create a small JSON inventory for files under `sample_store/` suitable for `scripts/load_sample.py`.

It writes `data/sample_inventory.json` by default. Each item contains keys expected by `load_sample.py`:
  - rel_path (relative path from repo root)
  - filename
  - extension
  - size_bytes
  - is_archive
  - raw_path_tokens (simple tokenization of the filename)
  - token_version (0)

Usage:
  .venv\Scripts\python.exe scripts\create_sample_inventory.py --root sample_store --out data/sample_inventory.json
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path


def tokenize_name(p: Path) -> list[str]:
    stem = p.stem.lower()
    # simple split on non-alphanumeric
    import re
    parts = re.split(r"[^0-9a-z]+", stem)
    return [t for t in parts if t and len(t) > 1]


def build_inventory(root: Path) -> list[dict]:
    items: list[dict] = []
    root = root.resolve()
    for p in sorted(root.rglob('*')):
        if p.is_dir():
            continue
        # Skip files located directly under the top-level sample_store root
        # (we only want to inventory files inside subfolders for now)
        try:
            if p.parent.resolve() == root:
                continue
        except Exception:
            pass
        rel = p.relative_to(Path(__file__).resolve().parent.parent)
        items.append({
            "rel_path": str(rel).replace('\\\\', '/'),
            "filename": p.name,
            "extension": p.suffix.lower(),
            "size_bytes": p.stat().st_size,
            "is_archive": p.suffix.lower() in {'.zip', '.rar', '.7z', '.cbz', '.cbr'},
            "raw_path_tokens": tokenize_name(p),
            "token_version": 0,
        })
    return items


def parse_args(argv: list[str]):
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='sample_store', help='Root folder containing sample files')
    ap.add_argument('--out', default='data/sample_inventory.json', help='Output JSON path')
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    if not root.exists() or not root.is_dir():
        print('Root not found or not a directory:', root)
        return 2
    items = build_inventory(root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(items, indent=2), encoding='utf-8')
    print(f'Wrote {len(items)} file entries to {out}')
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))
