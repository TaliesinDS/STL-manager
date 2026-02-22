from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Set

ROOT = Path(__file__).resolve().parents[2]

from sqlalchemy import select

from db.models import Variant  # type: ignore
from db.session import get_session  # type: ignore

NOISE_FILENAMES = {".ds_store", "thumbs.db", "desktop.ini"}
# Consider these extensions as meaningful 3D model or source files
MEANINGFUL_EXTS = {
    "stl", "obj", "ztl",  # common 3D model formats and ZBrush source
    # slicer/project and CAD formats (optional but useful)
    "lys", "lychee", "3mf", "step", "stp"
}
# Archives are considered meaningful (contain models inside)
ARCHIVE_EXTS = {"zip", "rar", "7z"}

# Child folder tokens that imply a modular squad kit (preserve such containers)
KIT_CHILD_TOKENS: Set[str] = {
    "body", "bodies", "torsos", "torso",
    "head", "heads", "helmet", "helmets",
    "arm", "arms", "left arm", "right arm",
    "weapon", "weapons", "ranged", "melee",
    "bits", "bitz", "accessories", "options",
    "shields", "backpacks", "shoulder pads", "pauldrons",
}


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _is_noise_filename(name: str) -> bool:
    n = _norm(name)
    if not n:
        return False
    if n in NOISE_FILENAMES:
        return True
    # AppleDouble wrapper files (resource forks), e.g., '._.DS_Store'
    if n.startswith("._"):
        core = n[2:]
        if core in NOISE_FILENAMES:
            return True
    return False


def _norm_text(s: str | None) -> str:
    s = (s or "").strip().lower()
    # Collapse underscores/dashes/spaces
    return re.sub(r"[\s_\-]+", " ", s)


def _has_meaningful_files(v: Variant) -> bool:
    files = getattr(v, 'files', []) or []
    for f in files:
        if getattr(f, 'is_dir', False):
            continue
        name = _norm(getattr(f, 'filename', ''))
        if not name or _is_noise_filename(name):
            continue
        ext = _norm(getattr(f, 'extension', ''))
        if getattr(f, 'is_archive', False) or ext in MEANINGFUL_EXTS or ext in ARCHIVE_EXTS:
            return True
    return False


def _only_noise_files(v: Variant) -> bool:
    files = getattr(v, 'files', []) or []
    saw_any = False
    for f in files:
        if getattr(f, 'is_dir', False):
            continue
        saw_any = True
        name = _norm(getattr(f, 'filename', ''))
        if not name:
            continue
        if not _is_noise_filename(name):
            return False
    return saw_any  # True only if there were files and all were noise


def _has_child_variants(v: Variant, all_rel_paths_lower: List[str]) -> bool:
    rel_lower = _norm(v.rel_path)
    if not rel_lower:
        return False
    for sep in ("\\", "/"):
        prefix = rel_lower + sep
        for rp in all_rel_paths_lower:
            if rp and rp != rel_lower and rp.startswith(prefix):
                return True
    return False


def _is_kit_container_rel(rel_path: str | None, all_rel_paths_lower: List[str]) -> tuple[bool, list[str]]:
    """Detect if a container folder looks like a modular kit (bodies/heads/weapons...).

    Returns (is_kit, matched_child_types)
    """
    rel_lower = _norm(rel_path)
    if not rel_lower:
        return (False, [])
    child_segs: Set[str] = set()
    for sep in ("\\", "/"):
        prefix = rel_lower + sep
        plen = len(prefix)
        for rp in all_rel_paths_lower:
            if rp and rp != rel_lower and rp.startswith(prefix):
                rest = rp[plen:]
                nxt = re.split(r"[\\/]+", rest)[0]
                n = _norm_text(nxt)
                if n:
                    child_segs.add(n)
    matched = sorted([s for s in child_segs if s in KIT_CHILD_TOKENS])
    return (len(matched) >= 2, matched)


def main() -> None:
    p = argparse.ArgumentParser(description="Prune invalid variants: container-only, noise-only, and known containers.")
    p.add_argument("--apply", action="store_true", help="Actually delete from DB (default: dry-run)")
    p.add_argument("--out", default=None, help="Optional JSON report path (timestamped if a directory)")
    p.add_argument(
        "--delete-path-equals",
        nargs="*",
        default=["sample_store"],
        help="Delete variants whose rel_path exactly equals any of these (case-insensitive).",
    )
    args = p.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path: Path | None = None
    if args.out:
        op = Path(args.out)
        if op.is_dir():
            out_path = op / f"prune_invalid_variants_{ts}{'_apply' if args.apply else ''}.json"
        else:
            out_path = op
    else:
        out_dir = ROOT / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"prune_invalid_variants_{ts}{'_apply' if args.apply else ''}.json"

    results = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "apply": args.apply,
        "delete_path_equals": args.delete_path_equals,
        "candidates": [],
        "counts": {
            "equals": 0,
            "container_only": 0,
            "noise_only": 0,
            "kit_containers_preserved": 0,
            "total": 0,
        },
    }

    equals_set = {s.lower() for s in (args.delete_path_equals or [])}

    with get_session() as session:
        variants = session.execute(select(Variant)).scalars().all()
        all_rel_paths = [_norm(v.rel_path) for v in variants]

        to_delete: List[int] = []
        preserved_kit_ids: List[int] = []
        for v in variants:
            rel_lower = _norm(v.rel_path)
            reason: str | None = None

            # 1) Delete by exact path equals (known containers like 'sample_store')
            if rel_lower and rel_lower in equals_set:
                reason = "equals"
            else:
                # 2) Container-only: no meaningful files but has child variants under it.
                # SAFETY: do not delete if the variant has any File rows at all.
                has_any_files = bool(getattr(v, 'files', []) or [])
                if not has_any_files and not _has_meaningful_files(v) and _has_child_variants(v, all_rel_paths):
                    # Preserve kit-like containers
                    is_kit, matched = _is_kit_container_rel(v.rel_path, all_rel_paths)
                    if is_kit:
                        preserved_kit_ids.append(v.id)
                        results["counts"]["kit_containers_preserved"] += 1  # type: ignore[index]
                        results["candidates"].append({
                            "variant_id": v.id,
                            "rel_path": v.rel_path,
                            "filename": v.filename,
                            "reason": "kit_container_preserved",
                            "kit_child_types": matched,
                        })
                        continue
                    reason = "container_only"
                # 3) Noise-only: has files, but all are OS noise (e.g., .DS_Store/Thumbs.db)
                elif not has_any_files and _only_noise_files(v):
                    reason = "noise_only"

            if reason:
                to_delete.append(v.id)
                results["counts"][reason] += 1  # type: ignore[index]
                results["candidates"].append({
                    "variant_id": v.id,
                    "rel_path": v.rel_path,
                    "filename": v.filename,
                    "reason": reason,
                })

        results["counts"]["total"] = len(to_delete)  # type: ignore[index]

        # On apply: make a DB backup and delete
        if args.apply and to_delete:
            # Backup DB file if we can locate it from env
            db_url = os.environ.get("STLMGR_DB_URL", "")
            if db_url.startswith("sqlite:///./"):
                rel_db = db_url[len("sqlite:///./"):]
                db_file = (ROOT / rel_db).resolve()
            elif db_url.startswith("sqlite:///"):
                db_file = Path(db_url[len("sqlite:///"):])
            else:
                db_file = None  # type: ignore[assignment]
            try:
                if db_file and db_file.exists():
                    backup = db_file.with_suffix(db_file.suffix + f".{ts}.bak")
                    shutil.copyfile(db_file, backup)
                    results["backup"] = str(backup)
            except Exception as e:
                results["backup_error"] = str(e)

            # Delete
            # Using ORM delete-orphan cascade on relationships
            q = session.query(Variant).filter(Variant.id.in_(to_delete))
            deleted = q.delete(synchronize_session=False)
            results["deleted"] = int(deleted)
            session.commit()

    if out_path:
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    print(json.dumps(results["counts"], indent=2))
    if results.get("backup"):
        print(f"DB backup: {results['backup']}")
    if results.get("deleted"):
        print(f"Deleted variants: {results['deleted']}")


if __name__ == "__main__":
    main()
