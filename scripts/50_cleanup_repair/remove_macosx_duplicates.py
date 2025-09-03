#!/usr/bin/env python3
"""Remove duplicate variants/files that live under macOS metadata folders (__MACOSX).

Features:
  - Dry-run by default: prints counts and sample IDs/paths
  - Optional JSON report via --out
  - --apply to actually delete rows (cascades to File via ORM relationships)

Usage (PowerShell):
  .\.venv\Scripts\python.exe .\scripts\50_cleanup_repair\remove_macosx_duplicates.py --out reports/remove_macosx_dryrun.json
  .\.venv\Scripts\python.exe .\scripts\50_cleanup_repair\remove_macosx_duplicates.py --apply --out reports/remove_macosx_apply.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session, DB_URL  # type: ignore
from db.models import Variant, File  # type: ignore


def find_targets(session):
    # Match on either forward- or backslash paths; use LIKE for both
    from sqlalchemy import or_  # type: ignore
    vq = session.query(Variant).filter(
        or_(
            Variant.rel_path.ilike('%/__MACOSX/%'),
            Variant.rel_path.ilike('%\\__MACOSX\\%'),
            Variant.rel_path.ilike('%/__macosx/%'),
            Variant.rel_path.ilike('%\\__macosx\\%'),
        )
    )
    fq = session.query(File).filter(
        or_(
            File.rel_path.ilike('%/__MACOSX/%'),
            File.rel_path.ilike('%\\__MACOSX\\%'),
            File.rel_path.ilike('%/__macosx/%'),
            File.rel_path.ilike('%\\__macosx\\%'),
        )
    )
    variants = vq.all()
    files = fq.all()
    return variants, files


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description='Delete variants/files under __MACOSX folders')
    ap.add_argument('--apply', action='store_true', help='Apply deletions to the database')
    ap.add_argument('--out', help='Optional JSON report path to write results')
    args = ap.parse_args(argv)

    print(f"Using database: {DB_URL}")
    with get_session() as session:
        variants, files = find_targets(session)
        v_ids = sorted({v.id for v in variants})
        f_ids = sorted({f.id for f in files})
        print(f"Found {len(v_ids)} variants and {len(f_ids)} files under __MACOSX paths.")
        sample = [{"variant_id": v.id, "rel_path": v.rel_path} for v in variants[:20]]
        for s in sample:
            print(f"  V#{s['variant_id']}: {s['rel_path']}")
        payload = {
            "apply": bool(args.apply),
            "variant_count": len(v_ids),
            "file_count": len(f_ids),
            "variant_ids": v_ids,
            "file_ids": f_ids,
        }
        if args.apply and (v_ids or f_ids):
            # Delete files first to avoid dangling references (though Variant has cascade delete)
            deleted_files = 0
            for f in files:
                session.delete(f)
                deleted_files += 1
            deleted_variants = 0
            for v in variants:
                session.delete(v)
                deleted_variants += 1
            session.commit()
            print(f"Deleted {deleted_variants} variant(s) and {deleted_files} file(s).")
            payload["deleted_variants"] = deleted_variants
            payload["deleted_files"] = deleted_files
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            print(f"Wrote report to {out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
