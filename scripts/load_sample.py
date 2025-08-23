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
    # Group items by their parent folder (variant rel_path directory)
    groups: dict[str, list[dict]] = {}
    for it in items:
        folder = str(Path(it.get("rel_path")).parent)
        groups.setdefault(folder, []).append(it)

    with get_session() as session:
        for folder, files in groups.items():
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

    return inserted_variants, inserted_files


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    fixture = root / "tests" / "fixtures" / "sample_inventory.json"
    if not fixture.exists():
        print("Sample fixture not found:", fixture)
        raise SystemExit(1)

    v_count, f_count = load_sample(fixture)
    print(f"Inserted {v_count} variant(s) and {f_count} file(s).")
