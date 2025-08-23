#!/usr/bin/env python3
"""
Load designers_tokenmap.md into the DB as VocabEntry(domain='designer').

Usage:
    .venv\Scripts\Activate.ps1
    python scripts\load_designers.py vocab\designers_tokenmap.md
"""
import sys
import re
import ast
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, ".")
try:
    from db.session import SessionLocal
    from db.models import VocabEntry
except Exception as e:
    print("ERROR: could not import db.session or db.models:", e)
    raise

FENCE_RE = re.compile(r"^```")
ENTRY_RE = re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*:\s*(\[.*\])\s*$")

def parse_tokenmap(path: Path):
    text = path.read_text(encoding="utf8")
    lines = text.splitlines()
    inside = False
    result = {}
    for ln in lines:
        if FENCE_RE.match(ln.strip()):
            inside = not inside
            continue
        if not inside:
            continue
        ln = ln.rstrip()
        if not ln or ln.lstrip().startswith("#"):
            continue
        m = ENTRY_RE.match(ln)
        if not m:
            continue
        key = m.group(1).strip()
        aliases_str = m.group(2)
        try:
            aliases = ast.literal_eval(aliases_str)
            if not isinstance(aliases, (list, tuple)):
                aliases = [aliases]
            aliases = [str(a) for a in aliases]
        except Exception as e:
            print(f"WARN: failed to parse aliases for {key}: {e}")
            aliases = []
        result[key] = aliases
    return result


def normalize_alias(a: str) -> str:
    return a.strip().lower()


def detect_conflicts(entries: dict, session):
    """Detect alias collisions within the provided entries and against existing DB rows.
    Returns a tuple (infile_conflicts, db_conflicts) where each is a dict alias->set(canonicals).
    """
    infile_map = defaultdict(set)
    for canonical, aliases in entries.items():
        # include canonical itself as an alias for detection
        infile_map[normalize_alias(canonical)].add(canonical)
        for a in aliases:
            infile_map[normalize_alias(a)].add(canonical)

    infile_conflicts = {a: cs for a, cs in infile_map.items() if len(cs) > 1}

    # build existing alias map from DB
    db_rows = session.query(VocabEntry).filter_by(domain="designer").all()
    db_map = defaultdict(set)
    for r in db_rows:
        db_map[normalize_alias(r.key)].add(r.key)
        for a in (r.aliases or []):
            db_map[normalize_alias(a)].add(r.key)

    # conflicts where alias maps to multiple canonicals across file+db
    combined = defaultdict(set)
    for a, cs in infile_map.items():
        combined[a].update(cs)
    for a, cs in db_map.items():
        combined[a].update(cs)

    db_conflicts = {a: cs for a, cs in combined.items() if len(cs) > 1}
    return infile_conflicts, db_conflicts

def sniff_map_version(path: Path):
    text = path.read_text(encoding="utf8")
    m = re.search(r"designers_map_version\s*:\s*(\d+)", text)
    if m:
        return int(m.group(1))
    return None

def upsert_vocab_entries(session, entries: dict, source_file: str, map_version=None):
    # detect conflicts and annotate meta
    infile_conflicts, db_conflicts = detect_conflicts(entries, session)
    if infile_conflicts:
        print("Found in-file alias conflicts (alias -> canonicals):")
        for a, cs in infile_conflicts.items():
            print(f"  {a} -> {sorted(list(cs))}")
    if db_conflicts:
        print("Found conflicts with existing DB entries (alias -> canonicals):")
        for a, cs in db_conflicts.items():
            print(f"  {a} -> {sorted(list(cs))}")

    for canonical, aliases in entries.items():
        normalized_aliases = [a.strip() for a in aliases if a and a.strip()]
        meta = {"source_file": str(source_file)}
        if map_version is not None:
            meta["map_version"] = map_version
        # attach conflict hints for this canonical if any of its aliases are conflicted
        conflicts_for_key = []
        for a in normalized_aliases + [canonical]:
            na = normalize_alias(a)
            if na in db_conflicts or na in infile_conflicts:
                conflicts_for_key.append(na)
        if conflicts_for_key:
            meta["conflicts_with"] = list(sorted(set(conflicts_for_key)))

        ve = session.query(VocabEntry).filter_by(domain="designer", key=canonical).one_or_none()
        if ve:
            ve.aliases = normalized_aliases
            ve.meta = meta
        else:
            ve = VocabEntry(domain="designer", key=canonical, aliases=normalized_aliases, meta=meta)
            session.add(ve)
    session.commit()

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/load_designers.py vocab/designers_tokenmap.md")
        sys.exit(2)
    path = Path(sys.argv[1])
    if not path.exists():
        print("File not found:", path)
        sys.exit(2)
    entries = parse_tokenmap(path)
    map_version = sniff_map_version(path)
    session = SessionLocal()
    try:
        upsert_vocab_entries(session, entries, source_file=path.name, map_version=map_version)
        print(f"Upserted {len(entries)} designer vocab entries (map_version={map_version})")
    finally:
        session.close()

if __name__ == "__main__":
    main()
