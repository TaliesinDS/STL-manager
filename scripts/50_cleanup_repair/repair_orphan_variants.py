#!/usr/bin/env python3
"""Repair orphaned files by recreating missing Variant rows.

Find distinct File.variant_id values where no Variant row exists and
recreate a minimal Variant for each using the common parent directory
of the files' rel_path values. Safe by default (dry-run). Use --apply to commit.

Usage (PowerShell):
  .\.venv\Scripts\python.exe .\scripts\50_cleanup_repair\repair_orphan_variants.py --db-url sqlite:///./data/stl_manager_v1.db --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Dict, List, Optional, Tuple

# ensure project root
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from db.session import get_session, DB_URL
from db.models import Variant, File

# Treat only these as true 3D model/slicer project files when deciding to recreate a Variant
MODEL_EXTS = {
    ".stl", ".obj", ".3mf", ".gltf", ".glb", ".step", ".stp",
    ".lys", ".chitubox", ".ctb", ".ztl"
}


def _split_dirs(rel_path: str) -> List[str]:
    # Normalize separators and split into parts
    rp = rel_path.replace("\\", "/").strip("/")
    return [p for p in rp.split("/") if p]


def _common_parent_dir(paths: List[str]) -> str:
    # Get longest common directory path
    if not paths:
        return ""
    parts_list = [_split_dirs(p) for p in paths]
    common: List[str] = []
    for idx in range(min(len(pl) for pl in parts_list)):
        token = parts_list[0][idx]
        if all((len(pl) > idx and pl[idx] == token) for pl in parts_list):
            common.append(token)
        else:
            break
    # If the common path ends with a filename that looks like a model file, drop the filename
    if common:
        last = common[-1]
        # If last segment has a known model extension, strip it to return the parent directory
        for ext in MODEL_EXTS:
            if last.lower().endswith(ext):
                common = common[:-1]
                break
    return "/".join(common)


@dataclass
class Repair:
    variant_id: int
    rel_path: str
    file_count: int
    action: str
    model_file_count: int = 0
    note: str = ""


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Repair orphaned File rows by recreating missing Variant rows")
    p.add_argument("--db-url", help="Override DB URL (else uses STLMGR_DB_URL or default)")
    p.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    p.add_argument("--limit", type=int, default=1000, help="Max number of orphaned variants to repair in one run")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    # Rebind DB if provided
    if args.db_url:
        try:
            from sqlalchemy import create_engine as _ce
            from sqlalchemy.orm import sessionmaker as _sm, Session as _S
            import db.session as _dbs
            try:
                _dbs.engine.dispose()
            except Exception:
                pass
            _dbs.DB_URL = args.db_url
            _dbs.engine = _ce(args.db_url, future=True)
            _dbs.SessionLocal = _sm(bind=_dbs.engine, autoflush=False, autocommit=False, class_=_S)
        except Exception as e:
            print(f"Failed to reconfigure DB session for URL {args.db_url}: {e}", file=sys.stderr)
            return 2

    repairs: List[Repair] = []
    with get_session() as session:
        # Find distinct variant_ids in File
        vids = [row[0] for row in session.execute(select(File.variant_id).distinct()).all()]
        orphan_vids: List[int] = []
        for vid in vids:
            if not session.get(Variant, vid):
                orphan_vids.append(int(vid))
                if len(orphan_vids) >= args.limit:
                    break

        for vid in orphan_vids:
            files = session.execute(select(File).where(File.variant_id == vid)).scalars().all()
            all_rels = [f.rel_path for f in files if f.rel_path]
            # Filter to model files only
            model_rels = []
            for rp in all_rels:
                try:
                    ext = ("." + rp.split(".")[-1]).lower() if "." in rp else ""
                except Exception:
                    ext = ""
                if ext in MODEL_EXTS:
                    model_rels.append(rp)

            if not model_rels:
                # Skip orphan groups that have no model files (e.g., only images/junk)
                repairs.append(Repair(
                    variant_id=vid,
                    rel_path=_common_parent_dir(all_rels) or (all_rels[0] if all_rels else f"recovered_variant_{vid}"),
                    file_count=len(files),
                    model_file_count=0,
                    action="skip_non_model_only",
                    note="No model files found in orphaned group; not creating Variant"
                ))
                continue

            # Derive parent directory from model files only
            parent_rel = _common_parent_dir(model_rels)
            if not parent_rel:
                # Fall back to directory of the first model file
                r0 = model_rels[0]
                parts = _split_dirs(r0)
                parent_rel = "/".join(parts[:-1]) if len(parts) > 1 else parts[0] if parts else f"recovered_variant_{vid}"

            repairs.append(Repair(
                variant_id=vid,
                rel_path=parent_rel,
                file_count=len(files),
                model_file_count=len(model_rels),
                action="create_variant",
                note="Created from orphaned model files"
            ))

        if args.apply and repairs:
            to_create = [r for r in repairs if r.action == "create_variant"]
            if to_create:
                for r in to_create:
                    v = Variant(id=r.variant_id, rel_path=r.rel_path, filename=None, is_dir=True)
                    session.add(v)
                session.commit()

    print(json.dumps({
        "db_url": DB_URL,
        "apply": bool(args.apply),
        "repairs": [asdict(r) for r in repairs],
        "count": len(repairs),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
