#!/usr/bin/env python
"""
Audit coverage of columns in the `variant` table.

Outputs a sorted summary of non-null coverage per column and dumps a JSON
report optionally to --out. JSON-typed columns are treated as "empty" when
they equal [] or {}.

Usage (PowerShell):
  .\.venv\Scripts\python.exe .\scripts\diagnostics\audit_variant_coverage.py \
    --db .\data\stl_manager_v1.db \
    --out ("reports/variant_coverage_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".json")
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Tuple


def detect_json_like(colname: str) -> bool:
    """Heuristic: treat these names as JSON-typed in our schema."""
    jsonish = {
        "raw_path_tokens",
        "character_aliases",
        "loadout_variants",
        "supported_loadout_codes",
        "lineage_aliases",
        "faction_path",
        "franchise_hints",
        "nsfw_act_tags",
        "style_aesthetic_tags",
        "user_tags",
        "residual_tokens",
        "normalization_warnings",
        "english_tokens",
        "kit_child_types",
        "compatible_units",
        "compatible_factions",
        "compatible_model_group_ids",
        "compatible_variant_ids",
        "compatibility_assertions",
        "attachment_points",
        "replaces_parts",
    }
    return colname in jsonish


def count_coverage(con: sqlite3.Connection) -> Tuple[int, List[Tuple[str, int, int, int]]]:
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM variant")
    total = int(cur.fetchone()[0] or 0)

    cur.execute("PRAGMA table_info(variant)")
    cols = [r[1] for r in cur.fetchall()]

    results: List[Tuple[str, int, int, int]] = []  # (col, non_null, non_empty, total)
    for c in cols:
        # Non-null count
        cur.execute(f"SELECT COUNT(*) FROM variant WHERE {c} IS NOT NULL")
        non_null = int(cur.fetchone()[0] or 0)

        non_empty = non_null
        if detect_json_like(c):
            # Consider [] or {} as empty. Use .format with escaped braces for '{}'.
            cur.execute(
                "SELECT COUNT(*) FROM variant WHERE {c} IS NOT NULL "
                "AND TRIM(CAST({c} AS TEXT)) NOT IN ('[]','{{}}')".format(c=c)
            )
            non_empty = int(cur.fetchone()[0] or 0)

        results.append((c, non_null, non_empty, total))

    # Sort primarily by non_empty desc, then non_null, then name
    results.sort(key=lambda t: (t[2], t[1], t[0]), reverse=True)
    return total, results


def sample_values(con: sqlite3.Connection, cols: List[str], limit: int = 5) -> Dict[str, List[Any]]:
    cur = con.cursor()
    out: Dict[str, List[Any]] = {}
    for c in cols:
        try:
            cur.execute(f"SELECT DISTINCT {c} FROM variant WHERE {c} IS NOT NULL LIMIT {int(limit)}")
            vals = [r[0] for r in cur.fetchall()]
            out[c] = vals
        except Exception as e:
            out[c] = [f"ERROR: {e}"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=os.path.join("data", "stl_manager_v1.db"), help="Path to SQLite DB file")
    ap.add_argument("--out", default=None, help="Optional JSON report output path")
    ap.add_argument("--top", type=int, default=50, help="Show top-N columns by coverage (stdout)")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"DB not found: {args.db}")

    con = sqlite3.connect(args.db)
    total, rows = count_coverage(con)

    print(f"Variant rows: {total}")
    print("Column coverage (non-empty JSON where applicable):")
    shown = 0
    for c, non_null, non_empty, tot in rows:
        pct_null = 0 if tot == 0 else (non_null / tot * 100)
        pct_nonempty = 0 if tot == 0 else (non_empty / tot * 100)
        mark = " (JSON)" if detect_json_like(c) else ""
        print(f"- {c:28s}: non-null {non_null:4d}/{tot} ({pct_null:5.1f}%) | non-empty {non_empty:4d}/{tot} ({pct_nonempty:5.1f}%){mark}")
        shown += 1
        if shown >= args.top:
            break

    # Include a curated sample of fields that are often derivable
    focus_cols = [
        "english_tokens",
        "token_locale",
        "segmentation",
        "internal_volume",
        "support_state",
        "has_slicer_project",
        "is_kit_container",
        "kit_child_types",
        "parent_id",
        "intended_use_bucket",
        "asset_category",
        "scale_ratio_den",
        "scale_name",
        "game_system",
        "codex_faction",
        "codex_unit_name",
    ]
    print("\nSample distinct values for focus columns:")
    samples = sample_values(con, focus_cols, limit=5)
    for k, vals in samples.items():
        print(f"- {k}: {vals}")

    if args.out:
        report = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "db": os.path.abspath(args.db),
            "rows": total,
            "coverage": [
                {"column": c, "non_null": non_null, "non_empty": non_empty, "total": total}
                for c, non_null, non_empty, total in rows
            ],
            "samples": samples,
        }
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nWrote report: {args.out}")


if __name__ == "__main__":
    main()
