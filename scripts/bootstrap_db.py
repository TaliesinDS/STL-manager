from pathlib import Path
import sys
# ensure project root on sys.path
proj = Path(__file__).resolve().parent.parent
if str(proj) not in sys.path:
    sys.path.insert(0, str(proj))
from db.session import engine
from db.models import Base
print('Using DB URL from engine:', engine.url)
Base.metadata.create_all(bind=engine)
print('Created tables (if they did not exist).')
