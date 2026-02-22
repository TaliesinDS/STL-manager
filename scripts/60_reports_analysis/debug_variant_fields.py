#!/usr/bin/env python3
"""Diagnostic helper: report counts for normalized fields on Variant rows and print sample rows."""
from __future__ import annotations

import json
import sys

from db.models import Variant
from db.session import get_session

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


def main(argv: list[str] | None = None) -> int:
    with get_session() as session:
        totals = {}
        for f in FIELDS:
            col = getattr(Variant, f)
            if f in ("pc_candidate_flag", "has_bust_variant"):
                cnt = session.query(Variant).filter(col.is_(True)).count()
            else:
                if hasattr(col, 'isnot'):
                    cnt = session.query(Variant).filter(col.isnot(None)).count()
                else:
                    cnt = session.query(Variant).filter(col != None).count()  # noqa: E711
            totals[f] = cnt
        print(json.dumps({"counts": totals}, indent=2))

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
            if len(samples) >= 20:
                break
        print("Sample variants with non-empty normalized fields (up to 20):")
        print(json.dumps(samples, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))
