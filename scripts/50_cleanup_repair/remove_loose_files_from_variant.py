#!/usr/bin/env python3
"""Detach "loose" files from a Variant by clearing their variant_id.

Dry-run by default; use `--apply` to commit changes. The script uses
conservative heuristics to decide which associated File rows are not
actually part of the variant: non-model extensions (images/archives) and
files that don't share tokens or path-prefix/filename containment with the
variant are considered loose.

Usage examples:
  # Dry-run for variant 66
  .venv\Scripts\python.exe scripts\50_cleanup_repair\remove_loose_files_from_variant.py 66

  # Apply changes
  $env:STLMGR_DB_URL = 'sqlite:///.../data/stl_manager_v1.db'
  .venv\Scripts\python.exe scripts\50_cleanup_repair\remove_loose_files_from_variant.py 66 --apply
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant, File
from scripts.quick_scan import tokenize


MODEL_EXTS = {'.stl', '.obj', '.3mf', '.gltf', '.glb', '.ztl', '.step', '.stp', '.lys', '.chitubox', '.ctb'}


def should_detach_file(variant: Variant, f: File, base_tokens: List[str]) -> bool:
    fname = (f.filename or "")
    frel = (f.rel_path or "")
    token_source = fname or frel
    if not token_source:
        return True
    p = Path(token_source)
    ext = p.suffix.lower()
    # Non-model extensions are loose by default
    if ext and ext not in MODEL_EXTS:
        return True
    # Tokenize file
    try:
        file_tokens = tokenize(Path(token_source))
    except Exception:
        file_tokens = []

    # If file path starts with variant rel_path -> keep
    if variant.rel_path and frel:
        try:
            if Path(frel).as_posix().lower().startswith(Path(variant.rel_path or "").as_posix().lower()):
                return False
        except Exception:
            pass

    # If filename contains the variant filename -> keep
    if variant.filename and fname:
        if variant.filename.lower() in fname.lower():
            return False

    # If the file shares a token with the variant base tokens -> keep
    if base_tokens and set(file_tokens) & set(base_tokens):
        return False

    # Otherwise consider it loose
    return True


def process_variant(variant_id: int, apply: bool):
    results = {"variant_id": variant_id, "detach_count": 0, "detached_files": []}
    with get_session() as session:
        v = session.query(Variant).get(variant_id)
        if not v:
            raise SystemExit(f"Variant {variant_id} not found")

        # build base tokens from variant rel_path + variant filename
        base_tokens = []
        try:
            base_tokens += tokenize(Path(v.rel_path or ""))
        except Exception:
            pass
        if v.filename:
            try:
                base_tokens += tokenize(Path(v.filename))
            except Exception:
                pass

        files = list(v.files or [])
        to_detach = []
        for f in files:
            if should_detach_file(v, f, base_tokens):
                to_detach.append({
                    "file_id": f.id,
                    "filename": f.filename,
                    "rel_path": f.rel_path,
                })

        results["detach_count"] = len(to_detach)
        results["detached_files"] = to_detach

        print(json.dumps({"dry_run": not apply, **results}, indent=2))

        if apply and to_detach:
            # Create or find an 'orphan' variant to reassign detached files to.
            # We use a rel_path under the same root as the original variant to
            # make it easy to inspect later (e.g. 'sample_store_orphaned').
            orphan_rel = f"{(v.rel_path or 'orphan')}_orphaned"
            orphan = session.query(Variant).filter_by(rel_path=orphan_rel).first()
            if not orphan:
                orphan = Variant(rel_path=orphan_rel, filename=None, is_dir=False)
                session.add(orphan)
                session.flush()  # assign orphan.id

            for entry in to_detach:
                frow = session.query(File).get(entry["file_id"])
                if frow:
                    frow.variant_id = orphan.id
            session.commit()
            print(f"Committed: reassigned {len(to_detach)} files from variant {variant_id} to orphan variant {orphan.id}")

    return results


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Detach loose files from a Variant (dry-run default)")
    ap.add_argument('variant_id', type=int, help='Variant id to clean')
    ap.add_argument('--apply', action='store_true', help='Commit detach operations')
    return ap.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    process_variant(args.variant_id, args.apply)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
