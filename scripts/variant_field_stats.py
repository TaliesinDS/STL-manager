#!/usr/bin/env python3
"""Report coverage counts for key Variant metadata fields.

Usage:
  .venv\Scripts\python.exe scripts\variant_field_stats.py
"""
from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant
from sqlalchemy import func


def main():
    with get_session() as s:
        total = s.query(func.count(Variant.id)).scalar()
        token_version_set = s.query(func.count(Variant.id)).filter(Variant.token_version.isnot(None)).scalar()
        designer_set = s.query(func.count(Variant.id)).filter(Variant.designer.isnot(None)).scalar()
        franchise_set = s.query(func.count(Variant.id)).filter(Variant.franchise.isnot(None)).scalar()
        residual_set = s.query(func.count(Variant.id)).filter(Variant.residual_tokens != None).scalar()
        content_set = s.query(func.count(Variant.id)).filter(Variant.content_flag.isnot(None)).scalar()
        print('total_variants:', total)
        print('token_version_set:', token_version_set)
        print('designer_set:', designer_set)
        print('franchise_set:', franchise_set)
        print('residual_tokens_set:', residual_set)
        print('content_flag_set:', content_set)


if __name__ == '__main__':
    main()
