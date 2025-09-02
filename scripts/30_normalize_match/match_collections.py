from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy import create_engine, select, and_
from sqlalchemy.orm import Session

# Ensure repository root is on sys.path for local package imports
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from ruamel.yaml import YAML
except Exception:
    YAML = None  # type: ignore

from db.models import Variant


@dataclass
class CompiledCollection:
    id: str
    name: str
    cycle: str
    theme: str
    publisher: Optional[str]
    aliases: List[str]
    path_patterns: List[re.Pattern]
    seq_regex: List[re.Pattern]


def _compile_regex_list(patterns: List[str]) -> List[re.Pattern]:
    compiled: List[re.Pattern] = []
    for p in patterns or []:
        try:
            compiled.append(re.compile(p))
        except re.error:
            # Skip invalid patterns to avoid hard failure
            continue
    return compiled


def load_designer_collections(designer_key: str) -> List[CompiledCollection]:
    if YAML is None:
        raise RuntimeError("ruamel.yaml is required. Please install requirements.txt")
    yaml = YAML(typ="rt")
    path = Path("vocab/collections") / f"{designer_key}.yaml"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = yaml.load(f) or {}
    out: List[CompiledCollection] = []
    for node in data.get("collections", []) or []:
        match = node.get("match", {}) or {}
        out.append(
            CompiledCollection(
                id=node.get("id", ""),
                name=node.get("name", ""),
                cycle=node.get("cycle", ""),
                theme=str(node.get("theme", "")),
                publisher=node.get("publisher"),
                aliases=[a for a in node.get("aliases", []) or [] if isinstance(a, str)],
                path_patterns=_compile_regex_list([p for p in match.get("path_patterns", []) or [] if isinstance(p, str)]),
                seq_regex=_compile_regex_list([p for p in match.get("sequence_number_regex", []) or [] if isinstance(p, str)]),
            )
        )
    return out


def _first_match(patterns: List[re.Pattern], text: str) -> Optional[re.Match]:
    for pat in patterns:
        m = pat.search(text)
        if m:
            return m
    return None


def _extract_sequence(seq_regex: List[re.Pattern], filename: str, folder: str) -> Optional[int]:
    for pat in seq_regex:
        for target in (filename, folder):
            if not target:
                continue
            m = pat.search(target)
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    continue
    return None


def _rel_text(v: Variant) -> Tuple[str, str]:
    # Build a text view to match against: near-leaf path and filename
    rel_path = v.rel_path or ""
    filename = v.filename or ""
    # last folder name
    parts = re.split(r"[\\/]+", rel_path)
    folder = parts[-1] if parts else ""
    return (rel_path, folder or filename)


def _alias_hit(aliases: List[str], text: str) -> Optional[str]:
    low = text.lower()
    for a in aliases:
        if not a:
            continue
        if a.lower() in low:
            return a
    return None


def _timestamped_out(path: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    root, ext = os.path.splitext(path)
    return f"{root}_{ts}{ext or '.json'}"


def mmf_refill_for_designer(designer: str, max_n: int = 5, apply: bool = False) -> Tuple[bool, str]:
    """Call the MMF updater script for a single designer to append new collections.

    Returns (ok, message)
    """
    script = str(Path("scripts/10_integrations/update_collections_from_mmf.py"))
    if not Path(script).exists():
        return False, "MMF updater script not found"

    cmd = [sys.executable, script, "--designer", designer, "--max", str(max_n)]
    if apply:
        cmd.append("--apply")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        ok = proc.returncode == 0
        msg = proc.stdout.strip() + ("\n" + proc.stderr.strip() if proc.stderr else "")
        return ok, msg
    except Exception as e:
        return False, f"Exception invoking updater: {e}"


def main():
    parser = argparse.ArgumentParser(description="Match variants to designer collections using YAML SSOT.")
    parser.add_argument("--db-url", dest="db_url", default=os.environ.get("STLMGR_DB_URL", "sqlite:///./data/stl_manager_v1.db"))
    parser.add_argument("--designer", action="append", help="Limit to one or more designer_keys.")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--apply", action="store_true", help="Write matches to DB (default: dry-run)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing collection_* fields")
    parser.add_argument("--mmf-refill-on-miss", action="store_true", help="Attempt MMF append when no YAML collection matches but phrase is strong")
    parser.add_argument("--out", default=os.path.join("reports", "match_collections.json"))
    args = parser.parse_args()

    engine = create_engine(args.db_url, future=True)
    out_path = _timestamped_out(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Lazy cache of compiled collections per designer
    compiled: Dict[str, List[CompiledCollection]] = {}

    report = {
        "summary": {"attempted": 0, "matched": 0, "skipped": 0, "refilled": 0, "errors": 0},
        "items": [],
    }

    with Session(engine) as session:
        conds = [Variant.designer.isnot(None)]
        if not args.overwrite:
            conds.append(Variant.collection_id.is_(None))
        if args.designer:
            conds.append(Variant.designer.in_(args.designer))
        q = select(Variant).where(and_(*conds)).limit(args.limit)
        variants: List[Variant] = list(session.execute(q).scalars())

        for v in variants:
            report["summary"]["attempted"] += 1
            designer = (v.designer or "").strip()
            if not designer:
                report["summary"]["skipped"] += 1
                report["items"].append({"variant_id": v.id, "reason": "no_designer"})
                continue

            if designer not in compiled:
                compiled[designer] = load_designer_collections(designer)

            rel_text, near_leaf = _rel_text(v)
            collections = compiled.get(designer, [])

            # Try deterministic path patterns
            chosen: Optional[CompiledCollection] = None
            label: Optional[str] = None
            seq_num: Optional[int] = None
            for c in collections:
                m = _first_match(c.path_patterns, rel_text)
                if m:
                    chosen = c
                    label = m.group(0)
                    seq_num = _extract_sequence(c.seq_regex, v.filename or "", near_leaf)
                    break

            # Fallback to aliases if no regex hit
            if not chosen:
                for c in collections:
                    hit = _alias_hit(c.aliases, near_leaf or rel_text)
                    if hit:
                        chosen = c
                        label = hit
                        seq_num = _extract_sequence(c.seq_regex, v.filename or "", near_leaf)
                        break

            # Optional MMF refill on miss
            refilled = False
            if not chosen and args.mmf_refill_on_miss:
                ok, msg = mmf_refill_for_designer(designer, apply=args.apply)
                report["items"].append({"variant_id": v.id, "designer": designer, "action": "mmf_refill", "ok": ok, "log": msg})
                if ok:
                    report["summary"]["refilled"] += 1
                    compiled[designer] = load_designer_collections(designer)
                    collections = compiled.get(designer, [])
                    for c in collections:
                        m = _first_match(c.path_patterns, rel_text)
                        if m:
                            chosen = c
                            label = m.group(0)
                            seq_num = _extract_sequence(c.seq_regex, v.filename or "", near_leaf)
                            break
                    if not chosen:
                        for c in collections:
                            hit = _alias_hit(c.aliases, near_leaf or rel_text)
                            if hit:
                                chosen = c
                                label = hit
                                seq_num = _extract_sequence(c.seq_regex, v.filename or "", near_leaf)
                                break

            if not chosen:
                report["summary"]["skipped"] += 1
                report["items"].append({
                    "variant_id": v.id,
                    "designer": designer,
                    "rel_path": v.rel_path,
                    "reason": "no_match",
                })
                continue

            # Apply or record
            item = {
                "variant_id": v.id,
                "designer": designer,
                "collection_id": chosen.id,
                "collection_name": chosen.name,
                "collection_cycle": chosen.cycle,
                "collection_theme": chosen.theme,
                "original_label": label,
                "seq": seq_num,
                "apply": args.apply,
            }

            if args.apply:
                try:
                    v.collection_id = chosen.id
                    v.collection_original_label = label
                    v.collection_cycle = chosen.cycle or None
                    v.collection_theme = chosen.theme or None
                    v.collection_sequence_number = seq_num
                    session.add(v)
                    report["summary"]["matched"] += 1
                    item["status"] = "updated"
                except Exception as e:
                    report["summary"]["errors"] += 1
                    item["status"] = "error"
                    item["error"] = str(e)
            else:
                report["summary"]["matched"] += 1
                item["status"] = "would_update"

            report["items"].append(item)

        if args.apply:
            session.commit()

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Wrote collections match report -> {out_path}")


if __name__ == "__main__":
    main()
