from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session
from scripts.30_normalize_match.normalize_inventory import build_franchise_alias_map, build_character_alias_map, tokens_from_variant  # type: ignore[attr-defined]
from scripts.30_normalize_match.apply_vocab_matches import load_franchise_token_strengths  # type: ignore[attr-defined]
from db.models import Variant


def main(argv: list[str] | None = None) -> int:
    fr_dir = ROOT / 'vocab' / 'franchises'
    with get_session() as s:
        fmap = build_franchise_alias_map(s)
        cmap = build_character_alias_map(s)
        print('franchise alias count:', len(fmap))
        print('character alias count:', len(cmap))
        print('sample franchise aliases (first 20):')
        for i, (k, v) in enumerate(sorted(fmap.items())[:20]):
            print(' ', k, '->', v)
        print('\nsample character aliases (first 20):')
        for i, (k, v) in enumerate(sorted(cmap.items())[:20]):
            print(' ', k, '->', v)

        token_strengths = load_franchise_token_strengths(fr_dir)
        print('\nfranchise token_strengths sample (first 20):')
        for i, (k, v) in enumerate(sorted(token_strengths.items())[:20]):
            print(' ', k, '->', v)

        ids = [68] + list(range(90, 119)) + list(range(155, 169))
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
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))
