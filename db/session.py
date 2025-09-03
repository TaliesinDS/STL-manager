from __future__ import annotations

import os
from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, inspect as _sa_inspect
from sqlalchemy.pool import NullPool
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path
try:
    from sqlalchemy.engine.url import make_url, URL  # type: ignore
except Exception:
    make_url = None  # type: ignore
    URL = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]


def _normalize_sqlite_url(db_url: str) -> str:
    """Ensure sqlite file URLs are absolute and anchored at repo root when relative.

    This prevents mismatched files when different processes have different CWDs.
    """
    try:
        if make_url is None:
            return db_url
        url = make_url(db_url)
        if url.get_backend_name() != "sqlite":
            return db_url
        db_path = url.database or ""
        # skip in-memory URLs
        if db_path in (None, ":memory:"):
            return db_url
        p = Path(db_path)
        if not p.is_absolute():
            abs_p = (ROOT / p).resolve()
            # reconstruct URL with absolute path
            if URL is not None:
                url = url.set(database=str(abs_p))
                return str(url)
            else:
                return f"sqlite:///{abs_p.as_posix()}"
        return db_url
    except Exception:
        return db_url


# Default to the v1 database; can be overridden by STLMGR_DB_URL or per-script reconfiguration
DB_URL = _normalize_sqlite_url(os.environ.get("STLMGR_DB_URL", "sqlite:///./data/stl_manager_v1.db"))

# Use NullPool so SQLite file handles are released immediately (avoids Windows file locks in tests)
engine = create_engine(DB_URL, future=True, poolclass=NullPool)

# Ensure SQLite enforces foreign keys so CASCADE/SET NULL work as intended
if DB_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[override]
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        except Exception:
            # Non-SQLite or connection without pragma support; ignore
            pass
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    # If the environment requests a different DB URL, switch before creating a session
    try:
        env_url = os.environ.get("STLMGR_DB_URL")
        if env_url:
            target_url = _normalize_sqlite_url(env_url)
            if target_url != DB_URL:
                reconfigure(target_url)
        session = SessionLocal()
    except Exception:
        session = SessionLocal()
    # Lazily ensure core schema exists in ephemeral DBs
    try:
        from db.models import Base as _Base  # type: ignore
        _Base.metadata.create_all(bind=session.bind)
        insp = _sa_inspect(session.bind)
        tables = set(insp.get_table_names())
        # Reconcile missing columns for variant table against ORM definition
        if 'variant' in tables:
            try:
                from db.models import Variant as _Variant  # type: ignore
                orm_cols = {c.name: c for c in _Variant.__table__.columns}  # type: ignore[attr-defined]
                live_cols = {c['name'] for c in insp.get_columns('variant')}
                missing = [orm_cols[name] for name in orm_cols.keys() - live_cols]
                if missing:
                    # Use direct DDL to add columns (SQLite-compatible)
                    conn = session.bind.connect()  # type: ignore
                    try:
                        for col in missing:
                            try:
                                ddl_type = col.type.compile(dialect=conn.dialect)  # type: ignore
                            except Exception:
                                ddl_type = 'TEXT'
                            # SQLite cannot add NOT NULL without default; relax to NULL-able
                            ddl = f"ALTER TABLE variant ADD COLUMN {col.name} {ddl_type}"
                            try:
                                conn.exec_driver_sql(ddl)
                            except Exception:
                                # Ignore if the column was added concurrently or backend limitations
                                pass
                    finally:
                        try:
                            conn.close()
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass
    try:
        yield session
    finally:
        session.close()
        # Proactively dispose global engine so SQLite file handles are released (Windows lock avoidance)
        try:
            engine.dispose()
        except Exception:
            pass


def reconfigure(db_url: str) -> None:
    """Rebuild the SQLAlchemy engine/session for a new DB URL.

    Ensures NullPool (to release SQLite file handles) and PRAGMA foreign_keys for SQLite.
    """
    global DB_URL, engine, SessionLocal
    # Dispose any existing connections
    try:
        engine.dispose()
    except Exception:
        pass
    DB_URL = _normalize_sqlite_url(db_url)
    engine = create_engine(DB_URL, future=True, poolclass=NullPool)
    if DB_URL.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma_new(dbapi_connection, connection_record):  # type: ignore[override]
            try:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
            except Exception:
                pass
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
