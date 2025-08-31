#!/usr/bin/env python3
"""Report coverage counts for key Variant metadata fields."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session
from db.models import Variant
from sqlalchemy import func


def main(argv: list[str] | None = None) -> int:
    with get_session() as s:
        total = s.query(func.count(Variant.id)).scalar()
        token_version_set = s.query(func.count(Variant.id)).filter(Variant.token_version.isnot(None)).scalar()
        designer_set = s.query(func.count(Variant.id)).filter(Variant.designer.isnot(None)).scalar()
        franchise_set = s.query(func.count(Variant.id)).filter(Variant.franchise.isnot(None)).scalar()
        residual_set = s.query(func.count(Variant.id)).filter(Variant.residual_tokens != None).scalar()  # noqa: E711
        content_set = s.query(func.count(Variant.id)).filter(Variant.content_flag.isnot(None)).scalar()
        print('total_variants:', total)
        print('token_version_set:', token_version_set)
        print('designer_set:', designer_set)
        print('franchise_set:', franchise_set)
        print('residual_tokens_set:', residual_set)
        print('content_flag_set:', content_set)
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))
