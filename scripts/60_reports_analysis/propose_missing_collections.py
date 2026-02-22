from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

try:
    from ruamel.yaml import YAML
except Exception:
    YAML = None  # type: ignore

from db.models import Variant

GENERIC_SEGMENTS = {
    "supported",
    "presupported",
    "pre-supported",
    "support",
    "supports",
    "unsupported",
    "bases",
    "base",
    "files",
    "stl",
    "stls",
    "obj",
    "images",
    "preview",
    "previews",
    "renders",
    "heroes",
    "miniatures",
    "models",
}


def snake_case(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.lower()


def titleize(text: str) -> str:
    # Normalize underscores/dashes to spaces, collapse whitespace, title-case
    t = re.sub(r"[_-]+", " ", text)
    t = re.sub(r"\s+", " ", t).strip()
    # Preserve ALLCAPS words like MMF or acronyms by title-casing but keeping >3 letter all-caps intact
    parts = t.split(" ")
    out: List[str] = []
    for p in parts:
        if len(p) > 3 and p.isupper():
            out.append(p)
        else:
            out.append(p.capitalize())
    return " ".join(out)


def segment_score(seg: str) -> float:
    # Score by length, word count, presence of stop words like 'of','the', and capitalization pattern
    raw = seg.strip(r" \/")
    if not raw:
        return 0.0
    norm = re.sub(r"[_-]+", " ", raw)
    words = [w for w in re.split(r"\s+", norm) if w]
    lw = [w.lower() for w in words]
    if any(w in GENERIC_SEGMENTS for w in lw):
        return 0.0
    score = 0.0
    score += min(len(norm) / 20.0, 3.0)  # length bonus up to 3
    score += min(len(words) / 2.0, 3.0)  # word count bonus up to 3
    if any(w in {"of", "the", "and", "in", "on"} for w in lw):
        score += 0.5
    letters = re.sub(r"[^A-Za-z]", "", norm)
    if letters:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio > 0.6:
            score += 0.5
    return score


def extract_collection_phrase(rel_path: str, max_segments: int = 5) -> Optional[str]:
    # Consider both top-level and near-leaf segments to accommodate different folder layouts
    parts = re.split(r"[\\/]+", rel_path)
    candidates: List[Tuple[float, str]] = []

    # Top N segments from root and from leaf
    head = parts[:max_segments]
    tail = parts[-max_segments:]

    for seg in head + tail:
        s = seg.strip()
        if not s:
            continue
        sc = segment_score(s)
        if sc > 0.75:
            candidates.append((sc, s))

    if not candidates:
        return None
    # Pick the highest score
    best = max(candidates, key=lambda x: x[0])[1]
    # Clean & titleize
    # Remove trailing generic suffixes in parentheses, etc.
    best = re.sub(r"\([^)]*\)$", "", best).strip()
    return titleize(best)


@dataclass
class ProposedCollection:
    designer_key: str
    name: str
    theme: str
    cycle: str  # empty if unknown
    publisher: str
    source_urls: List[str]
    aliases: List[str]
    match_path_patterns: List[str]

    def to_yaml_node(self, with_id: bool = True) -> Dict:
        node = {
            "name": self.name,
            "cycle": self.cycle,
            "theme": self.theme,
            "publisher": self.publisher,
            "source_urls": self.source_urls,
            "aliases": self.aliases,
            "match": {
                "path_patterns": self.match_path_patterns,
                "sequence_number_regex": [
                    r"^(\\d{1,2})[._ -]",
                    r"[ _-](\\d{1,2})[ _-]",
                ],
            },
        }
        if with_id:
            node["id"] = f"{self.designer_key}__{snake_case(self.cycle + '_' if self.cycle else '')}{self.theme}"
        return node


def load_designer_yaml(path: Path) -> Dict:
    if YAML is None:
        raise RuntimeError("ruamel.yaml is required. Please install requirements.txt")
    yaml = YAML(typ="rt")
    if not path.exists():
        return {
            "version": 1,
            "publisher": "myminifactory",
            "designer_key": path.stem,
            "collections": [],
        }
    with path.open("r", encoding="utf-8") as f:
        return yaml.load(f) or {}


def save_designer_yaml(path: Path, data: Dict) -> None:
    if YAML is None:
        raise RuntimeError("ruamel.yaml is required. Please install requirements.txt")
    yaml = YAML()
    yaml.indent(mapping=2, sequence=2, offset=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f)


def main():
    parser = argparse.ArgumentParser(description="Propose missing collection entries from variant path tokens.")
    parser.add_argument("--db-url", dest="db_url", default=os.environ.get("STLMGR_DB_URL", "sqlite:///./data/stl_manager_v1.db"))
    parser.add_argument("--designer", action="append", help="Limit to one or more designer_keys.")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--out", default=os.path.join("reports", "propose_missing_collections.json"))
    parser.add_argument("--apply-draft", action="store_true", help="Write draft YAML entries under vocab/collections/_drafts/<designer>.pending.yaml")
    args = parser.parse_args()

    engine = create_engine(args.db_url, future=True)
    report: List[Dict] = []

    with Session(engine) as session:
        q = select(Variant).where(Variant.designer.isnot(None), Variant.collection_id.is_(None))
        if args.designer:
            q = q.where(Variant.designer.in_(args.designer))
        q = q.limit(args.limit)
        variants: List[Variant] = list(session.execute(q).scalars())

    # Group by designer
    by_designer: Dict[str, List[Variant]] = {}
    for v in variants:
        if not v.designer:
            continue
        by_designer.setdefault(v.designer, []).append(v)

    drafts_root = Path("vocab/collections/_drafts")
    for designer, items in by_designer.items():
        # Load existing YAML to de-dupe by name
        yaml_path = Path("vocab/collections") / f"{designer}.yaml"
        try:
            data = load_designer_yaml(yaml_path)
            existing_names = {c.get("name", "").strip().lower() for c in data.get("collections", [])}
        except Exception:
            data = {"collections": []}
            existing_names = set()

        proposed_nodes: Dict[str, Dict] = {}
        for v in items:
            phrase = extract_collection_phrase(v.rel_path)
            if not phrase:
                continue
            key = phrase.strip().lower()
            if key in existing_names:
                continue
            if key in proposed_nodes:
                continue
            theme = snake_case(phrase)
            pattern = rf"(?i){re.sub(r'\s+', '[-_ ]', re.escape(phrase))}"
            proposal = ProposedCollection(
                designer_key=designer,
                name=phrase,
                theme=theme,
                cycle="",
                publisher=data.get("publisher", "myminifactory"),
                source_urls=[],
                aliases=[phrase],
                match_path_patterns=[pattern],
            )
            node = proposal.to_yaml_node(with_id=True)
            proposed_nodes[key] = node
            report.append(
                {
                    "designer": designer,
                    "variant_id": v.id,
                    "rel_path": v.rel_path,
                    "proposed": node,
                    "status": "needs_source_url",
                }
            )

        if args.apply_draft and proposed_nodes:
            draft_path = drafts_root / f"{designer}.pending.yaml"
            draft_data = load_designer_yaml(draft_path) if draft_path.exists() else {
                "version": 1,
                "publisher": data.get("publisher", "myminifactory"),
                "designer_key": designer,
                "collections": [],
            }
            # Append proposals not already present by name
            existing_draft_names = {c.get("name", "").strip().lower() for c in draft_data.get("collections", [])}
            for name_key, node in proposed_nodes.items():
                if name_key not in existing_draft_names:
                    draft_data["collections"].append(node)
            save_designer_yaml(draft_path, draft_data)

    # Write report
    Path(os.path.dirname(args.out)).mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Wrote report with {len(report)} proposals -> {args.out}")
    if args.apply_draft:
        print(f"Draft YAML written under {drafts_root}\n(Review and move curated entries into vocab/collections/<designer>.yaml)")


if __name__ == "__main__":
    main()
