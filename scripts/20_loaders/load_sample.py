from __future__ import annotations

import json
import sys
from pathlib import Path

from db.models import File, Variant
from db.session import get_session


def load_sample(fixture_path: Path) -> int:
    with fixture_path.open("r", encoding="utf-8") as fh:
        items = json.load(fh)

    inserted_variants = 0
    inserted_files = 0
    skipped_root_items = 0
    groups: dict[str, list[dict]] = {}
    IGNORED_LEAF_FOLDERS = {
        "hands",
        "supported",
        "unsupported",
        "stl",
        "supported stl",
        "unsupported stl",
        "supported_stl",
        "unsupported_stl",
        "lys",
    }
    for it in items:
        rel = it.get("rel_path") or ""
        # Skip any entries that are part of macOS metadata folders
        try:
            if "__macosx" in {part.lower() for part in Path(rel).parts}:
                continue
        except Exception:
            pass
        parent = Path(rel).parent
        try:
            while parent.name.lower() in IGNORED_LEAF_FOLDERS:
                parent = parent.parent
        except Exception:
            pass
        folder = parent.as_posix()
        if folder.lower() == "sample_store":
            skipped_root_items += 1
            continue
        groups.setdefault(folder, []).append(it)

    MODEL_EXTS = {".stl", ".obj", ".3mf", ".gltf", ".glb", ".step", ".stp", ".lys", ".chitubox", ".ctb", ".ztl"}

    with get_session() as session:
        for folder, files in groups.items():
            has_qualifying = False
            for f in files:
                ext = (f.get("extension") or "").lower()
                if f.get("is_archive", False) or ext in MODEL_EXTS:
                    has_qualifying = True
                    break
            if not has_qualifying:
                continue

            first = files[0]
            v = Variant(
                rel_path=folder,
                filename=None,
                extension=None,
                size_bytes=None,
                is_archive=False,
                residual_tokens=[t for f in files for t in (f.get("raw_path_tokens") or [])],
                token_version=first.get("token_version", 0),
            )
            session.add(v)
            session.flush()
            inserted_variants += 1

            for f in files:
                file_row = File(
                    variant_id=v.id,
                    rel_path=f.get("rel_path"),
                    filename=f.get("filename"),
                    extension=f.get("extension"),
                    size_bytes=f.get("size_bytes", 0),
                    is_archive=f.get("is_archive", False),
                    residual_tokens=f.get("raw_path_tokens") or [],
                    token_version=f.get("token_version", 0),
                )
                session.add(file_row)
                inserted_files += 1

        session.commit()

    if skipped_root_items:
        print(f"Skipped {skipped_root_items} loose file(s) directly under sample_store (not inserted).")

    return inserted_variants, inserted_files


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Load sample inventory JSON into DB")
    ap.add_argument("--file", required=True, help="Path to sample inventory JSON (e.g., data/sample_inventory.json)")
    args = ap.parse_args(argv)
    fixture = Path(args.file)
    if not fixture.exists():
        print("Sample fixture not found:", fixture)
        return 2
    v_count, f_count = load_sample(fixture)
    print(f"Inserted {v_count} variant(s) and {f_count} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
