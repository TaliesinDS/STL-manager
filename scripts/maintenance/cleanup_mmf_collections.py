from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List

try:
    from ruamel.yaml import YAML
except Exception:
    YAML = None  # type: ignore


def load_username_map(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_mmf_username(u: str) -> str:
    # Normalize spaces/underscores/hyphens and case for comparison
    u = u.strip().strip("/")
    return u


def url_has_username(url: str, username: str) -> bool:
    # Accept both /users/<username>/collection/... and profile variations
    u = normalize_mmf_username(username)
    return re.search(rf"/users/{re.escape(u)}(/|$)", url, flags=re.IGNORECASE) is not None


def cleanup_file(yaml_path: Path, username: str) -> int:
    if YAML is None:
        raise RuntimeError("ruamel.yaml is required. Please install requirements.txt")
    yaml = YAML(typ="rt")
    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.load(f) or {}
    collections = data.get("collections", []) or []
    kept = []
    removed = 0
    for c in collections:
        urls = [u for u in c.get("source_urls", []) or [] if isinstance(u, str)]
        if not urls:
            # keep if no source_urls (curated/manual entry)
            kept.append(c)
            continue
        if any(url_has_username(u, username) for u in urls):
            kept.append(c)
        else:
            removed += 1
    if removed:
        data["collections"] = kept
        yaml = YAML()
        yaml.indent(mapping=2, sequence=2, offset=2)
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.dump(data, f)
    return removed


def main():
    root = Path("vocab/collections")
    map_path = Path("vocab/mmf_usernames.json")
    username_map = load_username_map(map_path)
    total_removed = 0
    for yaml_path in sorted(root.glob("*.yaml")):
        designer = yaml_path.stem
        username = username_map.get(designer)
        if not username:
            continue
        removed = cleanup_file(yaml_path, username)
        total_removed += removed
        if removed:
            print(f"Cleaned {yaml_path}: removed {removed} entries not under {username}")
    print(f"Total removed: {total_removed}")


if __name__ == "__main__":
    main()
from typing import Any

# repo root for locating vocab/collections dirs
_here = os.path.abspath(os.path.dirname(__file__))
_repo_root = os.path.abspath(os.path.join(_here, os.pardir, os.pardir))

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

COLLECTIONS_DIR = os.path.join(_repo_root, "vocab", "collections")
MMF_USERNAMES_PATH = os.path.join(_repo_root, "vocab", "mmf_usernames.json")

DEFAULT_USERNAME_MAP: Dict[str, str] = {
    "dm_stash": "DM-Stash",
    "heroes_infinite": "HeroesInfinite",
    "titan_forge": "TitanForgeMiniatures",
    "archvillain": "ArchvillainGames",
    "artisan_guild_miniatures": "ArtisanGuild",
    "bestiarum_miniatures": "BestiarumMiniatures",
    "caballero_miniatures": "CaballeroMiniatures",
    "cast_n_play": "CastnPlay",
    "comet_lord_miniatures": "CometLordMiniatures",
    "cyber_forge": "Cyber-Forge",
    "epic_minis": "EpicMiniatures",
    "ghamak": "Ghamak",
    "last_sword_miniatures": "LastSwordMiniatures",
    "loot_studios": "LootStudios",
    "lost_kingdom": "LostKingdomMiniatures",
    "one_page_rules": "onepagerules",
    "printable_scenery": "Printable-Scenery",
    "soul_forge_studio": "SoulForgeStudio",
    "txarli_factory": "TxarliFactory",
    "bam_broken_anvil_monthly": "BrokenAnvil",
}


def load_username_overrides() -> Dict[str, str]:
    if not os.path.exists(MMF_USERNAMES_PATH):
        return {}
    try:
        with open(MMF_USERNAMES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {str(k): str(v) for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}
    except Exception:
        return {}


def ensure_collections_list(doc: CommentedMap) -> List[Any]:
    colls = doc.get("collections")
    if colls is None:
        colls = []
        doc["collections"] = colls
    return colls


def prune_non_designer_entries(doc: CommentedMap, username: str) -> int:
    colls = doc.get("collections") or []
    if not isinstance(colls, list):
        return 0
    expected_prefix = f"https://www.myminifactory.com/users/{username}/collection/"
    keep = []
    removed = 0
    for it in colls:
        if not isinstance(it, dict):
            keep.append(it)
            continue
        srcs = it.get("source_urls") or []
        if not srcs:
            keep.append(it)
            continue
        if any(isinstance(u, str) and u.startswith(expected_prefix) for u in srcs):
            keep.append(it)
        else:
            removed += 1
    if removed:
        doc["collections"] = keep
    return removed


def main() -> int:
    overrides = load_username_overrides()
    yaml = YAML()
    yaml.preserve_quotes = True

    total_removed = 0
    files_changed = 0

    for name in sorted(os.listdir(COLLECTIONS_DIR)):
        if not name.endswith(".yaml"):
            continue
        key = os.path.splitext(name)[0]
        username = overrides.get(key) or DEFAULT_USERNAME_MAP.get(key)
        if not username:
            continue
        path = os.path.join(COLLECTIONS_DIR, name)
        try:
            with open(path, encoding="utf-8") as f:
                raw_txt = f.read()
        except Exception:
            continue
        normalized_txt = re.sub(r"(?m)^(\t+)", lambda m: "  " * len(m.group(1)), raw_txt)
        try:
            doc = yaml.load(normalized_txt) or CommentedMap()
        except Exception:
            continue
        removed = prune_non_designer_entries(doc, username)
        if removed:
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(doc, f)
            total_removed += removed
            files_changed += 1
            print(f"Cleaned {removed} item(s) from {path}")

    print(f"Summary: cleaned {total_removed} entries across {files_changed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
