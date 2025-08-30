from __future__ import annotations

import os
from typing import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

DB_URL = os.environ.get("STLMGR_DB_URL", "sqlite:///./data/stl_manager.db")

engine = create_engine(DB_URL, future=True)

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
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
