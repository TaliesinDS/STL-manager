#!/usr/bin/env python3
"""Merge tokens captured from folder paths (sample_store) into Variant/File rows.

Reads `tests/fixtures/sample_inventory.json` (or `--inventory` path) which is produced
by `scripts/create_sample_inventory.py`. Tokenizes full path components using
`scripts.quick_scan.tokenize` (directory-aware) and compares with existing
`residual_tokens` on `File` and `Variant` rows. Proposes additions and can apply
them with `--apply` (creates a DB backup automatically).

Usage:
  .venv\Scripts\python.exe scripts\30_normalize_match\apply_sample_folder_tokens.py [--inventory path] [--apply] [--batch N]
"""
from __future__ import annotations
import argparse
import json
import shutil
import time
from pathlib import Path
import sys

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.quick_scan import tokenize
from db.session import get_session, engine
from db.models import Variant, File


def load_inventory(path: Path) -> list[dict]:
    with path.open('r', encoding='utf-8') as fh:
        return json.load(fh)


def backup_db(db_path: Path) -> Path:
    ts = time.strftime('%Y%m%d_%H%M%S')
    bak = db_path.with_name(db_path.name + f'.bak.{ts}')
    shutil.copy2(db_path, bak)
    return bak


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--inventory', default=str(PROJECT_ROOT / 'tests' / 'fixtures' / 'sample_inventory.json'))
    ap.add_argument('--apply', action='store_true', help='Write merged tokens to DB (default dry-run)')
    ap.add_argument('--batch', type=int, default=200, help='DB commit batch size when applying')
    args = ap.parse_args(argv)

    inv_path = Path(args.inventory)
    if not inv_path.exists():
        print('Inventory not found:', inv_path)
        return 2
    items = load_inventory(inv_path)
    print(f'Loaded {len(items)} inventory rows from {inv_path}')

    # Group by file rel_path for lookup. Store both original and slash-normalized keys
    # because `load_sample.py` writes rel_path exactly as in the fixture (backslashes
    # on Windows) while some utilities normalize to forward slashes.
    by_rel: dict[str, dict] = {}
    for it in items:
        raw = it['rel_path']
        norm = raw.replace('\\', '/')
        by_rel[raw] = it
        by_rel[norm] = it

    proposals = []
    with get_session() as session:
        # Fetch files that match inventory rel_paths
        q = session.query(File).filter(File.rel_path.in_(list(by_rel.keys())))
        files = q.all()
        print(f'Found {len(files)} matching File rows in DB')
        for f in files:
            inv = by_rel.get(f.rel_path)
            if not inv:
                continue
            # Compute full-path tokens using our improved tokenizer
            toks_full = tokenize(Path(inv['rel_path']))
            # Existing residual tokens on file and variant
            file_tokens = set((f.residual_tokens or []) )
            v = session.query(Variant).filter_by(id=f.variant_id).one_or_none()
            variant_tokens = set((v.residual_tokens or [])) if v else set()

            missing_for_file = sorted(t for t in toks_full if t not in file_tokens)
            missing_for_variant = sorted(t for t in toks_full if t not in variant_tokens)
            if missing_for_file or missing_for_variant:
                proposals.append({
                    'file_id': f.id,
                    'rel_path': f.rel_path,
                    'variant_id': f.variant_id,
                    'missing_for_file': missing_for_file,
                    'missing_for_variant': missing_for_variant,
                })

    print(f'Proposed token updates for {len(proposals)} files (dry-run={not args.apply})')
    if not proposals:
        print('No updates proposed; nothing to apply.')
        return 0

    # Show a small sample
    for p in proposals[:50]:
        print(json.dumps(p, ensure_ascii=False))

    if not args.apply:
        print('\nDry-run complete. Re-run with --apply to write the token merges to DB.')
        return 0

    # Apply path: create DB backup then merge tokens
    # Discover SQLite DB path from SQLAlchemy engine if possible so we can backup
    db_path = None
    try:
        # engine.url may be a sqlalchemy.engine.URL; for sqlite the database attribute
        # is a filesystem path (relative or absolute). Use that when available.
        url = engine.url
        if getattr(url, 'drivername', '').startswith('sqlite'):
            # url.database may be relative; resolve against project root
            candidate = Path(url.database)
            if not candidate.is_absolute():
                candidate = PROJECT_ROOT / candidate
            db_path = candidate
    except Exception:
        db_path = None

    if db_path and db_path.exists():
        bak = backup_db(db_path)
        print(f'Created DB backup: {bak}')
    else:
        # Fallback to previously used hardcoded name for compatibility
        fallback = PROJECT_ROOT / 'data' / 'stl_manager_v1.db'
        if fallback.exists():
            bak = backup_db(fallback)
            print(f'Created DB backup: {bak} (fallback)')
        else:
            print('Warning: DB file not found to create backup; applying directly to DB via SQLAlchemy session')

    applied = 0
    with get_session() as session:
        to_commit = []
        for p in proposals:
            f = session.query(File).filter_by(id=p['file_id']).one_or_none()
            if not f:
                continue
            v = session.query(Variant).filter_by(id=p['variant_id']).one_or_none()
            # Merge file tokens
            if p['missing_for_file']:
                cur = list(f.residual_tokens or [])
                for t in p['missing_for_file']:
                    if t not in cur:
                        cur.append(t)
                f.residual_tokens = cur
            # Merge variant tokens
            if v and p['missing_for_variant']:
                curv = list(v.residual_tokens or [])
                for t in p['missing_for_variant']:
                    if t not in curv:
                        curv.append(t)
                v.residual_tokens = curv
            to_commit.append((v,f))
            if len(to_commit) >= args.batch:
                session.commit()
                applied += len(to_commit)
                to_commit = []
        if to_commit:
            session.commit()
            applied += len(to_commit)

    print(f'Applied token merges to {applied} variant/file groups.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
