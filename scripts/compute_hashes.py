#!/usr/bin/env python3
"""Compute SHA-256 for File rows missing a hash and write them to the DB.

Safe defaults:
 - No DB writes unless `--apply` is provided.
 - Shows counts and a small sample in dry-run mode so you can estimate runtime.

Usage:
  # dry-run (default) - shows how many files are missing hashes and sample paths
  .venv\Scripts\python.exe scripts\compute_hashes.py

  # apply: compute and write hashes (may take long for many/large files)
  .venv\Scripts\python.exe scripts\compute_hashes.py --apply --batch 50
"""
from __future__ import annotations
import argparse
import hashlib
import sys
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import File


CHUNK = 8 * 1024 * 1024


def iter_missing_files(limit: int = 0) -> Iterator[File]:
    with get_session() as session:
        q = session.query(File).filter(File.hash_sha256 == None).order_by(File.id)
        if limit:
            q = q.limit(limit)
        for f in q:
            yield f


def sha256_of_path(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b''):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description='Compute SHA256 for File rows missing hash')
    ap.add_argument('--apply', action='store_true', help='Compute hashes and write to DB (default: dry-run)')
    ap.add_argument('--limit', type=int, default=0, help='Limit number of files to consider (0 = all)')
    ap.add_argument('--batch', type=int, default=100, help='Commit batch size when applying')
    ap.add_argument('--sample', type=int, default=20, help='Number of sample paths to show in dry-run')
    args = ap.parse_args(argv)

    files = list(iter_missing_files(args.limit))
    total = len(files)
    print(f'Files missing hash: {total}')
    if total == 0:
        return 0

    # Show a small sample and existence stats
    exists = 0
    missing = 0
    sample = []
    for i, f in enumerate(files, start=1):
        rel = Path(f.rel_path)
        fs_path = (PROJECT_ROOT / rel).resolve()
        ok = fs_path.exists()
        if ok:
            exists += 1
        else:
            missing += 1
        if len(sample) < args.sample:
            sample.append((f.id, f.rel_path, ok))

    print(f'  On-disk existence: {exists} present, {missing} missing')
    print('\nSample entries:')
    for fid, rel, ok in sample:
        print(f'  id={fid} present={ok} rel_path={rel}')

    if not args.apply:
        print('\nDry-run mode (no hashes computed/written). Re-run with --apply to compute and commit.')
        return 0

    # Apply mode: compute and write hashes in batches
    print('\nApply mode enabled: computing hashes and updating DB...')
    to_update = []
    count_done = 0
    count_skipped = 0
    batch = []
    for f in files:
        rel = Path(f.rel_path)
        fs_path = (PROJECT_ROOT / rel).resolve()
        if not fs_path.exists():
            print(f'[SKIP] missing on disk: id={f.id} rel={f.rel_path}')
            count_skipped += 1
            continue
        try:
            h = sha256_of_path(fs_path)
        except Exception as e:
            print(f'[ERROR] hashing id={f.id} rel={f.rel_path}: {e}')
            count_skipped += 1
            continue
        batch.append((f.id, h))
        if len(batch) >= args.batch:
            # write batch
            with get_session() as session:
                for fid, hh in batch:
                    session.query(File).filter(File.id == fid).update({"hash_sha256": hh})
                session.commit()
            count_done += len(batch)
            print(f'Committed batch of {len(batch)} (total {count_done})')
            batch = []

    # final flush
    if batch:
        with get_session() as session:
            for fid, hh in batch:
                session.query(File).filter(File.id == fid).update({"hash_sha256": hh})
            session.commit()
        count_done += len(batch)
        print(f'Committed final batch of {len(batch)} (total {count_done})')

    print(f'Done. hashes written: {count_done}; skipped: {count_skipped}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
