"""Merge leaf Variants with trivial folder names (e.g., 'Hands') into their parent Variant.

Dry-run by default: prints planned merges. Use --apply to modify the DB.

Usage (PowerShell):
  $env:STLMGR_DB_URL="sqlite:///./data/stl_manager_v1.db"
  .\.venv\Scripts\python.exe .\scripts\cleanup_merge_leaf_variants.py --leaf hands --apply
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session  # type: ignore
from db.models import Variant, File, VariantUnitLink  # type: ignore


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Merge leaf variants (e.g., 'Hands') into their parent variant.")
    ap.add_argument("--leaf", dest="leaf_names", action="append", default=["hands"],
                    help="Leaf folder name to merge into parent (repeatable). Default: hands")
    ap.add_argument("--apply", action="store_true", help="Apply changes to DB (default: dry-run)")
    ap.add_argument("--limit", type=int, default=0, help="Max number of leaf variants to process (0 = all)")
    return ap.parse_args(argv)


def norm_sep(s: str) -> str:
    return s.replace("\\", "/")


def is_leaf_match(rel_path: str, leaf: str) -> bool:
    rp = norm_sep(rel_path).strip().lower()
    return rp.endswith("/" + leaf.lower())


TRIVIAL_FOLDERS = {"hands", "supported", "unsupported", "stl", "supported stl", "unsupported stl", "supported_stl", "unsupported_stl", "lys"}


def parent_path(rel_path: str) -> str:
    """Return the nearest non-trivial parent path for grouping."""
    p = Path(rel_path)
    while p.name.lower() in TRIVIAL_FOLDERS:
        p = p.parent
    return p.parent.as_posix()


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    leaves = [l.strip().lower() for l in (args.leaf_names or []) if l and l.strip()]
    if not leaves:
        print("No leaf names provided; nothing to do.")
        return 0

    processed = 0
    planned_merges = 0
    with get_session() as session:
        q = session.query(Variant).all()
        leaf_variants: list[Variant] = [v for v in q if any(is_leaf_match(v.rel_path or "", lf) for lf in leaves)]
        if args.limit and args.limit > 0:
            leaf_variants = leaf_variants[: args.limit]

        for leaf_var in leaf_variants:
            processed += 1
            leaf_path = leaf_var.rel_path or ""
            parent_rel = parent_path(leaf_path)
            parent_var = session.query(Variant).filter(Variant.rel_path == parent_rel).one_or_none()
            if not parent_var:
                print(f"INFO: Creating parent variant '{parent_rel}' for leaf '{leaf_path}'.")
                parent_var = Variant(
                    rel_path=parent_rel,
                    filename=None,
                    extension=None,
                    size_bytes=None,
                    is_archive=False,
                )
                session.add(parent_var)
                session.flush()

            files = session.query(File).filter(File.variant_id == leaf_var.id).all()
            links = session.query(VariantUnitLink).filter(VariantUnitLink.variant_id == leaf_var.id).all()
            print(f"Merge leaf '{leaf_path}' (id={leaf_var.id}) -> parent '{parent_rel}' (id={parent_var.id}) | files={len(files)} links={len(links)}")
            planned_merges += 1

            if args.apply:
                # Reassign files
                for fr in files:
                    fr.variant_id = parent_var.id
                # Move links as well (rare for leafs but safe)
                for lk in links:
                    lk.variant_id = parent_var.id
                # Delete the leaf variant
                session.delete(leaf_var)

        if args.apply:
            session.commit()

    print(f"Processed {processed} leaf candidate(s); {'applied' if args.apply else 'planned'} merges: {planned_merges}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
