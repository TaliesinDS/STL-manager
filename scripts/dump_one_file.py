from pathlib import Path
import sys
proj = Path(__file__).resolve().parent.parent
if str(proj) not in sys.path:
    sys.path.insert(0, str(proj))
from db.session import get_session
from db.models import File
with get_session() as s:
    f = s.query(File).first()
    if f:
        print('Sample File.rel_path:', f.rel_path)
        print('Sample File.filename:', f.filename)
    else:
        print('No File rows found')
