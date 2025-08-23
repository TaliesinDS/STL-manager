import json
import sys
from pathlib import Path

# Ensure project root is on sys.path so `from db...` imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant


def load_sample(fixture_path: Path) -> int:
    with fixture_path.open("r", encoding="utf-8") as fh:
        items = json.load(fh)

    inserted = 0
    with get_session() as session:
        for it in items:
            # Map fixture keys to model columns; Variant doesn't have raw_path_tokens,
            # so store that data in residual_tokens for now.
            v = Variant(
                rel_path=it.get("rel_path"),
                filename=it.get("filename"),
                extension=it.get("extension"),
                size_bytes=it.get("size_bytes", 0),
                is_archive=it.get("is_archive", False),
                residual_tokens=it.get("raw_path_tokens") or [],
                token_version=it.get("token_version", 0),
            )
            session.add(v)
            inserted += 1
        session.commit()

    return inserted


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    fixture = root / "tests" / "fixtures" / "sample_inventory.json"
    if not fixture.exists():
        print("Sample fixture not found:", fixture)
        raise SystemExit(1)

    n = load_sample(fixture)
    print(f"Inserted {n} sample records.")
