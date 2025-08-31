#!/usr/bin/env python3
"""Remove or merge Variants that contain only junk/preview files.

Dry-run by default; use --apply to commit changes.

Behavior:
- A Variant is considered "junk-only" if it has no associated File rows with a
  model/project extension nor any archive files. We treat the following as model/project:
    .stl .obj .3mf .gltf .glb .step .stp .lys .chitubox .ctb
  Archives: .zip .rar .7z .cbz .cbr
- For each junk-only Variant, we try to find the nearest parent Variant by
  walking up past trivial leaf folder names (hands/supported/unsupported/stl/.../lys).
  If a parent Variant exists, we reassign the junk files to the parent and delete
  the junk-only Variant. If no parent exists, we can optionally create one when
  --create-parent is passed; otherwise we skip.

Usage (PowerShell):
  $env:STLMGR_DB_URL = 'sqlite:///./data/stl_manager_v1.db'
  .\.venv\Scripts\python.exe .\scripts\50_cleanup_repair\cleanup_remove_junk_only_variants.py --apply
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session  # type: ignore
from db.models import Variant, File  # type: ignore


MODEL_EXTS = {'.stl', '.obj', '.3mf', '.gltf', '.glb', '.step', '.stp', '.lys', '.chitubox', '.ctb', '.ztl'}
ARCHIVE_EXTS = {'.zip', '.rar', '.7z', '.cbz', '.cbr'}
TRIVIAL_FOLDERS = {"hands", "supported", "unsupported", "stl", "supported stl", "unsupported stl", "supported_stl", "unsupported_stl", "lys"}


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Remove or merge variants that contain only junk/preview files (dry-run by default)")
    ap.add_argument('--apply', action='store_true', help='Commit changes to DB (default: dry-run)')
    ap.add_argument('--limit', type=int, default=0, help='Max variants to process (0 = no limit)')
    ap.add_argument('--create-parent', action='store_true', help='Create a parent variant when none exists while merging')
    return ap.parse_args(argv)


def is_model_or_archive(f: File) -> bool:
    # Decide if a File row is a model/project or an archive we care about
    ext = (f.extension or '').lower()
    if not ext and f.filename:
        # fall back to suffix from filename
        from pathlib import Path as P
        ext = P(f.filename).suffix.lower()
    return (ext in MODEL_EXTS) or (ext in ARCHIVE_EXTS) or bool(f.is_archive)


def nearest_nontrivial_parent(rel_path: str) -> str:
    p = Path(rel_path)
    # move up one level first; then skip trivial names
    p = p.parent
    while p.name.lower() in TRIVIAL_FOLDERS:
        p = p.parent
    return p.as_posix()


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    processed = 0
    affected = 0
    with get_session() as session:
        # Consider all Variants; we'll classify by their associated File rows
        variants = session.query(Variant).all()
        for v in variants:
            files = list(getattr(v, 'files', []) or [])
            if not files:
                # Empty variants are junk-only by definition; prefer to remove/merge if possible
                junk_only = True
            else:
                junk_only = not any(is_model_or_archive(f) for f in files)
            if not junk_only:
                continue
            processed += 1

            parent_rel = nearest_nontrivial_parent(v.rel_path or '')
            parent = session.query(Variant).filter(Variant.rel_path == parent_rel).one_or_none()
            action = 'delete' if parent else 'skip'
            if not parent and args.create_parent:
                parent = Variant(rel_path=parent_rel, filename=None, extension=None, size_bytes=None, is_archive=False)
                session.add(parent)
                session.flush()
                action = 'create_parent+delete'

            print(f"JUNK-ONLY Variant id={v.id} rel='{v.rel_path}' -> parent='{parent_rel}' action={action} files={len(files)}")

            if args.apply and parent:
                # Move files up and delete variant
                for f in files:
                    f.variant_id = parent.id
                session.delete(v)
                affected += 1
            elif args.apply and not parent and not args.create_parent:
                # No safe parent; leave it in place (explicit)
                pass

        if args.apply:
            session.commit()

    print(f"Processed {processed} junk-only variant(s); {'applied' if args.apply else 'planned'} removals/merges: {affected}")
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))
