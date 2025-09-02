import os
import re
import sys
import json
from typing import Dict, List, Any

# path shim
_here = os.path.abspath(os.path.dirname(__file__))
_repo_root = os.path.abspath(os.path.join(_here, os.pardir, os.pardir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

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
        with open(MMF_USERNAMES_PATH, "r", encoding="utf-8") as f:
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
            with open(path, "r", encoding="utf-8") as f:
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
