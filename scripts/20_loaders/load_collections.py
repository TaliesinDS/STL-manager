#!/usr/bin/env python3
"""
Load collection SSOT YAML files into the DB's Collection table (dry-run by default).

Phase 1 note:
- The Collection model is minimal (no slug/designer linkage yet). We upsert on a
  conservative key tuple: (original_label=name, cycle, publisher, theme, sequence_number).
- Variant.collection_* fields are written by the matcher script, independently of this loader.

Usage (PowerShell):
  .\.venv\Scripts\python.exe .\scripts\20_loaders\load_collections.py \
    --file .\vocab\collections\dm_stash.yaml \
    --db-url sqlite:///./data/stl_manager_v1.db   # optional override

Add --commit to persist changes; otherwise it's a dry-run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure repo root on sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.models import Collection  # type: ignore
import db.session as _dbs  # type: ignore


def reconfigure_db(db_url: str | None) -> None:
    if not db_url:
        return
    try:
        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import sessionmaker as _sm, Session as _S
        try:
            _dbs.engine.dispose()
        except Exception:
            pass
        _dbs.DB_URL = db_url
        _dbs.engine = _ce(db_url, future=True)
        _dbs.SessionLocal = _sm(bind=_dbs.engine, autoflush=False, autocommit=False, class_=_S)
    except Exception as e:
        print(f"Failed to reconfigure DB session for URL {db_url}: {e}", file=sys.stderr)
        raise


def load_yaml(path: Path) -> Dict[str, Any]:
    import yaml  # lazy import
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def upsert_collection(session, entry: Dict[str, Any], source_file: str) -> tuple[Collection, bool]:
    """Upsert a single Collection row based on a conservative key tuple.

    Returns (row, created_flag).
    """
    name = (entry.get("name") or "").strip() or None
    publisher = (entry.get("publisher") or "").strip() or None
    cycle = (entry.get("cycle") or "").strip() or None
    theme = (entry.get("theme") or "").strip() or None
    seq = entry.get("sequence_number")
    try:
        seq_int = int(seq) if seq is not None else None
    except Exception:
        seq_int = None

    # Find existing by tuple (name as original_label, cycle, publisher, theme, sequence_number)
    q = (
        session.query(Collection)
        .filter(Collection.original_label == name)
        .filter(Collection.cycle == cycle)
        .filter(Collection.publisher == publisher)
        .filter(Collection.theme == theme)
        .filter(Collection.sequence_number == seq_int)
    )
    row = q.one_or_none()
    created = False
    if row is None:
        row = Collection(
            original_label=name,
            publisher=publisher,
            cycle=cycle,
            sequence_number=seq_int,
            theme=theme,
        )
        session.add(row)
        created = True
    else:
        # Update simple fields (idempotent)
        row.original_label = name
        row.publisher = publisher
        row.cycle = cycle
        row.sequence_number = seq_int
        row.theme = theme
    # Provenance isn't modeled; we keep the YAML around in repo as SSOT.
    return row, created


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Load collection SSOT YAMLs into DB Collection table (dry-run by default)")
    p.add_argument("--file", "-f", action="append", required=False, help="Path to a collections YAML file; can be repeated")
    p.add_argument("--dir", "-d", default=str(ROOT / "vocab" / "collections"), help="Directory to scan for *.yaml if --file not provided")
    p.add_argument("--db-url", default=None, help="Override database URL (defaults to STLMGR_DB_URL env var or sqlite:///./data/stl_manager.db)")
    p.add_argument("--commit", action="store_true", help="Apply changes (default: dry-run)")
    args = p.parse_args(argv)

    reconfigure_db(args.db_url)

    # Gather files
    files: List[Path] = []
    if args.file:
        for f in args.file:
            files.append(Path(f))
    else:
        d = Path(args.dir)
        if d.exists():
            files.extend(sorted(d.glob("*.yaml")))
    files = [f for f in files if f.exists()]
    if not files:
        print("No collection YAML files found.")
        return 0

    created = 0
    updated = 0
    total = 0

    with _dbs.get_session() as session:
        for path in files:
            data = load_yaml(path)
            entries = (data or {}).get("collections") or []
            if not isinstance(entries, list):
                continue
            for entry in entries:
                total += 1
                row, is_new = upsert_collection(session, entry, source_file=path.name)
                if is_new:
                    created += 1
                else:
                    updated += 1
        if args.commit:
            session.commit()

    print(f"Processed files: {len(files)}; collections: {total}; created: {created}; updated: {updated}; commit={args.commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
