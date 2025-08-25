from pathlib import Path
import sys
proj = Path(__file__).resolve().parent.parent
if str(proj) not in sys.path:
    sys.path.insert(0, str(proj))

from db.session import get_session
from scripts.normalize_inventory import build_franchise_alias_map, build_character_alias_map, tokens_from_variant
from scripts.apply_vocab_matches import load_franchise_token_strengths
from db.models import Variant

fr_dir = proj / 'vocab' / 'franchises'

with get_session() as s:
    fmap = build_franchise_alias_map(s)
    cmap = build_character_alias_map(s)
    print('franchise alias count:', len(fmap))
    print('character alias count:', len(cmap))
    print('sample franchise aliases (first 20):')
    for i, (k,v) in enumerate(sorted(fmap.items())[:20]):
        print(' ', k, '->', v)
    print('\nsample character aliases (first 20):')
    for i, (k,v) in enumerate(sorted(cmap.items())[:20]):
        print(' ', k, '->', v)

    token_strengths = load_franchise_token_strengths(fr_dir)
    print('\nfranchise token_strengths sample (first 20):')
    for i, (k,v) in enumerate(sorted(token_strengths.items())[:20]):
        print(' ', k, '->', v)

    # inspect specific variants (if present)
    ids = [68] + list(range(90,119)) + list(range(155,169))
    found = 0
    for vid in ids:
        v = s.query(Variant).filter_by(id=vid).one_or_none()
        if not v:
            continue
        found += 1
        toks = tokens_from_variant(s, v)
        print(f"\nVariant {vid} rel_path={v.rel_path} tokens=", toks[:50])
    if found == 0:
        print('\nNo variants found in the requested id ranges (IDs may differ in this DB).')
