from pathlib import Path
import sys
proj = Path(__file__).resolve().parent.parent
if str(proj) not in sys.path:
    sys.path.insert(0, str(proj))
from db.session import get_session
from db.models import File, Variant
with get_session() as s:
    # find a file with 'Ryuko' in rel_path (case-insensitive not supported in sqlite LIKE by default)
    f = s.query(File).filter(File.rel_path.like('%Ryuko%')).first()
    if f:
        print('Found file with Ryuko: id', f.id)
        print('rel_path:', f.rel_path)
        print('file residual_tokens sample:', (f.residual_tokens or [])[:20])
        v = s.query(Variant).get(f.variant_id)
        print('variant residual_tokens sample:', (v.residual_tokens or [])[:20])
    else:
        print('No Ryuko file found; printing sample file id=1 tokens')
        f2 = s.query(File).get(1)
        print('File 1 rel_path:', f2.rel_path)
        print('File 1 residual_tokens:', (f2.residual_tokens or [])[:40])
        v2 = s.query(Variant).get(f2.variant_id)
        print('Variant 1 residual_tokens:', (v2.residual_tokens or [])[:40])
