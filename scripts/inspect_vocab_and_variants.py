from pathlib import Path
import sys
proj = Path(__file__).resolve().parent.parent
if str(proj) not in sys.path:
    sys.path.insert(0, str(proj))
from db.session import get_session
from db.models import VocabEntry, Variant
with get_session() as s:
    total_vocab = s.query(VocabEntry).count()
    franchises = s.query(VocabEntry).filter_by(domain='franchise').count()
    characters = s.query(VocabEntry).filter_by(domain='character').count()
    print('VocabEntry total:', total_vocab)
    print('franchise entries:', franchises)
    print('character entries:', characters)
    print('\nSample franchise rows:')
    for r in s.query(VocabEntry).filter_by(domain='franchise').limit(5):
        print('-', r.key, 'aliases=', (r.aliases or [])[:10])
    print('\nSample character rows:')
    for r in s.query(VocabEntry).filter_by(domain='character').limit(5):
        print('-', r.key, 'aliases=', (r.aliases or [])[:10])
    vt = s.query(Variant).count()
    vt_tokens = s.query(Variant).filter(Variant.residual_tokens != None).count()
    print('\nVariants total:', vt)
    print('Variants with residual_tokens not null:', vt_tokens)
