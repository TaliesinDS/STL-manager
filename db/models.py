from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    JSON,
    LargeBinary,
)
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class Variant(Base):
    __tablename__ = "variant"

    id = Column(Integer, primary_key=True, index=True)
    rel_path = Column(String(1024), nullable=False, index=True)
    filename = Column(String(512), nullable=False)
    extension = Column(String(32), nullable=True, index=True)
    size_bytes = Column(Integer, nullable=True)
    mtime_iso = Column(String(64), nullable=True)
    is_archive = Column(Boolean, default=False)
    hash_sha256 = Column(String(128), nullable=True, index=True)

    # Normalized metadata fields (phase P0/P1 subset)
    designer = Column(String(256), nullable=True, index=True)
    franchise = Column(String(256), nullable=True, index=True)
    content_flag = Column(String(32), nullable=True)

    # Residual/diagnostic fields
    residual_tokens = Column(JSON, default=list)
    token_version = Column(Integer, nullable=True)
    normalization_warnings = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Variant id={self.id} path={self.rel_path} file={self.filename}>"


class Archive(Base):
    __tablename__ = "archive"

    id = Column(Integer, primary_key=True)
    rel_path = Column(String(1024), nullable=False)
    filename = Column(String(512), nullable=False)
    size_bytes = Column(Integer, nullable=True)
    hash_sha256 = Column(String(128), nullable=True)
    nested_archive_flag = Column(Boolean, default=False)
    scan_first_seen_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Archive id={self.id} file={self.filename}>"


class VocabEntry(Base):
    __tablename__ = "vocab_entry"

    id = Column(Integer, primary_key=True)
    domain = Column(String(64), nullable=False, index=True)  # e.g., 'designer', 'franchise'
    key = Column(String(256), nullable=False, index=True)
    aliases = Column(JSON, default=list)
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<VocabEntry {self.domain}:{self.key}>"


class Job(Base):
    __tablename__ = "job"

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)
    status = Column(String(32), default="pending", index=True)
    progress = Column(Integer, default=0)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Job id={self.id} name={self.name} status={self.status}>"


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(Integer, nullable=True, index=True)
    field = Column(String(128), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    actor = Column(String(128), nullable=True)
    ts = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<AuditLog {self.resource_type}:{self.resource_id} {self.field}>"
