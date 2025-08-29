import json
import sys
from pathlib import Path

# Ensure project root is on sys.path so `from db...` imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant, File


def load_sample(fixture_path: Path) -> int:
    with fixture_path.open("r", encoding="utf-8") as fh:
        items = json.load(fh)

    inserted_variants = 0
    inserted_files = 0
    skipped_root_items = 0
    # Group items by their parent folder (variant rel_path directory)
    # and skip any files that live directly under the top-level container
    # folder "sample_store". These are considered loose files/archives and
    # should not create a Variant nor be inserted as File rows.
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
        parent = Path(rel).parent
        # Collapse trivial trailing folders by walking up until a non-trivial parent
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

    # Qualifying model/project extensions (treated as 3D-print files)
    MODEL_EXTS = {".stl", ".obj", ".3mf", ".gltf", ".glb", ".step", ".stp", ".lys", ".chitubox", ".ctb", ".ztl"}

    with get_session() as session:
        for folder, files in groups.items():
            # Only create a Variant if the folder contains at least one model or archive file
            has_qualifying = False
            for f in files:
                ext = (f.get("extension") or "").lower()
                if f.get("is_archive", False) or ext in MODEL_EXTS:
                    has_qualifying = True
                    break
            if not has_qualifying:
                # Skip junk/preview-only folders; do not create a Variant
                continue

            # Create a Variant record for the folder
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
            session.flush()  # assign v.id
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


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    fixture = root / "tests" / "fixtures" / "sample_inventory.json"
    if not fixture.exists():
        print("Sample fixture not found:", fixture)
        raise SystemExit(1)

    v_count, f_count = load_sample(fixture)
    print(f"Inserted {v_count} variant(s) and {f_count} file(s).")
