from pathlib import Path
import sys

# Ensure project root is on sys.path so top-level imports like `from db.models`
# work even when this script is executed as `python scripts/init_db.py`.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.models import Base
from db.session import engine


def init_db() -> None:
    # Ensure the SQLite parent directory exists (SQLAlchemy won't create parent dirs)
    try:
        db_file = Path(engine.url.database)
        if db_file and db_file.parent:
            db_file.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # If we can't determine a filesystem path (e.g., non-sqlite URL), ignore
        pass

    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    print("Creating database schema...")
    init_db()
    print("Done.")
