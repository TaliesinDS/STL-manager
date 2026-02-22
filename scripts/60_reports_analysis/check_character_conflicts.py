#!/usr/bin/env python3
"""Check for alias conflicts between `vocab/characters_tokenmap.md` and franchise manifests.

Usage: python scripts/60_reports_analysis/check_character_conflicts.py

Outputs a small JSON report to stdout and writes `reports/character_conflicts.json` when conflicts exist.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHAR_FILE = ROOT / "vocab" / "characters_tokenmap.md"
FRANCHISE_DIR = ROOT / "vocab" / "franchises"
OUT_REPORT = ROOT / "reports" / "character_conflicts.json"

ALIAS_RE = re.compile(r'"([^"]+)"')
CANON_RE = re.compile(r'^\s*([a-z0-9_+-]+):\s*$')


def load_char_map(path: Path) -> dict[str, list[str]]:
    """Parse a very small, conservative subset of the characters_tokenmap.md format.
    Returns mapping canonical -> [aliases].
    This parser is intentionally tolerant and does not require PyYAML.
    """
    if not path.exists():
        return {}
    cur = None
    cmap: dict[str, list[str]] = {}
    for ln in path.read_text(encoding='utf-8').splitlines():
        m = CANON_RE.match(ln)
        if m:
            cur = m.group(1).strip()
            cmap.setdefault(cur, [])
            continue
        if cur is None:
            continue
        for am in ALIAS_RE.findall(ln):
            if am:
                cmap[cur].append(am.strip().lower())
    return cmap


def load_franchise_aliases(fr_dir: Path) -> dict[str, dict]:
    """Return alias -> {franchise_file, franchise, character_canonical} mapping."""
    amap: dict[str, dict] = {}
    for p in sorted(fr_dir.glob('*.json')):
        try:
            j = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        franchise = j.get('franchise') or p.stem
        chars = j.get('characters') or []
        for c in chars:
            canon = c.get('canonical') or None
            aliases = c.get('aliases') or []
            # include canonical itself as an alias
            if canon:
                aliases = [canon] + list(aliases)
            for a in aliases:
                if not a:
                    continue
                key = str(a).strip().lower()
                amap.setdefault(key, []).append({
                    'file': str(p.relative_to(ROOT)),
                    'franchise': franchise,
                    'character_canonical': canon,
                })
    return amap


def main() -> int:
    cmap = load_char_map(CHAR_FILE)
    if not cmap:
        print('No characters_tokenmap.md found or empty; nothing to do.')
        return 0
    fr_aliases = load_franchise_aliases(FRANCHISE_DIR)

    conflicts = {}
    for canon, aliases in cmap.items():
        for a in aliases:
            if a in fr_aliases:
                conflicts.setdefault(canon, {})
                conflicts[canon].setdefault(a, []).extend(fr_aliases[a])

    if not conflicts:
        print('No conflicts detected between characters_tokenmap.md and franchise manifests.')
        return 0

    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(conflicts, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Conflicts detected: wrote report to {OUT_REPORT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
