from db.models import Base
from db.session import engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    print("Creating database schema...")
    init_db()
    print("Done.")
