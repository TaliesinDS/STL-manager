#!/usr/bin/env python3
"""Filter a dry-run proposals report to remove faction_general changes.

This reuses the same brace-balanced JSON-object parser approach used by
`apply_proposals_from_report.py` so it's robust to the existing report format.

Behavior:
- Remove the `faction_general` key from each proposal's `changes` map.
- If a proposal's `changes` map becomes empty after removal, drop the
  proposal entirely (we don't want to apply faction-only suggestions).
- Write the filtered proposals to an output file, one JSON object per line
  (the apply script's parser can still read it).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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


def filter_proposals(proposals: list[dict]) -> list[dict]:
    out = []
    for p in proposals:
        changes = dict(p.get('changes') or {})
        # Remove faction_general from changes (we don't want to use faction hints
        # as franchise signals; factions are for tabletop). This prevents the
        # apply step from setting faction-based franchise fields accidentally.
        if 'faction_general' in changes:
            changes.pop('faction_general', None)
        # If the only change was faction_general, skip this proposal entirely
        if not changes:
            continue
        newp = dict(p)
        newp['changes'] = changes
        out.append(newp)
    return out


def write_proposals(proposals: list[dict], out_path: Path):
    # Write one JSON object per line for easy parsing by existing tools
    with out_path.open('w', encoding='utf-8') as fh:
        for p in proposals:
            fh.write(json.dumps(p, ensure_ascii=False))
            fh.write('\n')


def parse_args(argv: list[str]):
    ap = argparse.ArgumentParser(description='Filter proposals report to remove faction_general suggestions')
    ap.add_argument('--in', dest='infile', required=True, help='Input proposals report')
    ap.add_argument('--out', dest='outfile', required=True, help='Output filtered proposals file')
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    ip = Path(args.infile)
    op = Path(args.outfile)
    if not ip.exists():
        print(f'Input report not found: {ip}')
        return 2
    proposals = parse_proposals(ip)
    print(f'Parsed {len(proposals)} proposal objects from {ip}')
    filtered = filter_proposals(proposals)
    print(f'Filtered down to {len(filtered)} proposals (removed faction_general-only proposals and stripped faction_general)')
    op.parent.mkdir(parents=True, exist_ok=True)
    write_proposals(filtered, op)
    print(f'Wrote filtered proposals to {op}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
