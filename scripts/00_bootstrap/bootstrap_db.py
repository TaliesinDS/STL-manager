#!/usr/bin/env python3
"""Project database bootstrapper

Creates or upgrades the database schema to the latest Alembic revision.

Defaults are safe:
- Uses Alembic migrations by default (no destructive operations)
- Accepts --db-url to override target DB (preferred over env var on Windows)
- Falls back to SQLAlchemy metadata create_all if Alembic is unavailable

Examples (PowerShell):
  .\.venv\Scripts\python.exe scripts\00_bootstrap\bootstrap_db.py --db-url sqlite:///./data/stl_manager_v1.db

Optional:
  --use-metadata      Use SQLAlchemy Base.metadata.create_all instead of Alembic
  --echo              Enable SQL echo for troubleshooting
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
def _reconcile_missing_columns(db_url: str, project_root: Path) -> None:
    """Add any ORM-declared columns that are missing from existing tables.

    This is a safety net when Alembic history lags the ORM models. It only ADDs
    nullable columns; it won't modify or drop existing columns.
    """
    try:
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        import sqlalchemy as sa  # type: ignore
        from sqlalchemy import inspect as _sa_inspect  # type: ignore
        from db.models import Base as _Base  # type: ignore
        eng = sa.create_engine(db_url, future=True)
        insp = _sa_inspect(eng)
        meta_tables = {t.name: t for t in _Base.metadata.sorted_tables}
        for tname, table in meta_tables.items():
            if tname not in insp.get_table_names():
                continue
            existing = {c['name'] for c in insp.get_columns(tname)}
            for col in table.columns:
                if col.name in existing:
                    continue
                # Build column DDL; default to NULL-able
                try:
                    ddl_type = col.type.compile(dialect=eng.dialect)
                except Exception:
                    # Fallback for exotic types
                    ddl_type = "TEXT"
                nullable = "" if getattr(col, 'nullable', True) else " NOT NULL"
                ddl = f"ALTER TABLE {tname} ADD COLUMN {col.name} {ddl_type}{'' if nullable == '' else ''}"
                # SQLite can't add NOT NULL without default; relax to NULL-able
                if eng.dialect.name == 'sqlite':
                    ddl = f"ALTER TABLE {tname} ADD COLUMN {col.name} {ddl_type}"
                with eng.begin() as conn:
                    try:
                        conn.exec_driver_sql(ddl)
                        print(f"[reconcile] Added missing column {tname}.{col.name} ({ddl_type})")
                    except Exception as e:
                        print(f"[reconcile][warn] Failed to add {tname}.{col.name}: {e}")
        eng.dispose()
    except Exception as e:
        print(f"[reconcile][warn] Skipping column reconcile: {e}")


def _ensure_sqlite_dir(db_url: str, project_root: Path) -> None:
    # Create parent directory for SQLite files if needed
    try:
        from sqlalchemy.engine import make_url  # type: ignore
        url = make_url(db_url)
        if url.get_backend_name() == "sqlite" and url.database:
            db_path = Path(url.database)
            if not db_path.is_absolute():
                db_path = (project_root / db_path).resolve()
            if db_path.parent:
                db_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Best-effort only; continue if parsing fails
        pass


def _run_alembic_upgrade_head(db_url: str, project_root: Path) -> int:
    try:
        from alembic.config import Config  # type: ignore
        from alembic import command  # type: ignore
        from sqlalchemy.exc import IntegrityError  # type: ignore
    except Exception as e:  # Alembic not installed or import error
        print("[warn] Alembic not available:", e)
        return 2

    ini_path = project_root / "alembic.ini"
    if not ini_path.is_file():
        print(f"[error] alembic.ini not found at {ini_path}")
        return 2

    cfg = Config(str(ini_path))
    # Ensure script location and URL are set correctly
    cfg.set_main_option("script_location", str(project_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    print("Running Alembic upgrade to head...")
    try:
        command.upgrade(cfg, "head")
        print("Alembic upgrade complete.")
    except IntegrityError as ie:
        # Occurs when the version row is already present (idempotent re-run)
        print(f"[warn] Alembic IntegrityError during upgrade: {ie}; attempting stamp-and-upgrade fallback...")
        try:
            # Prefer stamping to initial baseline if present, else directly to head
            try:
                command.stamp(cfg, "0001_canonical_initial")
                print("Stamped to 0001_canonical_initial.")
                command.upgrade(cfg, "head")
                print("Alembic upgrade complete after stamping baseline.")
            except Exception:
                command.stamp(cfg, "head")
                print("Stamped to head to reconcile version table.")
        except Exception as e:
            print(f"[error] Alembic stamp/upgrade fallback failed: {e}")
            return 2
    except Exception as e:
        print(f"[warn] Alembic upgrade failed ({e}); attempting metadata create_all fallback...")
        # Fall through to metadata create_all below
    # Safety net: ensure all ORM-declared tables exist (no-ops for existing tables)
    try:
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from sqlalchemy import create_engine as _ce  # type: ignore
        from db.models import Base as _Base  # type: ignore
        eng = _ce(db_url, future=True)
        _Base.metadata.create_all(bind=eng)
        eng.dispose()
        print("Verified baseline tables via SQLAlchemy metadata.")
    except Exception as e:
        print(f"[warn] metadata create_all verification skipped: {e}")
    # Final pass: add any ORM-declared columns that are missing (non-destructive)
    _reconcile_missing_columns(db_url, project_root)
    return 0


def _create_with_metadata(db_url: str, project_root: Path, echo: bool = False) -> int:
    print("Creating tables via SQLAlchemy metadata (create_all)...")
    os.environ["STLMGR_DB_URL"] = db_url
    # Import after setting env var so db.session picks it up
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from sqlalchemy import create_engine
    from db.models import Base  # type: ignore
    engine = create_engine(db_url, echo=echo, future=True)
    Base.metadata.create_all(bind=engine)
    print("Metadata create_all complete.")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Bootstrap/upgrade the project database schema")
    ap.add_argument("--db-url", dest="db_url", default=os.environ.get("STLMGR_DB_URL", "sqlite:///./data/stl_manager.db"),
                   help="Target database URL (overrides env var STLMGR_DB_URL)")
    ap.add_argument("--use-metadata", action="store_true",
                   help="Use SQLAlchemy Base.metadata.create_all instead of Alembic")
    ap.add_argument("--echo", action="store_true", help="Echo SQL statements (metadata mode)")
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    project_root = Path(__file__).resolve().parents[2]
    db_url = args.db_url
    print(f"Target DB URL: {db_url}")
    _ensure_sqlite_dir(db_url, project_root)

    if args.use_metadata:
        return _create_with_metadata(db_url, project_root, echo=args.echo)

    # Prefer Alembic; fall back to metadata if Alembic is not available
    rc = _run_alembic_upgrade_head(db_url, project_root)
    if rc != 0:
        print("[warn] Falling back to SQLAlchemy metadata create_all...")
        return _create_with_metadata(db_url, project_root, echo=args.echo)
    return 0


if __name__ == "__main__":
    import sys as _sys
    raise SystemExit(main(_sys.argv[1:]))
