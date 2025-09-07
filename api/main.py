from __future__ import annotations

from typing import List, Optional, Generator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.session import get_session
from db import models


def get_db() -> Generator[Session, None, None]:
    # Wrap the existing contextmanager for FastAPI dependency injection
    with get_session() as s:
        yield s


class FileOut(BaseModel):
    id: int
    filename: str
    extension: Optional[str] = None
    size_bytes: Optional[int] = None


class VariantSummary(BaseModel):
    id: int
    rel_path: str
    filename: Optional[str] = None
    designer: Optional[str] = None
    franchise: Optional[str] = None
    game_system: Optional[str] = None
    codex_faction: Optional[str] = None
    base_size_mm: Optional[int] = None
    ui_display_en: Optional[str] = None
    updated_at: Optional[str] = None


class VariantDetail(VariantSummary):
    files: List[FileOut] = []


class PaginatedVariants(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[VariantSummary]


app = FastAPI(title="STL Manager API", version="0.1.0")

# CORS for local dev (adjust later as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _to_summary(v: models.Variant) -> VariantSummary:
    return VariantSummary(
        id=v.id,
        rel_path=v.rel_path,
        filename=v.filename,
        designer=v.designer,
        franchise=v.franchise,
        game_system=v.game_system,
        codex_faction=v.codex_faction,
        base_size_mm=v.base_size_mm,
        ui_display_en=v.ui_display_en,
        updated_at=v.updated_at.isoformat() if getattr(v, "updated_at", None) else None,
    )


@app.get("/variants", response_model=PaginatedVariants)
def list_variants(
    q: Optional[str] = Query(None, description="Search in rel_path, filename, display text"),
    system: Optional[str] = Query(None, description="Filter by game_system key (e.g., w40k)"),
    faction: Optional[str] = Query(None, description="Filter by codex_faction"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    qry = db.query(models.Variant)
    if q:
        like = f"%{q}%"
        qry = qry.filter(
            (models.Variant.rel_path.ilike(like))
            | (models.Variant.filename.ilike(like))
            | (models.Variant.ui_display_en.ilike(like))
        )
    if system:
        qry = qry.filter(models.Variant.game_system == system)
    if faction:
        qry = qry.filter(models.Variant.codex_faction == faction)

    total = db.query(func.count(models.Variant.id)).select_from(qry.subquery()).scalar()  # type: ignore
    items = (
        qry.order_by(models.Variant.updated_at.desc().nullslast(), models.Variant.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return PaginatedVariants(
        total=int(total or 0),
        limit=limit,
        offset=offset,
        items=[_to_summary(v) for v in items],
    )


@app.get("/variants/{variant_id}", response_model=VariantDetail)
def get_variant(variant_id: int, db: Session = Depends(get_db)):
    v = db.query(models.Variant).filter(models.Variant.id == variant_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    files = [
        FileOut(id=f.id, filename=f.filename, extension=f.extension, size_bytes=f.size_bytes)
        for f in getattr(v, "files", [])
    ]
    base = _to_summary(v).dict()
    base["files"] = files
    return base
