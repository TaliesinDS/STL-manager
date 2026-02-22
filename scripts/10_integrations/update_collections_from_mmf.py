import argparse
import json
import os
import re
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional

# repo root for locating vocab/collections and reports
_here = os.path.abspath(os.path.dirname(__file__))
_repo_root = os.path.abspath(os.path.join(_here, os.pardir, os.pardir))

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from scripts.lib.mmf_client import (
    MMFError,
    get_access_token,
    paginate_user_collections,
    scrape_user_collections,
)

COLLECTIONS_DIR = os.path.join(_repo_root, "vocab", "collections")
MMF_USERNAMES_PATH = os.path.join(_repo_root, "vocab", "mmf_usernames.json")

# Map designer_key -> MMF username
DEFAULT_USERNAME_MAP: Dict[str, str] = {
    # fill the ones we know or can infer
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
    except Exception as e:
        print(f"Warn: failed to load {MMF_USERNAMES_PATH}: {e}")
        return {}


def find_designer_keys() -> List[str]:
    keys: List[str] = []
    for name in os.listdir(COLLECTIONS_DIR):
        if not name.endswith(".yaml"):
            continue
        key = os.path.splitext(name)[0]
        keys.append(key)
    return sorted(keys)


def detect_username_from_yaml(designer_key: str) -> Optional[str]:
    """Extract the most common MMF username from source_urls in the designer YAML.
    Returns None if no MMF user URL is found.
    """
    yaml_path = os.path.join(COLLECTIONS_DIR, f"{designer_key}.yaml")
    if not os.path.exists(yaml_path):
        return None
    try:
        with open(yaml_path, encoding="utf-8") as f:
            txt = f.read()
    except Exception:
        return None
    # Find users/<username>/collection/ occurrences
    usernames = re.findall(r"https?://www\.myminifactory\.com/users/([^/]+)/collection/", txt, flags=re.IGNORECASE)
    if not usernames:
        return None
    from collections import Counter
    normalized = [u.strip() for u in usernames if u.strip()]
    if not normalized:
        return None
    # Blacklist generic or known non-designer accounts that often appear in examples
    blacklist = {"romain", "Scan The World", "Scan%20The%20World"}
    counts = Counter(normalized)
    for cand, freq in counts.most_common():
        if cand in blacklist:
            continue
        if freq < 2:
            # require at least 2 occurrences to reduce chance of stray links
            continue
        return cand
    return None


def choose_items(items: List[Dict[str, Any]], count: int = 5) -> List[Dict[str, Any]]:
    # The API returns newest-first typically; HTML scrape order may vary; just take first N.
    return items[:count]


def dump_report(designer_key: str, username: str, items: List[Dict[str, Any]]) -> str:
    os.makedirs(os.path.join(_repo_root, "reports"), exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(_repo_root, "reports", f"mmf_latest_{designer_key}_{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"designer_key": designer_key, "username": username, "count": len(items), "items": items}, f, ensure_ascii=False, indent=2)
    return path


_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def try_parse_cycle(text: str) -> Optional[str]:
    t = text.strip()
    # Patterns like: March 2025, Mar 2025
    m = re.search(r"(?i)\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\s+(\d{4})", t)
    if m:
        mon = _MONTHS[m.group(1).lower()]
        year = int(m.group(2))
        return f"{year:04d}-{mon:02d}"
    # Patterns like: 2025-03 or 2025/03 or 2025_03
    m = re.search(r"\b(\d{4})[\-_/](\d{1,2})\b", t)
    if m:
        year = int(m.group(1))
        mon = int(m.group(2))
        if 1 <= mon <= 12:
            return f"{year:04d}-{mon:02d}"
    return None


def slugify_theme(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9_\- ]+", "", s)
    s = s.replace("-", "_")
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_") or "untitled"


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
            keep.append(it)  # if no sources, we don’t delete automatically
            continue
        # If any source URL matches the designer path, keep; else drop
        if any(isinstance(u, str) and u.startswith(expected_prefix) for u in srcs):
            keep.append(it)
        else:
            removed += 1
    if removed:
        doc["collections"] = keep
    return removed


def entry_exists(colls: List[Any], url: str, name: str) -> bool:
    for it in colls:
        if not isinstance(it, dict):
            continue
        if it.get("name") == name:
            return True
        srcs = it.get("source_urls") or []
        if isinstance(srcs, list) and any(url == u for u in srcs):
            return True
    return False


def make_entry(designer_key: str, name: str, url: str, slug: str) -> Dict[str, Any]:
    cycle = try_parse_cycle(name) or ""
    theme = slugify_theme(slug)
    id_parts = [designer_key]
    if cycle:
        id_parts.append(cycle.replace("-", "_"))
    id_parts.append(theme)
    entry_id = "__".join([id_parts[0], "_".join(id_parts[1:])]) if len(id_parts) > 1 else f"{designer_key}__{theme}"
    return {
        "id": entry_id,
        "name": name,
        "cycle": cycle,
        "theme": theme,
        "publisher": "myminifactory",
        "source_urls": [url],
        "aliases": [name],
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Update vocab/collections/* from MyMiniFactory with latest 5 collections")
    p.add_argument("--designer", action="append", help="Limit to specific designer_key(s); can be used multiple times")
    p.add_argument("--max", type=int, default=5, help="How many latest collections to select (default 5)")
    p.add_argument("--prefer-api", dest="prefer_api", action="store_true", help="Prefer API over scrape (requires auth)")
    p.add_argument("--apply", action="store_true", help="Apply YAML updates; otherwise only write JSON reports")
    args = p.parse_args()

    keys = args.designer or find_designer_keys()
    overrides = load_username_overrides()

    client_id = os.environ.get("MMF_CLIENT_ID") or os.environ.get("MMF_CLIENT_KEY")
    client_secret = os.environ.get("MMF_CLIENT_SECRET")
    api_key = os.environ.get("MMF_API_KEY")

    access_token = None
    if args.prefer_api and client_id and client_secret:
        try:
            access_token = get_access_token(client_id, client_secret)
        except MMFError as e:
            print(f"Warn: OAuth token fetch failed ({e}); falling back to scrape.")

    for key in keys:
        username = overrides.get(key) or DEFAULT_USERNAME_MAP.get(key)
        if not username:
            print(f"Skip {key}: no known MMF username mapping yet")
            continue

        items: List[Dict[str, Any]] = []
        tried_usernames: List[str] = []

        def fetch_for(u: str) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            # Use the user-specific endpoint when possible
            if access_token or api_key:
                try:
                    api_items = paginate_user_collections(u, access_token=access_token, api_key=api_key, per_page=50, max_pages=1)
                    norm: List[Dict[str, Any]] = []
                    expected_prefix = f"https://www.myminifactory.com/users/{urllib.parse.quote(u)}/collection/"
                    for obj in api_items:
                        name = obj.get("name") or obj.get("title") or ""
                        slug = obj.get("slug") or obj.get("id") or ""
                        url = obj.get("url") or (f"https://www.myminifactory.com/users/{u}/collection/{slug}" if slug else "")
                        if url.startswith(expected_prefix):
                            norm.append({"name": name, "slug": slug, "url": url})
                    out = norm
                except MMFError:
                    pass
            if not out:
                try:
                    out = scrape_user_collections(u, limit=50)
                except MMFError:
                    out = []
            return out

        items = fetch_for(username)
        tried_usernames.append(username)
        if not items:
            yaml_username = detect_username_from_yaml(key)
            if yaml_username and yaml_username not in tried_usernames:
                print(f"Info: mapped username failed; trying YAML-detected username for {key}: {yaml_username}")
                items = fetch_for(yaml_username)
                if items:
                    username = yaml_username
        if not items:
            print(f"Error: no collections found for {key} using usernames {tried_usernames} and YAML fallback.")
            continue

        chosen = choose_items(items, count=args.max)
        report = dump_report(key, username, chosen)
        print(f"Wrote report for {key} -> {report}")

        if not args.apply:
            continue

        # Apply: parse YAML and append structured entries if missing; also prune obviously unrelated MMF entries
        yaml_path = os.path.join(COLLECTIONS_DIR, f"{key}.yaml")
        if not os.path.exists(yaml_path):
            print(f"Skip apply for {key}: missing {yaml_path}")
            continue

        yaml = YAML()
        yaml.preserve_quotes = True
        with open(yaml_path, encoding="utf-8") as f:
            raw_txt = f.read()
        # Normalize leading tabs to two spaces to accommodate files using tab indentation
        normalized_txt = re.sub(r"(?m)^(\t+)", lambda m: "  " * len(m.group(1)), raw_txt)
        try:
            doc = yaml.load(normalized_txt) or CommentedMap()
        except Exception as e:
            print(f"Error parsing YAML for {key} ({yaml_path}): {e}")
            continue
        # Prune unrelated entries if they point to different MMF users
        removed = 0
        if username:
            removed = prune_non_designer_entries(doc, username)
            if removed:
                print(f"Pruned {removed} non-designer MMF collection(s) from {yaml_path}")
        colls = ensure_collections_list(doc)
        added = 0
        for it in chosen:
            name = it.get("name") or "Unnamed Collection"
            url = it.get("url") or ""
            slug = it.get("slug") or name.lower().replace(" ", "-")
            if not url:
                continue
            if entry_exists(colls, url, name):
                continue
            entry = make_entry(key, name, url, slug)
            colls.append(entry)
            added += 1
        if added:
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(doc, f)
            print(f"Updated {yaml_path}: appended {added} collection(s)")
        else:
            print(f"No new entries to append for {key}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
