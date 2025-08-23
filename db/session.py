from __future__ import annotations

import os
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_URL = os.environ.get("STLMGR_DB_URL", "sqlite:///./data/stl_manager.db")

engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Iterator[sessionmaker]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
