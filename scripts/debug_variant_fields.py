#!/usr/bin/env python3
"""Diagnostic helper: report counts for normalized fields on Variant rows and print sample rows.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant
from sqlalchemy import and_

FIELDS = [
    "support_state",
    "internal_volume",
    "segmentation",
    "part_pack_type",
    "scale_ratio_den",
    "height_mm",
    "content_flag",
    "pc_candidate_flag",
    "has_bust_variant",
]

def pretty(v: Variant):
    return {
        "id": v.id,
        "rel_path": v.rel_path,
        "support_state": v.support_state,
        "internal_volume": v.internal_volume,
        "segmentation": v.segmentation,
        "part_pack_type": v.part_pack_type,
        "scale_ratio_den": v.scale_ratio_den,
        "height_mm": v.height_mm,
        "content_flag": v.content_flag,
        "pc_candidate_flag": v.pc_candidate_flag,
        "has_bust_variant": v.has_bust_variant,
        "residual_tokens": v.residual_tokens,
    }

def main():
    with get_session() as session:
            totals = {}
            for f in FIELDS:
                col = getattr(Variant, f)
                # Special-case booleans: count True only
                if f in ("pc_candidate_flag", "has_bust_variant"):
                    cnt = session.query(Variant).filter(col.is_(True)).count()
                else:
                    # For others count non-null and non-empty strings
                    if hasattr(col, 'isnot'):
                        cnt = session.query(Variant).filter(col.isnot(None)).count()
                    else:
                        cnt = session.query(Variant).filter(col != None).count()
                totals[f] = cnt
            print(json.dumps({"counts": totals}, indent=2))

            # Also print up to 20 sample variants that have any non-null/true of those fields
            q = session.query(Variant)
            samples = []
            for v in q.limit(1000).all():
                any_set = False
                for f in FIELDS:
                    val = getattr(v, f)
                    if f in ("pc_candidate_flag", "has_bust_variant"):
                        if val is True:
                            any_set = True
                            break
                    else:
                        if val not in (None, False, "", [], {}):
                            any_set = True
                            break
                if any_set:
                    samples.append(pretty(v))
                # stop once we have enough samples
                if len(samples) >= 20:
                    break
            print("Sample variants with non-empty normalized fields (up to 20):")
            print(json.dumps(samples, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    raise SystemExit(main())
