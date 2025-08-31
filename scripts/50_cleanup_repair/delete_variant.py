#!/usr/bin/env python3
"""Delete a Variant and all associated rows (files, unit/part links) by id or rel_path.

Dry-run by default; use --apply to commit. Example (PowerShell):
  .\.venv\Scripts\python.exe .\scripts\50_cleanup_repair\delete_variant.py --id 66 --apply
  .\.venv\Scripts\python.exe .\scripts\50_cleanup_repair\delete_variant.py --rel-path sample_store --apply
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant


def find_variant(session, vid: int | None, rel_path: str | None) -> Variant | None:
    if vid is not None:
        return session.query(Variant).get(vid)
    if rel_path:
        return session.query(Variant).filter(Variant.rel_path == rel_path).first()
    return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Delete a Variant and cascaded rows (dry-run by default)")
    ap.add_argument('--id', type=int, help='Variant id to delete')
    ap.add_argument('--rel-path', help='Variant rel_path to delete (exact match)')
    ap.add_argument('--apply', action='store_true', help='Commit deletion')
    args = ap.parse_args(argv)

    if args.id is None and not args.rel_path:
        print('Provide --id or --rel-path')
        return 2

    with get_session() as session:
        v = find_variant(session, args.id, args.rel_path)
        if not v:
            print(json.dumps({"found": False, "id": args.id, "rel_path": args.rel_path}))
            return 0
        info = {
            "found": True,
            "id": v.id,
            "rel_path": v.rel_path,
            "files": len(v.files or []),
            "unit_links": len(v.unit_links or []),
            "part_links": len(v.part_links or []),
        }
        print(json.dumps({"dry_run": (not args.apply), **info}, indent=2))
        if args.apply:
            session.delete(v)
            session.commit()
            print(f"Deleted variant {v.id} ({v.rel_path}) and cascaded rows.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
