#!/usr/bin/env python3
"""Apply proposed changes extracted from a dry-run report file.

This reads the provided report (default: reports/match_franchise_dryrun_after_apply.txt)
and applies the `changes` for each `variant_id` found. Conservative by default:
only sets fields when empty unless `--force` is used. Use `--apply` to commit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.session import get_session
from db.models import Variant


def parse_proposals(report_path: Path):
    text = report_path.read_text(encoding='utf-8')
    objs = []
    # Robust brace-balance parser: collect chunks that are JSON objects
    buf = []
    depth = 0
    in_chunk = False
    for ch in text:
        if ch == '{':
            depth += 1
            in_chunk = True
        if in_chunk:
            buf.append(ch)
        if ch == '}':
            depth -= 1
            if depth == 0 and in_chunk:
                chunk = ''.join(buf)
                buf = []
                in_chunk = False
                try:
                    objs.append(json.loads(chunk))
                except Exception:
                    # ignore parse errors for partial chunks
                    continue
    return objs


def apply_changes(proposals, apply: bool, force: bool):
    applied = []
    with get_session() as session:
        for p in proposals:
            vid = p.get('variant_id')
            changes = p.get('changes', {})
            v = session.query(Variant).filter_by(id=vid).one_or_none()
            if not v:
                print(f"Variant {vid} not found; skipping")
                continue
            changed = False
            # helper
            def set_if_empty(field, value):
                nonlocal changed
                if value is None:
                    return
                cur = getattr(v, field)
                if (cur in (None, '', [], {}) ) or force:
                    setattr(v, field, value)
                    changed = True

            set_if_empty('franchise', changes.get('franchise'))
            # Backwards compatibility: if report proposes codex_unit_name, treat
            # it as a character name unless you have enabled Phase-2 codex unit extraction.
            if changes.get('codex_unit_name'):
                set_if_empty('character_name', changes.get('codex_unit_name'))
                # also record the token as a single-item alias if provided
                if changes.get('codex_unit_token'):
                    set_if_empty('character_aliases', [changes.get('codex_unit_token')])
            # New-style proposals may include character_name / character_aliases
            set_if_empty('character_name', changes.get('character_name'))
            if changes.get('character_aliases'):
                set_if_empty('character_aliases', changes.get('character_aliases'))
            set_if_empty('faction_general', changes.get('faction_general'))
            # normalization_warnings: merge
            if changes.get('normalization_warnings'):
                curw = v.normalization_warnings or []
                neww = list(curw)
                for w in changes.get('normalization_warnings'):
                    if w not in neww:
                        neww.append(w)
                if neww != curw:
                    v.normalization_warnings = neww
                    changed = True

            if changed:
                print(f"Would apply to Variant {vid}: {changes}")
                if apply:
                    session.commit()
                    print(f"Applied to Variant {vid}")
                    applied.append(vid)

    print(f"Done. Applied to {len(applied)} variants.")
    return applied


def parse_args(argv):
    ap = argparse.ArgumentParser(description='Apply proposals from a dry-run report')
    ap.add_argument('--report', default='reports/match_franchise_dryrun_after_apply.txt')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--force', action='store_true')
    return ap.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    report = Path(args.report)
    if not report.exists():
        print(f"Report not found: {report}")
        return 2
    proposals = parse_proposals(report)
    print(f"Found {len(proposals)} proposal objects in report {report}")
    apply_changes(proposals, apply=args.apply, force=args.force)


if __name__ == '__main__':
    import sys as _sys
    raise SystemExit(main(_sys.argv[1:]))
