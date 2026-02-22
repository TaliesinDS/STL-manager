#!/usr/bin/env python3
"""
Load JSON franchise files from `vocab/franchises/` into the DB.

Canonical location: scripts/20_loaders/load_franchises.py
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import List, Optional

from db.models import Character, VocabEntry
from db.session import SessionLocal


def load_franchise_file(path: Path):
    try:
        obj = json.loads(path.read_text(encoding="utf8"))
    except Exception as e:
        print(f"SKIP: failed to parse {path}: {e}")
        return None
    key = obj.get("id") or obj.get("key") or path.stem
    aliases = obj.get("aliases") or obj.get("alias") or []
    if isinstance(aliases, str):
        aliases = [aliases]
    aliases = [str(a) for a in aliases]
    characters = obj.get("characters") or []
    return {"key": str(key), "aliases": aliases, "characters": characters, "meta": {"source_file": path.name}}


def normalize_name_for_key(name: str) -> str:
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name)
    s = s.lower()
    out_chars = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat.startswith("P") or cat.startswith("S"):
            out_chars.append(" ")
        else:
            out_chars.append(ch)
    s = "".join(out_chars)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def dedupe_characters(session, commit: bool = False, preview: Optional[int] = None):
    rows = session.query(Character).all()
    groups = {}
    for r in rows:
        norm_name = normalize_name_for_key(r.name)
        norm_franchise = normalize_name_for_key(r.franchise or "")
        comp_key = f"{norm_name}||{norm_franchise}"
        groups.setdefault(comp_key, []).append(r)
    dup_groups = {k: v for k, v in groups.items() if len(v) > 1 and k}
    report = {
        "groups_total": len(groups),
        "duplicate_groups": len(dup_groups),
        "duplicate_rows": sum(len(v) for v in dup_groups.values()),
    }
    preview_samples = []
    for k, group in list(dup_groups.items())[: (preview or 10)]:
        try:
            norm_name, norm_fr = k.split("||", 1)
        except Exception:
            norm_name, norm_fr = k, ""
        preview_samples.append({
            "norm_name": norm_name,
            "norm_franchise": norm_fr,
            "rows": [(r.id, r.name, r.franchise, r.aliases) for r in group],
        })
    if not commit:
        report["preview"] = preview_samples
        return report
    merged_count = 0
    deleted_count = 0
    for k, group in dup_groups.items():
        canonical = sorted(group, key=lambda r: r.id)[0]
        for other in group:
            if other.id == canonical.id:
                continue
            a_can = set(canonical.aliases or [])
            a_other = set(other.aliases or [])
            canonical.aliases = list(sorted(a_can.union(a_other)))
            if not canonical.actor_likeness and other.actor_likeness:
                canonical.actor_likeness = other.actor_likeness
            if not canonical.actor_confidence and other.actor_confidence:
                canonical.actor_confidence = other.actor_confidence
            if not canonical.info_url and other.info_url:
                canonical.info_url = other.info_url
            if not canonical.franchise and other.franchise:
                canonical.franchise = other.franchise
            session.delete(other)
            deleted_count += 1
        merged_count += 1
    session.commit()
    report.update({"merged_groups": merged_count, "deleted_rows": deleted_count})
    return report


def upsert_franchises(dir_path: Path, commit: bool = False, preview: Optional[int] = None):
    session = SessionLocal()
    try:
        files = sorted(dir_path.glob("*.json"))
        franchises_total = 0
        franchises_will_create = 0
        franchises_will_update = 0
        characters_total = 0
        characters_will_create = 0
        characters_will_update = 0
        for p in files:
            info = load_franchise_file(p)
            if not info:
                continue
            key = info["key"]
            aliases = info["aliases"]
            meta = info.get("meta", {})
            franchises_total += 1
            ve = session.query(VocabEntry).filter_by(domain="franchise", key=key).one_or_none()
            if ve:
                franchises_will_update += 1
                if commit:
                    ve.aliases = aliases
                    ve.meta = meta
            else:
                franchises_will_create += 1
                if commit:
                    ve = VocabEntry(domain="franchise", key=key, aliases=aliases, meta=meta)
                    session.add(ve)
            for c in info.get("characters", []):
                if isinstance(c, str):
                    name = c
                    aliases_c: List[str] = []
                    actor = None
                    actor_conf = None
                    info_url = None
                elif isinstance(c, dict):
                    name = c.get("name") or c.get("id") or c.get("canonical") or c.get("canonical_name")
                    aliases_c = c.get("aliases") or c.get("alias") or []
                    actor = c.get("actor_likeness") or c.get("actor") or c.get("actor_name")
                    actor_conf = c.get("actor_confidence") or c.get("actor_confidence_score")
                    info_url = c.get("info_url") or c.get("url") or c.get("wiki_url")
                else:
                    continue
                if not name:
                    continue
                aliases_c = [str(a) for a in aliases_c] if aliases_c else []
                characters_total += 1
                q = session.query(Character).filter_by(name=name)
                try:
                    ch = q.one_or_none()
                except Exception:
                    ch = q.order_by(Character.id).limit(1).one_or_none()
                if ch:
                    characters_will_update += 1
                    if commit:
                        ch.aliases = aliases_c
                        ch.franchise = key
                        if actor:
                            ch.actor_likeness = actor
                        if actor_conf:
                            ch.actor_confidence = actor_conf
                        if info_url:
                            ch.info_url = info_url
                else:
                    characters_will_create += 1
                    if commit:
                        ch = Character(name=name, aliases=aliases_c, franchise=key, actor_likeness=actor, actor_confidence=actor_conf, info_url=info_url)
                        session.add(ch)
        if commit:
            session.commit()
            return {
                "committed": True,
                "franchises_total": franchises_total,
                "franchises_created": franchises_will_create,
                "franchises_updated": franchises_will_update,
                "characters_total": characters_total,
                "characters_created": characters_will_create,
                "characters_updated": characters_will_update,
            }
        else:
            session.rollback()
            return {
                "committed": False,
                "franchises_total": franchises_total,
                "franchises_will_create": franchises_will_create,
                "franchises_will_update": franchises_will_update,
                "characters_total": characters_total,
                "characters_will_create": characters_will_create,
                "characters_will_update": characters_will_update,
            }
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Load franchises and characters from JSON files (dry-run by default)")
    p.add_argument("dir", help="Path to vocab/franchises folder")
    p.add_argument("--commit", action="store_true", help="Apply changes to the DB (default: dry-run)")
    p.add_argument("--dedupe", action="store_true", help="Run Character dedupe before upsert")
    p.add_argument("--preview", type=int, default=None, help="Preview up to N duplicate groups")
    args = p.parse_args(argv)
    dirp = Path(args.dir)
    if not dirp.exists() or not dirp.is_dir():
        print("Directory not found:", dirp)
        return 2
    if args.dedupe:
        session_dedupe = SessionLocal()
        try:
            dedupe_report = dedupe_characters(session_dedupe, commit=args.commit, preview=args.preview)
            if args.commit:
                print("Dedupe: merged_groups=", dedupe_report.get("merged_groups"), "deleted_rows=", dedupe_report.get("deleted_rows"))
            else:
                print("Dedupe (dry-run): duplicate_groups=", dedupe_report.get("duplicate_groups"), "duplicate_rows=", dedupe_report.get("duplicate_rows"))
                if dedupe_report.get("preview"):
                    print("Dedupe preview (first groups):")
                    for sample in dedupe_report["preview"]:
                        print(sample)
        finally:
            session_dedupe.close()
    result = upsert_franchises(dirp, commit=args.commit, preview=args.preview)
    if result.get("committed"):
        print("Committed changes to DB")
        print(f"franchises total={result['franchises_total']} created={result['franchises_created']} updated={result['franchises_updated']}")
        print(f"characters total={result['characters_total']} created={result['characters_created']} updated={result['characters_updated']}")
    else:
        print("Dry-run (no changes applied). Summary of what would happen:")
        print(f"franchises total={result['franchises_total']} would_create={result['franchises_will_create']} would_update={result['franchises_will_update']}")
        print(f"characters total={result['characters_total']} would_create={result['characters_will_create']} would_update={result['characters_will_update']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
