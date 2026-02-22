from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.exc import OperationalError

# __file__ is .../scripts/30_normalize_match/match_variants_to_units.py
# parents[2] -> repo root
ROOT = Path(__file__).resolve().parents[2]

from db.models import (  # type: ignore
    Faction,
    GameSystem,
    Unit,
    Variant,
    VariantUnitLink,
)
from db.session import get_session  # type: ignore
from scripts.lib.alias_rules import AMBIGUOUS_ALIASES  # type: ignore

WORD_SEP_RE = re.compile(r"[\W_]+", re.UNICODE)
# Default scale per system as 1:denominator (e.g., 1:56 ~ 28-32mm heroic)
SYSTEM_DEFAULT_SCALE_DEN: Dict[str, int] = {"w40k": 56, "aos": 56, "heresy": 56, "old_world": 56}
SYSTEM_DEFAULT_SCALE_NAME: Dict[str, str] = {"w40k": "28mm heroic", "aos": "28mm heroic", "heresy": "28mm heroic", "old_world": "28mm heroic"}
# Ambiguous/generic aliases that are too weak to accept on their own
# Reuse the central list used by normalization/character matching for consistency
GENERIC_ROLE_ALIASES: Set[str] = set(AMBIGUOUS_ALIASES)

# Default tabletop scale by system (denominator of 1:scale). Conservative defaults for GW systems.
DEFAULT_SCALE_BY_SYSTEM: Dict[str, int] = {
    "w40k": 56,     # ~28mm heroic
    "heresy": 56,   # same physical scale as 40k
    "aos": 56,      # Age of Sigmar ~28-32mm heroic, keep single denom
    # "old_world": 56,  # uncomment if Old World is ingested as a system key
}


def norm_text(s: str) -> str:
    s = s.lower()
    s = s.replace("warhammer 40,000", "w40k").replace("warhammer 40k", "w40k")
    s = s.replace("age of sigmar", "aos").replace("horus heresy", "heresy").replace("30k", "heresy")
    # collapse non-word
    s = WORD_SEP_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def system_hint(text: str) -> Optional[str]:
    t = text.lower()
    if any(k in t for k in ["w40k", "40k", "wh40k", "warhammer 40"]):
        return "w40k"
    # Direct AoS keywords
    if any(k in t for k in ["aos", "age of sigmar", "sigmar", "freeguild"]):
        return "aos"
    # Heuristic: presence of known AoS faction tokens implies AoS system
    AOS_FACTION_TOKENS = [
        "flesh eater courts", "soulblight gravelords", "nighthaunt", "stormcast eternals",
        "seraphon", "kharadron overlords", "gloomspite gitz", "orruk warclans",
        "ogor mawtribes", "sylvaneth", "cities of sigmar", "skaven", "slaves to darkness",
        "blades of khorne", "disciples of tzeentch", "maggotkin of nurgle", "hedonites of slaanesh",
        "beasts of chaos", "sons of behemat", "fyreslayers", "lumineth realm lords",
        "daughters of khaine", "idoneth deepkin", "ossiarch bonereapers",
    ]
    if any(re.search(rf"\b{re.escape(tok)}\b", t) for tok in AOS_FACTION_TOKENS):
        return "aos"
    if any(k in t for k in ["heresy", "30k", "horus heresy"]):
        return "heresy"
    return None


# Lightweight chapter/sub-faction cues for Space Marines folders
# Keyed by normalized text (use with norm_text input)
CHAPTER_HINTS = {
    "blood angels": "blood_angels",
    "dark angels": "dark_angels",
    "space wolves": "space_wolves",
    "black templars": "black_templars",
    "imperial fists": "imperial_fists",
    "ultramarines": "ultramarines",
    "salamanders": "salamanders",
    "raven guard": "raven_guard",
    "iron hands": "iron_hands",
    "white scars": "white_scars",
    "deathwatch": "deathwatch",
    "crimson fists": "crimson_fists",
}

# Commonly used sub-factions (map to parent chapter + subfaction key)
SUBFACTION_HINTS: Dict[str, Tuple[str, str]] = {
    "ravenwing": ("dark_angels", "ravenwing"),
    "deathwing": ("dark_angels", "deathwing"),
    "flesh tearers": ("blood_angels", "flesh_tearers"),
}

# Abbreviations often appearing in file/folder names
# For short 2–3 letter abbreviations, we'll require a Space Marine context to reduce false positives
ABBREV_HINTS: Dict[str, Tuple[str, Optional[str]]] = {
    # Chapters
    "ba": ("blood_angels", None),
    "da": ("dark_angels", None),
    "sw": ("space_wolves", None),
    "bt": ("black_templars", None),
    "if": ("imperial_fists", None),
    "um": ("ultramarines", None),
    "rg": ("raven_guard", None),
    "ih": ("iron_hands", None),
    "ws": ("white_scars", None),
    "cf": ("crimson_fists", None),
    # Subfactions
    "rw": ("dark_angels", "ravenwing"),
    # Note: 'dw' is ambiguous (Deathwing vs Deathwatch). We'll only treat 'dw' as Deathwing
    # when 'terminator' context is present; otherwise ignore.
    "dw": ("dark_angels", "deathwing"),
    "ft": ("blood_angels", "flesh_tearers"),
}

MARINE_CONTEXT_TOKENS = [
    "space marine", "adeptus astartes", "terminator", "assault terminator", "terminator assault",
    "intercessor", "assault squad", "tactical", "gravis", "bladeguard", "inceptor",
    "hellblaster", "devastator", "sternguard", "vanguard veteran", "captain", "librarian",
    "apothecary", "chaplain", "death company", "sanguinary guard"
]


def _has_marine_context(v_text_norm: str) -> bool:
    for tok in MARINE_CONTEXT_TOKENS:
        if re.search(rf"\b{re.escape(tok)}\b", v_text_norm):
            return True
    return False


def find_chapter_hint(v_text_norm: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (chapter_key, subfaction_key) hints from normalized text.

    - Prefer explicit long-form chapter phrases.
    - Then subfaction phrases (yield both chapter and subfaction keys).
    - Then abbreviations if Space Marine context is present. For 'dw', require a clear
      Terminator context to prefer Deathwing over Deathwatch.
    """
    # Long-form chapters
    for phrase, chap in CHAPTER_HINTS.items():
        if re.search(rf"\b{re.escape(phrase)}\b", v_text_norm):
            return chap, None

    # Subfactions
    for phrase, (chap, subf) in SUBFACTION_HINTS.items():
        if re.search(rf"\b{re.escape(phrase)}\b", v_text_norm):
            return chap, subf

    # Abbreviations (guarded)
    marine_ctx = _has_marine_context(v_text_norm)
    if marine_ctx:
        # Special-case 'dw' to require terminator in text for Deathwing
        if re.search(r"\bdw\b", v_text_norm) and re.search(r"\bterminator\b", v_text_norm):
            return "dark_angels", "deathwing"
        for abbr, (chap, subf) in ABBREV_HINTS.items():
            if abbr == "dw":
                continue  # handled above
            if re.search(rf"\b{re.escape(abbr)}\b", v_text_norm):
                return chap, subf

    return None, None


@dataclass
class UnitRef:
    unit_id: int
    system_key: str
    unit_key: str
    unit_name: str
    faction_key: Optional[str]
    category: Optional[str] = None  # e.g., 'unit', 'endless_spell', 'manifestation', 'invocation', 'terrain'


def build_unit_alias_index(session) -> Tuple[
    Dict[str, List[UnitRef]],
    Dict[str, UnitRef],
    Dict[str, List[UnitRef]],
    Dict[str, List[UnitRef]],
]:
    # Return:
    # - idx: maps normalized alias phrase -> list of UnitRef
    # - key_index: unit_key -> UnitRef
    # - mount_children: base_key -> list of mounted UnitRefs (keys that start with f"{base_key}_on_")
    # - spells_by_faction: faction_key -> list of UnitRefs whose category is a spell-like category
    sys_map = {row.id: row.key for row in session.execute(select(GameSystem)).scalars()}
    fac_map = {row.id: row.key for row in session.execute(select(Faction)).scalars()}

    idx: Dict[str, List[UnitRef]] = defaultdict(list)
    key_index: Dict[str, UnitRef] = {}
    mount_children: Dict[str, List[UnitRef]] = defaultdict(list)
    spells_by_faction: Dict[str, List[UnitRef]] = defaultdict(list)
    # Select only the columns we need to avoid touching fields that may not exist in older DBs
    try:
        unit_rows = session.execute(
            select(Unit.id, Unit.system_id, Unit.faction_id, Unit.key, Unit.name, Unit.aliases, Unit.category)
        ).all()
        have_category = True
    except OperationalError:
        # Older DB without 'category' column
        unit_rows = session.execute(
            select(Unit.id, Unit.system_id, Unit.faction_id, Unit.key, Unit.name, Unit.aliases)
        ).all()
        have_category = False
    for u in unit_rows:
        u_id = u.id
        u_system_id = u.system_id
        u_faction_id = u.faction_id
        u_key = u.key
        u_name = u.name
        u_aliases = u.aliases
        u_category = (u.category if have_category else None)
        phrases: List[str] = []
        # primary name & key forms
        if u_name:
            phrases.append(u_name)
        if u_key:
            phrases.append(u_key.replace("_", " "))
        # include provided aliases
        try:
            for a in (u_aliases or []):
                if isinstance(a, str):
                    phrases.append(a)
        except Exception:
            pass

        unique_phrases = sorted({norm_text(p) for p in phrases if isinstance(p, str) and len(p) >= 3})
        ref = UnitRef(
            unit_id=u_id,
            system_key=sys_map.get(u_system_id, ""),
            unit_key=u_key,
            unit_name=u_name,
            faction_key=fac_map.get(u_faction_id) if u_faction_id else None,
            category=u_category,
        )
        if u_key:
            key_index[u_key] = ref
            # Build mounted children index: keys following pattern '<base>_on_*'
            if "_on_" in u_key:
                base = u_key.split("_on_", 1)[0]
                mount_children[base].append(ref)
        # Spells by faction (endless_spell/manifestation/invocation)
        if ref.category in {"endless_spell", "manifestation", "invocation"} and ref.faction_key:
            spells_by_faction[ref.faction_key].append(ref)
        for p in unique_phrases:
            if not p or len(p) < 3:
                continue
            idx[p].append(ref)
    return idx, key_index, mount_children, spells_by_faction


def detect_mount_context(v_text_norm: str) -> Tuple[bool, Optional[str]]:
    """Detects mount context and mount type.
    Returns (is_mount_context, mount_type) where mount_type in {'terror', 'dragon', 'bat', None}.
    Heuristics:
      - Look for 'mount' or explicit ' on ' combined with mount animal tokens.
      - 'terror'/'terrorgeist' => 'terror'; 'bat' => 'bat'; 'dragon/draggon' => 'dragon'.
    """
    t = v_text_norm
    has_mount_word = re.search(r"\bmount(ed)?\b", t) is not None
    has_on = re.search(r"\bon\b", t) is not None
    terror = re.search(r"\bterror(g|gh)eist(s)?\b", t) is not None
    bat = re.search(r"\bbat(s)?\b", t) is not None
    dragon = re.search(r"\b(zombie\s+)?dra(g|gg)on(s)?\b", t) is not None
    any_mount = has_mount_word or has_on
    if any_mount:
        if terror or bat:
            return True, 'terror'
        if dragon:
            return True, 'dragon'
        return True, None
    return False, None


def apply_mount_bias(results: List[Tuple[UnitRef, float, str]], v_text_norm: str) -> List[Tuple[UnitRef, float, str]]:
    """Bias scores toward mounted variants when mount context is detected.
    Boost units whose unit_key contains '_on_...' and relevant mount animal.
    Slightly penalize base (unmounted) when mount context present.
    """
    is_mount, mtype = detect_mount_context(v_text_norm)
    if not is_mount:
        return results
    adj: List[Tuple[UnitRef, float, str]] = []
    for ref, score, via in results:
        key = ref.unit_key or ""
        delta = 0.0
        if "_on_" in key:
            if mtype == 'terror' and ('terrorgeist' in key or 'terrorgheist' in key):
                delta += 4.0
            elif mtype == 'dragon' and ('zombie_dragon' in key or 'dragon' in key):
                delta += 3.5
            else:
                delta += 1.5
        else:
            delta -= 1.0
        adj.append((ref, score + delta, via))
    # Resort with bias applied
    adj.sort(key=lambda x: x[1], reverse=True)
    return adj


def inject_mounted_candidates(results: List[Tuple[UnitRef, float, str]], mount_children: Dict[str, List[UnitRef]], v_text_norm: str) -> List[Tuple[UnitRef, float, str]]:
    """If a base unit is in results and mount context exists, inject its mounted children as additional candidates.
    Avoid duplicates (by unit_id). Provide a reasonable base score and 'via' marker.
    """
    is_mount, _ = detect_mount_context(v_text_norm)
    if not is_mount or not results:
        return results
    existing_ids: Set[int] = {r[0].unit_id for r in results}
    out = list(results)
    for ref, score, via in results[:5]:  # consider top few only
        key = ref.unit_key or ""
        if "_on_" in key:
            continue  # already mounted
        base = key
        children = mount_children.get(base) or []
        for ch in children:
            if ch.unit_id in existing_ids:
                continue
            # Seed candidate with slight advantage over base to allow bias to take over
            out.append((ch, max(0.0, score - 0.5), 'mount_hint'))
            existing_ids.add(ch.unit_id)
    return out


# -----------------
# Spells heuristics
# -----------------

AOS_FACTION_TOKENS_MAP: Dict[str, str] = {
    # map phrase -> faction_key
    "flesh eater courts": "flesh_eater_courts",
    "soulblight gravelords": "soulblight_gravelords",
    "nighthaunt": "nighthaunt",
    "stormcast eternals": "stormcast_eternals",
    "seraphon": "seraphon",
    "kharadron overlords": "kharadron_overlords",
    "gloomspite gitz": "gloomspite_gitz",
    "orruk warclans": "orruk_warclans",
    "ogor mawtribes": "ogor_mawtribes",
    "sylvaneth": "sylvaneth",
    "cities of sigmar": "cities_of_sigmar",
    "skaven": "skaven",
    "slaves to darkness": "slaves_to_darkness",
    "blades of khorne": "blades_of_khorne",
    "disciples of tzeentch": "disciples_of_tzeentch",
    "maggotkin of nurgle": "maggotkin_of_nurgle",
    "hedonites of slaanesh": "hedonites_of_slaanesh",
    "beasts of chaos": "beasts_of_chaos",
    "sons of behemat": "sons_of_behemat",
    "fyreslayers": "fyreslayers",
    "lumineth realm lords": "lumineth_realm_lords",
    "daughters of khaine": "daughters_of_khaine",
    "idoneth deepkin": "idoneth_deepkin",
    "ossiarch bonereapers": "ossiarch_bonereapers",
}

# AoS: map leaf faction keys to their Grand Alliance for fallback/path expansion
AOS_LEAF_TO_GRAND: Dict[str, str] = {
    # Order
    "stormcast_eternals": "order",
    "cities_of_sigmar": "order",
    "fyreslayers": "order",
    "kharadron_overlords": "order",
    "lumineth_realm_lords": "order",
    "idoneth_deepkin": "order",
    "daughters_of_khaine": "order",
    "seraphon": "order",
    "sylvaneth": "order",
    # Chaos
    "slaves_to_darkness": "chaos",
    "blades_of_khorne": "chaos",
    "disciples_of_tzeentch": "chaos",
    "maggotkin_of_nurgle": "chaos",
    "hedonites_of_slaanesh": "chaos",
    "beasts_of_chaos": "chaos",
    "skaven": "chaos",
    # Death
    "flesh_eater_courts": "death",
    "soulblight_gravelords": "death",
    "nighthaunt": "death",
    "ossiarch_bonereapers": "death",
    # Destruction
    "gloomspite_gitz": "destruction",
    "orruk_warclans": "destruction",
    "ogor_mawtribes": "destruction",
    "sons_of_behemat": "destruction",
}


def detect_spell_context(v_text_norm: str) -> bool:
    return bool(re.search(r"\b(spell|spells|endless spell|endless spells|manifestation|invocation)s?\b", v_text_norm))


def detect_aos_faction_hint(v_text_norm: str) -> Optional[str]:
    for phrase, fkey in AOS_FACTION_TOKENS_MAP.items():
        if re.search(rf"\b{re.escape(phrase)}\b", v_text_norm):
            return fkey
    return None


def inject_spell_candidates(
    results: List[Tuple[UnitRef, float, str]],
    spells_by_faction: Dict[str, List[UnitRef]],
    v_text_norm: str,
) -> List[Tuple[UnitRef, float, str]]:
    if not detect_spell_context(v_text_norm):
        return results
    fkey = detect_aos_faction_hint(v_text_norm)
    if not fkey:
        return results
    existing_ids: Set[int] = {r[0].unit_id for r in results}
    out = list(results)
    for ref in spells_by_faction.get(fkey, [])[:10]:
        if ref.unit_id in existing_ids:
            continue
        # Seed with a low score so this never auto-accepts without explicit text cues
        out.append((ref, 5.5, 'spell_context'))
        existing_ids.add(ref.unit_id)
    return out


def apply_spell_bias(results: List[Tuple[UnitRef, float, str]], v_text_norm: str) -> List[Tuple[UnitRef, float, str]]:
    if not detect_spell_context(v_text_norm):
        return results
    adj: List[Tuple[UnitRef, float, str]] = []
    for ref, score, via in results:
        delta = 0.0
        if (ref.category or "") in {"endless_spell", "manifestation", "invocation"}:
            delta += 2.0
        else:
            delta -= 0.5
        adj.append((ref, score + delta, via))
    adj.sort(key=lambda x: x[1], reverse=True)
    return adj


def text_for_variant(v: Variant) -> str:
    parts: List[str] = []
    if v.rel_path:
        parts.append(v.rel_path)
    if v.filename:
        parts.append(v.filename)
    # Prefer english_tokens when present
    try:
        eng = getattr(v, 'english_tokens', None) or []
        if isinstance(eng, list) and eng:
            parts.append(" ".join([str(t) for t in eng if isinstance(t, str)]))
    except Exception:
        pass
    # include any recorded raw tokens
    try:
        for t in (v.raw_path_tokens or []):
            if isinstance(t, str):
                parts.append(t)
    except Exception:
        pass
    # If this looks like a spells folder, include a few child filenames to aid matching (e.g., 'undead skeleton horse')
    try:
        rel_norm = norm_text(v.rel_path or "")
        if re.search(r"\b(spell|spells|endless|manifestation|invocation)s?\b", rel_norm):
            for f in (v.files or [])[:5]:  # only a few to limit noise
                parts.append(getattr(f, 'filename', '') or '')
    except Exception:
        pass
    return norm_text(" ".join(parts))

def _path_segments(rel_path: Optional[str]) -> List[str]:
    """Return normalized path segments from a rel_path, filtering noise tokens.

    Example: "Freeguild Cavaliers\\5. Calix\\CalixAlternativeDeers" ->
      ["freeguild cavaliers", "5 calix", "calixalternativedeers"]
    """
    if not rel_path:
        return []
    raw = re.split(r"[\\/]+", rel_path)
    segs: List[str] = []
    NOISE = {
        "stl", "supported stl", "unsupported", "presupported", "__macosx",
        "combined", "lychee", "one page rules", "opr",
    }
    for s in raw:
        n = norm_text(s)
        if not n or n in NOISE:
            continue
        segs.append(n)
    return segs


def score_match(alias_phrase: str, unit: UnitRef, v_text: str, sys_hint: Optional[str], seg_set: Optional[Set[str]] = None) -> float:
    # base scores
    score = 10.0
    # longer phrases weigh a bit more
    score += min(5.0, len(alias_phrase) / 10.0)
    # system consistency boost
    if sys_hint and unit.system_key == sys_hint:
        score += 3.0
    # cross-system penalty: if we have a system hint that contradicts the unit's system, penalize
    if sys_hint and unit.system_key and unit.system_key != sys_hint:
        score -= 6.0
    # light faction boost if faction token present in text
    if unit.faction_key and re.search(rf"\b{re.escape(unit.faction_key)}\b", v_text):
        score += 2.0
    # Strong boost when the alias exactly equals a path segment (unit folder certainty)
    if seg_set and alias_phrase in seg_set:
        # Do not boost for generic single-word role tokens (e.g., 'rangers')
        if alias_phrase not in GENERIC_ROLE_ALIASES:
            score += 6.0
    # Generic alias penalty: avoid accepting units based solely on ambiguous single-word roles
    if alias_phrase in GENERIC_ROLE_ALIASES:
        score -= 8.0
    return score


def find_best_matches(
    idx: Dict[str, List[UnitRef]],
    v_text: str,
    sys_hint: Optional[str],
    mount_children: Optional[Dict[str, List[UnitRef]]] = None,
    spells_by_faction: Optional[Dict[str, List[UnitRef]]] = None,
    path_segment_set: Optional[Set[str]] = None,
) -> List[Tuple[UnitRef, float, str]]:
    # First collect all matched phrases
    matched: Dict[str, List[UnitRef]] = {}
    for phrase, refs in idx.items():
        if not phrase:
            continue
        pattern = rf"\b{re.escape(phrase)}\b"
        if re.search(pattern, v_text):
            matched.setdefault(phrase, []).extend(refs)

    if not matched:
        # If no direct phrase matches, try injecting spell candidates in spell context
        results: List[Tuple[UnitRef, float, str]] = []
        if spells_by_faction is not None:
            results = inject_spell_candidates(results, spells_by_faction, v_text)
            if results:
                results = apply_spell_bias(results, v_text)
        return results

    # Prefer longest specific phrases: drop any phrase that is strictly contained
    # within another matched phrase. This avoids matching "assault squad" when
    # "terminator assault squad" is also present.
    phrases = sorted(matched.keys(), key=lambda p: (-len(p), p))
    kept: List[str] = []
    for p in phrases:
        if any(p != q and p in q for q in kept):
            continue  # p is subsumed by an already-kept longer phrase
        kept.append(p)

    # Score matches only for kept phrases
    results: List[Tuple[UnitRef, float, str]] = []
    for phrase in kept:
        for ref in matched[phrase]:
            results.append((ref, score_match(phrase, ref, v_text, sys_hint, path_segment_set), phrase))

    results.sort(key=lambda x: x[1], reverse=True)
    # Inject mounted candidates and apply mount bias if context detected
    if mount_children is not None:
        results = inject_mounted_candidates(results, mount_children, v_text)
        results = apply_mount_bias(results, v_text)
    if spells_by_faction is not None:
        results = inject_spell_candidates(results, spells_by_faction, v_text)
        results = apply_spell_bias(results, v_text)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Match Variants to Warhammer Units by token/alias heuristics.")
    parser.add_argument("--db-url", help="Override database URL (defaults to STLMGR_DB_URL env var or sqlite:///./data/stl_manager.db)")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N variants (0 = all)")
    parser.add_argument("--systems", nargs="*", default=None, help="Only consider units from these systems (e.g., w40k aos heresy)")
    parser.add_argument("--min-score", type=float, default=12.0, help="Minimum score threshold to accept a match")
    parser.add_argument("--delta", type=float, default=3.0, help="Minimum advantage over runner-up to accept (ambiguity guard)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite variant existing fields/links if present")
    parser.add_argument("--apply", action="store_true", help="Apply changes to DB (default is dry-run)")
    parser.add_argument("--out", default=None, help="Write JSON report to this path (default: reports/match_units_YYYYMMDD_HHMMSS.json)")
    parser.add_argument(
        "--append-timestamp",
        action="store_true",
        help=(
            "When used with --out, append a timestamp (YYYYMMDD_HHMMSS) before the extension to avoid overwriting"
        ),
    )
    parser.add_argument(
        "--include-unhinted",
        action="store_true",
        help=(
            "Include variants with no Warhammer hints and no matches in the report (default: exclude them to reduce noise)"
        ),
    )
    parser.add_argument(
        "--exclude-path-equals",
        nargs="*",
        default=["sample_store"],
        help=(
            "Exclude variants whose rel_path exactly equals any of these values (case-insensitive). "
            "Use to skip container-only folders like 'sample_store'."
        ),
    )
    parser.add_argument(
        "--include-container-folders",
        action="store_true",
        help=(
            "Include container-only folders (folders with no files where subfolders are already variants) in the report. "
            "By default these are skipped to reduce noise."
        ),
    )
    parser.add_argument(
        "--include-kit-children",
        action="store_true",
        help=(
            "Include kit children (e.g., bodies/heads/weapons sub-variants under a kit container) in the report. "
            "By default these are collapsed under the kit container to produce one result per kit."
        ),
    )
    parser.add_argument(
        "--group-kit-children",
        action="store_true",
        help=(
            "When applying matches, also assign a common model_group_id to all kit children under a kit container so the UI can aggregate them."
        ),
    )
    parser.add_argument(
        "--intended-use",
        nargs="*",
        default=None,
        help=(
            "Only process variants whose intended_use_bucket is one of these values (e.g., tabletop_intent display_large)."
        ),
    )
    parser.add_argument(
        "--tabletop-only",
        action="store_true",
        help=(
            "Shortcut for --intended-use tabletop_intent to restrict report to tabletop models only."
        ),
    )
    args = parser.parse_args()

    # Reconfigure DB session if a URL override is provided (fixes Windows env var quoting issues)
    if args.db_url:
        try:
            from sqlalchemy import create_engine as _ce
            from sqlalchemy.orm import Session as _S
            from sqlalchemy.orm import sessionmaker as _sm

            import db.session as _dbs
            try:
                _dbs.engine.dispose()
            except Exception:
                pass
            _dbs.DB_URL = args.db_url
            _dbs.engine = _ce(args.db_url, future=True)
            _dbs.SessionLocal = _sm(bind=_dbs.engine, autoflush=False, autocommit=False, class_=_S)
        except Exception as e:
            print(f"Failed to reconfigure DB session for URL {args.db_url}: {e}", file=sys.stderr)
            return

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    if args.out:
        # Use provided path and optionally append timestamp before extension
        base_path = Path(args.out)
        if args.append_timestamp:
            stem = base_path.stem or "match_units"
            suffix = base_path.suffix or ".json"
            stamped = f"{stem}_{ts}{'_apply' if args.apply else ''}{suffix}"
            out_path = base_path.with_name(stamped)
        else:
            out_path = base_path
    else:
        # Default filename already includes timestamp
        out_path = reports_dir / f"match_units_{ts}{'_apply' if args.apply else ''}.json"

    total = 0
    applied = 0
    skipped_nonwarhammer = 0
    skipped_containers_equals = 0
    skipped_containers_auto = 0
    kit_containers_included = 0
    skipped_kit_children = 0
    proposals: List[Dict[str, Any]] = []

    with get_session() as session:
        unit_idx, unit_key_index, mount_children, spells_by_faction = build_unit_alias_index(session)

        # Optionally restrict to selected systems by pruning index
        if args.systems:
            allowed = set([s.lower() for s in args.systems])
            unit_idx = {
                k: [ref for ref in v if ref.system_key in allowed]
                for k, v in unit_idx.items()
            }

        q = select(Variant)
        # Apply intended_use_bucket filter when requested
        intended_filters: Optional[List[str]] = None
        if args.tabletop_only:
            intended_filters = ["tabletop_intent"]
        elif args.intended_use:
            intended_filters = [s for s in args.intended_use if s]
        if intended_filters:
            try:
                from sqlalchemy import or_
                clauses = []
                for val in intended_filters:
                    clauses.append(Variant.intended_use_bucket == val)
                if clauses:
                    q = q.where(or_(*clauses))
            except Exception:
                # Fallback for older SQLAlchemy or missing column (should not happen with current models)
                q = q.where(Variant.intended_use_bucket.in_(intended_filters))
        if args.limit and args.limit > 0:
            q = q.limit(args.limit)
        variants = session.execute(q).scalars().all()

        # Precompute normalized rel_paths for container detection and immediate child segment names
        all_rel_paths: List[str] = []
        for v in variants:
            try:
                all_rel_paths.append((v.rel_path or "").strip().lower())
            except Exception:
                all_rel_paths.append("")

        # Helper: get immediate child segment names for a given parent rel_path
        def _immediate_child_segments(parent_rel_lower: str) -> Set[str]:
            segs: Set[str] = set()
            if not parent_rel_lower:
                return segs
            for sep in ("\\", "/"):
                prefix = parent_rel_lower + sep
                plen = len(prefix)
                for rp in all_rel_paths:
                    if rp and rp != parent_rel_lower and rp.startswith(prefix):
                        rest = rp[plen:]
                        # take only the next segment
                        nxt = re.split(r"[\\/]+", rest)[0]
                        n = norm_text(nxt)
                        if n:
                            segs.add(n)
            return segs

        KIT_CHILD_TOKENS: Set[str] = {
            "body", "bodies", "torsos", "torso",
            "head", "heads", "helmet", "helmets",
            "arm", "arms", "left arm", "right arm",
            "weapon", "weapons", "ranged", "melee",
            "bits", "bitz", "accessories", "options",
            "shields", "backpacks", "shoulder pads", "pauldrons",
        }

        def _is_kit_container(parent_rel_lower: str) -> Tuple[bool, List[str]]:
            """Heuristic: container-only folder that aggregates modular subfolders like bodies/heads/weapons.

            Returns (is_kit, matched_child_types)
            """
            child_segs = _immediate_child_segments(parent_rel_lower)
            matched = sorted([s for s in child_segs if s in KIT_CHILD_TOKENS])
            # require at least two distinct kit child types to consider it a kit container
            return (len(matched) >= 2, matched)

    # Helper to decide whether a variant has meaningful files (ignore OS noise files)
        NOISE_FILENAMES = {".ds_store", "thumbs.db", "desktop.ini"}

        def _is_noise_filename(name: str) -> bool:
            n = (name or "").strip().lower()
            if not n:
                return False
            if n in NOISE_FILENAMES:
                return True
            # AppleDouble resource fork files, e.g., '._.DS_Store'
            if n.startswith("._"):
                core = n[2:]
                if core in NOISE_FILENAMES:
                    return True
            return False

        def _has_meaningful_files(variant: Variant) -> bool:
            try:
                files = getattr(variant, 'files', []) or []
                MEANINGFUL_EXTS = {
                    "stl", "obj", "ztl",
                    "lys", "lychee", "3mf", "step", "stp",
                }
                for f in files:
                    # Skip directories
                    if getattr(f, 'is_dir', False):
                        continue
                    name = (getattr(f, 'filename', '') or '').strip().lower()
                    if not name:
                        continue
                    if _is_noise_filename(name):
                        continue
                    ext = (getattr(f, 'extension', '') or '').strip().lower()
                    # Treat only actual model/CAD/slicer files as meaningful for container-detection purposes.
                    # Archives (zip/rar/7z) and preview images should NOT force inclusion of a container-only folder.
                    if ext in MEANINGFUL_EXTS:
                        # at least one meaningful model/archive exists
                        return True
            except Exception:
                return False
            return False

        def _has_meaningful_model_files(variant: Variant) -> bool:
            """Stricter version for container collapsing: ignore archives and previews entirely.

            Returns True only if actual model/slicer/CAD files are present at this variant level.
            """
            return _has_meaningful_files(variant)

        # Precompute meaningful files and parent/child relationships for kit collapsing
        rel_lower_index: Dict[str, Variant] = {}
        for v in variants:
            try:
                rel_lower_index[(v.rel_path or "").strip().lower()] = v
            except Exception:
                continue

        # Quick helpers reusing container detection logic
        def _has_any_child_variants(parent_rel_lower: str) -> bool:
            for sep in ("\\", "/"):
                prefix = parent_rel_lower + sep
                for rp in all_rel_paths:
                    if rp and rp != parent_rel_lower and rp.startswith(prefix):
                        return True
            return False

        # Build kit container map: rel_lower -> (kit_types)
        # Prefer database flags; fall back to heuristic path-based detection for legacy DBs.
        kit_container_map: Dict[str, List[str]] = {}
        for v in variants:
            try:
                rel_lower = (v.rel_path or "").strip().lower()
            except Exception:
                rel_lower = ""
            if not rel_lower:
                continue
            # If DB says it's a kit container, trust it and take recorded kit_child_types when available
            try:
                if getattr(v, 'is_kit_container', False):
                    kt = []
                    try:
                        for t in (getattr(v, 'kit_child_types', []) or []):
                            if isinstance(t, str):
                                kt.append(norm_text(t))
                    except Exception:
                        kt = []
                    kit_container_map[rel_lower] = kt
                    continue
            except Exception:
                pass
            # Otherwise, consider heuristic container style (no meaningful model files) with children
            if not _has_meaningful_model_files(v) and _has_any_child_variants(rel_lower):
                is_kit, kit_types = _is_kit_container(rel_lower)
                if is_kit:
                    kit_container_map[rel_lower] = kit_types

        # Build a parent->children index to detect virtual kit parents even if the parent Variant doesn't exist
        parent_children_map: Dict[str, Set[str]] = defaultdict(set)
        parent_children_variants: Dict[str, List[Variant]] = defaultdict(list)
        def _parent_of(rel_lower: str) -> str:
            if not rel_lower:
                return ""
            i1 = rel_lower.rfind("\\")
            i2 = rel_lower.rfind("/")
            idx = max(i1, i2)
            if idx <= 0:
                return ""
            return rel_lower[:idx]
        for v in variants:
            rel_lower = (getattr(v, 'rel_path', '') or '').strip().lower()
            if not rel_lower:
                continue
            parent_rel = _parent_of(rel_lower)
            if not parent_rel:
                continue
            # immediate child segment name under this parent (preserving sep)
            child_seg = ""
            for sep in ("\\", "/"):
                prefix = parent_rel + sep
                if rel_lower.startswith(prefix) and len(rel_lower) > len(prefix):
                    rest = rel_lower[len(prefix):]
                    child_seg = re.split(r"[\\/]+", rest)[0]
                    break
            child_seg_norm = norm_text(child_seg)
            if child_seg_norm:
                parent_children_map[parent_rel].add(child_seg_norm)
                parent_children_variants[parent_rel].append(v)

        virtual_kit_container_map: Dict[str, List[str]] = {}
        for parent_rel, child_segs in parent_children_map.items():
            matched = sorted([s for s in child_segs if s in KIT_CHILD_TOKENS])
            if len(matched) >= 2 and parent_rel not in kit_container_map:
                virtual_kit_container_map[parent_rel] = matched

        def _find_kit_parent_rel(child_rel_lower: str) -> Optional[str]:
            if not child_rel_lower:
                return None
            # Check real kit parents
            for parent_rel in kit_container_map.keys():
                for sep in ("\\", "/"):
                    prefix = parent_rel + sep
                    if child_rel_lower != parent_rel and child_rel_lower.startswith(prefix):
                        return parent_rel
            # Check virtual kit parents
            for parent_rel in virtual_kit_container_map.keys():
                for sep in ("\\", "/"):
                    prefix = parent_rel + sep
                    if child_rel_lower != parent_rel and child_rel_lower.startswith(prefix):
                        return parent_rel
            return None

        # Prepare exclude set (lowercased)
        exclude_equals = set(s.lower() for s in (args.exclude_path_equals or []))

        # Build id -> variant for quick parent lookup
        id_index: Dict[int, Variant] = {}
        for v in variants:
            try:
                id_index[int(v.id)] = v
            except Exception:
                pass

        for v in variants:
            total += 1
            # Early skip: container-only variants by exact rel_path match
            try:
                rel_lower = (v.rel_path or "").strip().lower()
            except Exception:
                rel_lower = ""
            if rel_lower and rel_lower in exclude_equals:
                skipped_containers_equals += 1
                continue
            # Auto-skip container-only variants: no files, and there exists another variant whose rel_path starts with this rel_path + path sep
            if not args.include_container_folders:
                has_files = _has_meaningful_model_files(v)
                if (rel_lower and not has_files):
                    sep_candidates = ["\\", "/"]
                    prefix_matches = False
                    for sep in sep_candidates:
                        prefix = rel_lower + sep
                        # any other rel_path that starts with this prefix
                        for rp in all_rel_paths:
                            if rp and rp != rel_lower and rp.startswith(prefix):
                                prefix_matches = True
                                break
                        if prefix_matches:
                            break
                    if prefix_matches:
                        # Exception: keep container if it looks like a modular kit (bodies/heads/weapons...)
                        is_kit, kit_types = _is_kit_container(rel_lower)
                        if is_kit:
                            kit_containers_included += 1
                        else:
                            skipped_containers_auto += 1
                            continue

            # Collapse kit children into their parent kit container for reporting (unless explicitly included)
            if not args.include_kit_children:
                db_parent_id = None
                try:
                    db_parent_id = getattr(v, 'parent_id', None)
                except Exception:
                    db_parent_id = None
                if db_parent_id:
                    # Minimal hint-only enrichment for kit children before skipping
                    if args.apply:
                        try:
                            v_text = text_for_variant(v)
                            # Try to get parent variant from index
                            parent_v = None
                            try:
                                parent_v = id_index.get(int(db_parent_id))
                            except Exception:
                                parent_v = None
                            # System guess from text
                            sys_guess = system_hint(v_text)
                            v_norm = norm_text(v_text)
                            aos_leaf = detect_aos_faction_hint(v_norm)
                            new_fp: Optional[List[str]] = None
                            new_leaf: Optional[str] = None
                            if aos_leaf:
                                new_leaf = aos_leaf
                                ga = AOS_LEAF_TO_GRAND.get(aos_leaf)
                                new_fp = [ga, aos_leaf] if ga else [aos_leaf]
                            else:
                                ch, sf = find_chapter_hint(v_norm)
                                leaf = sf or ch
                                if leaf:
                                    new_leaf = leaf
                                    try:
                                        fac_row = session.execute(select(Faction).where(Faction.key == leaf)).scalars().first()
                                        if fac_row is not None:
                                            tmp = getattr(fac_row, 'full_path', None) or None
                                            if not tmp:
                                                chain: List[str] = []
                                                cur = fac_row; guard = 0
                                                while cur is not None and guard < 20:
                                                    k = getattr(cur, 'key', None)
                                                    if isinstance(k, str) and k:
                                                        chain.append(k)
                                                    pid = getattr(cur, 'parent_id', None)
                                                    if not pid:
                                                        break
                                                    cur = session.get(Faction, pid)
                                                    guard += 1
                                                if chain:
                                                    tmp = list(reversed(chain))
                                            if tmp:
                                                new_fp = list(tmp)
                                    except Exception:
                                        pass
                            # If no hint-derived faction, propagate from parent or Unit lookup by parent name
                            if (not new_leaf and not new_fp) and parent_v:
                                try:
                                    p_fp = getattr(parent_v, 'faction_path', None)
                                    if isinstance(p_fp, list) and p_fp:
                                        new_fp = list(p_fp)
                                        new_leaf = new_fp[-1]
                                    elif getattr(parent_v, 'codex_faction', None):
                                        cf = parent_v.codex_faction
                                        fac_row = session.execute(select(Faction).where(Faction.key == cf)).scalars().first()
                                        if fac_row is not None:
                                            tmp = getattr(fac_row, 'full_path', None) or None
                                            if not tmp:
                                                chain: List[str] = []
                                                cur = fac_row; guard = 0
                                                while cur is not None and guard < 20:
                                                    k = getattr(cur, 'key', None)
                                                    if isinstance(k, str) and k:
                                                        chain.append(k)
                                                    pid = getattr(cur, 'parent_id', None)
                                                    if not pid:
                                                        break
                                                    cur = session.get(Faction, pid)
                                                    guard += 1
                                                if chain:
                                                    tmp = list(reversed(chain))
                                            if tmp:
                                                new_fp = list(tmp)
                                                new_leaf = new_fp[-1]
                                    # Last attempt: look up Unit by parent codex_unit_name
                                    if (not new_fp) and getattr(parent_v, 'codex_unit_name', None):
                                        try:
                                            uname = parent_v.codex_unit_name
                                            urow = session.execute(select(Unit).where(Unit.name == uname)).scalars().first()
                                            if urow and getattr(urow, 'faction_id', None):
                                                f = session.get(Faction, urow.faction_id)
                                                if f is not None:
                                                    tmp = getattr(f, 'full_path', None) or None
                                                    if not tmp and getattr(f, 'key', None):
                                                        tmp = [f.key]
                                                    if tmp:
                                                        new_fp = list(tmp)
                                                        new_leaf = new_fp[-1]
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                            # Propagate codex_unit_name and game_system from parent when available
                            try:
                                if (args.overwrite or not getattr(v, 'codex_unit_name', None)) and parent_v and getattr(parent_v, 'codex_unit_name', None):
                                    v.codex_unit_name = parent_v.codex_unit_name
                            except Exception:
                                pass
                            try:
                                if args.overwrite or not getattr(v, 'game_system', None):
                                    if parent_v and getattr(parent_v, 'game_system', None):
                                        v.game_system = parent_v.game_system
                                    elif sys_guess:
                                        v.game_system = sys_guess
                                    elif aos_leaf:
                                        v.game_system = 'aos'
                            except Exception:
                                pass
                            if new_leaf or new_fp:
                                try:
                                    if new_leaf and (args.overwrite or not getattr(v, 'codex_faction', None)):
                                        v.codex_faction = new_leaf
                                except Exception:
                                    pass
                                try:
                                    if isinstance(new_fp, list) and new_fp:
                                        existing_fp = getattr(v, 'faction_path', None)
                                        cf_try = getattr(v, 'codex_faction', None)
                                        should_set = False
                                        if args.overwrite or not existing_fp:
                                            should_set = True
                                        elif isinstance(existing_fp, list):
                                            if len(existing_fp) <= 1 and len(new_fp) > len(existing_fp):
                                                if not existing_fp or (cf_try and existing_fp == [cf_try]):
                                                    should_set = True
                                        if should_set:
                                            # AoS expansion
                                            if len(new_fp) == 1:
                                                leaf = new_fp[0]
                                                ga = AOS_LEAF_TO_GRAND.get(leaf)
                                                if ga:
                                                    new_fp = [ga, leaf]
                                            v.faction_path = new_fp
                                            try:
                                                v.faction_general = new_fp[0]
                                            except Exception:
                                                pass
                                        # Ensure codex_faction present
                                        try:
                                            if args.overwrite or not getattr(v, 'codex_faction', None):
                                                v.codex_faction = new_fp[-1]
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    skipped_kit_children += 1
                    continue
                kit_parent_rel = _find_kit_parent_rel(rel_lower)
                if kit_parent_rel:
                    # Minimal hint-only enrichment for kit children before skipping
                    if args.apply:
                        try:
                            v_text = text_for_variant(v)
                            # Try to get parent variant by rel path
                            parent_v = rel_lower_index.get(kit_parent_rel)
                            sys_guess = system_hint(v_text)
                            aos_leaf = detect_aos_faction_hint(norm_text(v_text))
                            new_fp: Optional[List[str]] = None
                            new_leaf: Optional[str] = None
                            if aos_leaf:
                                new_leaf = aos_leaf
                                ga = AOS_LEAF_TO_GRAND.get(aos_leaf)
                                new_fp = [ga, aos_leaf] if ga else [aos_leaf]
                            else:
                                ch, sf = find_chapter_hint(norm_text(v_text))
                                leaf = sf or ch
                                if leaf:
                                    new_leaf = leaf
                                    try:
                                        fac_row = session.execute(select(Faction).where(Faction.key == leaf)).scalars().first()
                                        if fac_row is not None:
                                            tmp = getattr(fac_row, 'full_path', None) or None
                                            if not tmp:
                                                chain: List[str] = []
                                                cur = fac_row; guard = 0
                                                while cur is not None and guard < 20:
                                                    k = getattr(cur, 'key', None)
                                                    if isinstance(k, str) and k:
                                                        chain.append(k)
                                                    pid = getattr(cur, 'parent_id', None)
                                                    if not pid:
                                                        break
                                                    cur = session.get(Faction, pid)
                                                    guard += 1
                                                if chain:
                                                    tmp = list(reversed(chain))
                                            if tmp:
                                                new_fp = list(tmp)
                                    except Exception:
                                        pass
                            # If no hint-derived faction, propagate from parent or Unit lookup by parent name
                            if (not new_leaf and not new_fp) and parent_v:
                                try:
                                    p_fp = getattr(parent_v, 'faction_path', None)
                                    if isinstance(p_fp, list) and p_fp:
                                        new_fp = list(p_fp)
                                    elif getattr(parent_v, 'codex_faction', None):
                                        cf = parent_v.codex_faction
                                        fac_row = session.execute(select(Faction).where(Faction.key == cf)).scalars().first()
                                        if fac_row is not None:
                                            tmp = getattr(fac_row, 'full_path', None) or None
                                            if not tmp:
                                                chain: List[str] = []
                                                cur = fac_row; guard = 0
                                                while cur is not None and guard < 20:
                                                    k = getattr(cur, 'key', None)
                                                    if isinstance(k, str) and k:
                                                        chain.append(k)
                                                    pid = getattr(cur, 'parent_id', None)
                                                    if not pid:
                                                        break
                                                    cur = session.get(Faction, pid)
                                                    guard += 1
                                                if chain:
                                                    tmp = list(reversed(chain))
                                            if tmp:
                                                new_fp = list(tmp)
                                                new_leaf = cf
                                    # Last attempt: look up Unit by parent codex_unit_name
                                    if (not new_fp) and getattr(parent_v, 'codex_unit_name', None):
                                        try:
                                            uname = parent_v.codex_unit_name
                                            urow = session.execute(select(Unit).where(Unit.name == uname)).scalars().first()
                                            if urow and getattr(urow, 'faction_id', None):
                                                f = session.get(Faction, urow.faction_id)
                                                if f is not None:
                                                    tmp = getattr(f, 'full_path', None) or None
                                                    if not tmp and getattr(f, 'key', None):
                                                        tmp = [f.key]
                                                    if tmp:
                                                        new_fp = list(tmp)
                                                        new_leaf = tmp[-1]
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                            # Propagate codex_unit_name and game_system from parent when available
                            try:
                                if (args.overwrite or not getattr(v, 'codex_unit_name', None)) and parent_v and getattr(parent_v, 'codex_unit_name', None):
                                    v.codex_unit_name = parent_v.codex_unit_name
                            except Exception:
                                pass
                            try:
                                if args.overwrite or not getattr(v, 'game_system', None):
                                    if parent_v and getattr(parent_v, 'game_system', None):
                                        v.game_system = parent_v.game_system
                                    elif sys_guess:
                                        v.game_system = sys_guess
                                    elif aos_leaf:
                                        v.game_system = 'aos'
                            except Exception:
                                pass
                            if new_leaf or new_fp:
                                try:
                                    if new_leaf and (args.overwrite or not getattr(v, 'codex_faction', None)):
                                        v.codex_faction = new_leaf
                                except Exception:
                                    pass
                                try:
                                    if isinstance(new_fp, list) and new_fp:
                                        existing_fp = getattr(v, 'faction_path', None)
                                        cf_try = getattr(v, 'codex_faction', None)
                                        should_set = False
                                        if args.overwrite or not existing_fp:
                                            should_set = True
                                        elif isinstance(existing_fp, list):
                                            if len(existing_fp) <= 1 and len(new_fp) > len(existing_fp):
                                                if not existing_fp or (cf_try and existing_fp == [cf_try]):
                                                    should_set = True
                                        if should_set:
                                            # AoS expansion
                                            if len(new_fp) == 1:
                                                leaf = new_fp[0]
                                                ga = AOS_LEAF_TO_GRAND.get(leaf)
                                                if ga:
                                                    new_fp = [ga, leaf]
                                            v.faction_path = new_fp
                                        try:
                                            fg = getattr(v, 'faction_general', None)
                                            if args.overwrite or not fg or (isinstance(fg, str) and cf_try and fg == cf_try):
                                                v.faction_general = new_fp[0]
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    skipped_kit_children += 1
                    continue
            v_text = text_for_variant(v)
            # Precompute normalized path segments for unit-folder certainty boosts
            seg_set: Set[str] = set(_path_segments(v.rel_path))
            sys_h = system_hint(v_text) or (v.game_system.lower() if v.game_system else None)
            matches = find_best_matches(unit_idx, v_text, sys_h, mount_children, spells_by_faction, seg_set)
            chap_hint, subf_hint = find_chapter_hint(v_text)  # e.g., blood_angels / ravenwing from top folder names

            accepted: Optional[Tuple[UnitRef, float, str]] = None
            also_accepted: List[Tuple[UnitRef, float, str]] = []
            ambiguous: List[Tuple[UnitRef, float, str]] = []
            if matches:
                # Focus on the longest phrase group (already biased by find_best_matches),
                # and accept co-equal matches across systems when within delta.
                top = matches[0]
                if top[1] >= args.min_score:
                    # Determine co-acceptance window based on same phrase and close scores
                    same_phrase = [m for m in matches if m[2] == top[2]]
                    same_phrase.sort(key=lambda x: x[1], reverse=True)
                    window = [m for m in same_phrase if (top[1] - m[1]) <= args.delta and m[1] >= args.min_score]
                    if window:
                        accepted = top
                        also_accepted = [m for m in window if m is not top]
                    else:
                        # Fall back to ambiguity if runner-up too close on a different phrase
                        if len(matches) == 1 or (top[1] - matches[1][1]) >= args.delta:
                            accepted = top
                        else:
                            ambiguous = matches[:5]

            # Kit reporting metadata (DB-aware)
            # Prefer DB flags for kit containers and children; fall back to heuristics for legacy entries.
            is_kit_flag = False
            kit_child_types: List[str] = []
            try:
                if getattr(v, 'is_kit_container', False):
                    is_kit_flag = True
                    try:
                        kit_child_types = [norm_text(t) for t in (getattr(v, 'kit_child_types', []) or []) if isinstance(t, str)]
                    except Exception:
                        kit_child_types = []
                else:
                    is_kit_flag, kit_child_types = _is_kit_container(rel_lower)
            except Exception:
                is_kit_flag, kit_child_types = _is_kit_container(rel_lower)

            kit_parent_rel: Optional[str] = None
            kit_child_label: Optional[str] = None
            # DB parent relationship
            db_parent_id = None
            try:
                db_parent_id = getattr(v, 'parent_id', None)
            except Exception:
                db_parent_id = None
            if db_parent_id:
                parent_v = id_index.get(int(db_parent_id))
                if parent_v:
                    kit_parent_rel = getattr(parent_v, 'rel_path', None)
                    # Prefer stored part_pack_type as the child label when present
                    lab = None
                    try:
                        lab = getattr(v, 'part_pack_type', None)
                    except Exception:
                        lab = None
                    if lab:
                        kit_child_label = norm_text(str(lab))
                # If DB parent exists we won't compute heuristic child label further
            if not kit_parent_rel:
                # Heuristic fallback: derive from path structure
                kpr = _find_kit_parent_rel(rel_lower)
                if kpr:
                    kit_parent_rel = kpr
                    for sep in ("\\", "/"):
                        prefix = kpr + sep
                        if rel_lower.startswith(prefix) and len(rel_lower) > len(prefix):
                            rest = rel_lower[len(prefix):]
                            nxt = re.split(r"[\\/]+", rest)[0]
                            lab = norm_text(nxt)
                            if lab:
                                kit_child_label = lab
                            break

            prop = {
                "variant_id": v.id,
                "rel_path": v.rel_path,
                "filename": v.filename,
                "system_hint": sys_h,
                "chapter_hint": chap_hint,
                "subfaction_hint": subf_hint,
                "kit_container": is_kit_flag,
                **({"kit_child_types": kit_child_types} if is_kit_flag else {}),
                **({
                    "kit_child_of": True,
                    "kit_parent_rel": kit_parent_rel,
                    "kit_child_label": kit_child_label,
                } if kit_parent_rel else {"kit_child_of": False}),
                "accepted": None,
                "ambiguous": [
                    {
                        "unit_id": m[0].unit_id,
                        "unit_key": m[0].unit_key,
                        "unit_name": m[0].unit_name,
                        "system_key": m[0].system_key,
                        "faction_key": m[0].faction_key,
                        "score": m[1],
                        "via": m[2],
                    }
                    for m in ambiguous
                ],
            }

            if accepted:
                ref, score, via = accepted
                prop["accepted"] = {
                    "unit_id": ref.unit_id,
                    "unit_key": ref.unit_key,
                    "unit_name": ref.unit_name,
                    "system_key": ref.system_key,
                    "faction_key": ref.faction_key,
                    "score": score,
                    "via": via,
                }
                if also_accepted:
                    prop["also_accepted"] = [
                        {
                            "unit_id": r[0].unit_id,
                            "unit_key": r[0].unit_key,
                            "unit_name": r[0].unit_name,
                            "system_key": r[0].system_key,
                            "faction_key": r[0].faction_key,
                            "score": r[1],
                            "via": r[2],
                        }
                        for r in also_accepted
                    ]

                if args.apply:
                    # If not overwriting and variant already has core fields, we'll enrich but not modify core fields/links.
                    existing_core = False
                    if not args.overwrite and (v.game_system or v.codex_unit_name):
                        existing_core = True
                    # Set variant columns. If multiple accepted across systems, avoid
                    # forcing a single game_system; otherwise set to the primary.
                    if not existing_core:
                        if not also_accepted:
                            v.game_system = ref.system_key
                        v.codex_unit_name = ref.unit_name
                        # Single source of truth: prefer Unit table faction over token-derived hints
                        if ref.faction_key:
                            v.codex_faction = ref.faction_key
                        elif subf_hint:
                            v.codex_faction = subf_hint
                        elif chap_hint:
                            v.codex_faction = chap_hint
                    # Enrich with additional codex-derived metadata when available
                    try:
                        urow = session.get(Unit, ref.unit_id)
                    except Exception:
                        urow = None
                    if urow is not None:
                        # Game system from matched unit (fill if missing even when also_accepted exists)
                        try:
                            if args.overwrite or not getattr(v, 'game_system', None):
                                if getattr(ref, 'system_key', None):
                                    v.game_system = ref.system_key
                        except Exception:
                            pass

                        # Tabletop role from Unit.role
                        try:
                            if args.overwrite or not getattr(v, 'tabletop_role', None):
                                if getattr(urow, 'role', None):
                                    v.tabletop_role = urow.role
                        except Exception:
                            pass

                        # Ensure intended_use_bucket defaults for tabletop-like variants once system/faction is known
                        try:
                            if args.apply and (args.overwrite or not getattr(v, 'intended_use_bucket', None)):
                                if getattr(v, 'game_system', None) or getattr(v, 'codex_faction', None) or getattr(ref, 'system_key', None):
                                    v.intended_use_bucket = 'tabletop_intent'
                        except Exception:
                            pass

                        # Default scale by system (if unset). Prefer DB defaults on GameSystem, else fall back.
                        try:
                            if args.apply:
                                sys_key = getattr(ref, 'system_key', None) or getattr(v, 'game_system', None)
                                if sys_key:
                                    # fetch GameSystem row if present
                                    gs = None
                                    try:
                                        gs = session.query(GameSystem).filter(GameSystem.key == sys_key).first()
                                    except Exception:
                                        gs = None
                                    if args.overwrite or not getattr(v, 'scale_ratio_den', None):
                                        den = (getattr(gs, 'default_scale_den', None) if gs else None) or SYSTEM_DEFAULT_SCALE_DEN.get(sys_key)
                                        if den:
                                            v.scale_ratio_den = den
                                    if args.overwrite or not getattr(v, 'scale_name', None):
                                        sname = (getattr(gs, 'default_scale_name', None) if gs else None) or SYSTEM_DEFAULT_SCALE_NAME.get(sys_key)
                                        if sname:
                                            v.scale_name = sname
                        except Exception:
                            pass

                        # Default scale based on system if not already set
                        try:
                            if args.apply and (args.overwrite or getattr(v, 'scale_ratio_den', None) in (None, 0)):
                                sys_key = getattr(v, 'game_system', None) or getattr(ref, 'system_key', None)
                                if sys_key and sys_key in DEFAULT_SCALE_BY_SYSTEM:
                                    v.scale_ratio_den = DEFAULT_SCALE_BY_SYSTEM[sys_key]
                        except Exception:
                            pass

                        # Faction path enrichment: always compute a candidate path, then upgrade if it's better
                        try:
                            new_fp: Optional[List[str]] = None
                            # Prefer Unit.faction relationship
                            fobj = getattr(urow, 'faction', None)
                            if fobj is not None:
                                # If variant has no codex_faction yet, set leaf faction key from Unit
                                try:
                                    if args.overwrite or not getattr(v, 'codex_faction', None):
                                        k = getattr(fobj, 'key', None)
                                        if isinstance(k, str) and k:
                                            v.codex_faction = k
                                except Exception:
                                    pass
                                tmp = getattr(fobj, 'full_path', None) or None
                                if tmp:
                                    new_fp = list(tmp)
                                else:
                                    k = getattr(fobj, 'key', None)
                                    if isinstance(k, str) and k:
                                        new_fp = [k]
                            # Try via faction_id if relationship wasn’t loaded
                            if new_fp is None and getattr(urow, 'faction_id', None):
                                try:
                                    fobj2 = session.get(Faction, getattr(urow, 'faction_id'))
                                    if fobj2 is not None:
                                        tmp = getattr(fobj2, 'full_path', None) or None
                                        if tmp:
                                            new_fp = list(tmp)
                                        else:
                                            k = getattr(fobj2, 'key', None)
                                            if isinstance(k, str) and k:
                                                new_fp = [k]
                                except Exception:
                                    pass
                            # As a last resort, derive from Unit.available_to when it points to a single root
                            if new_fp is None and (args.overwrite or not getattr(v, 'codex_faction', None)):
                                try:
                                    avail = getattr(urow, 'available_to', None)
                                    root_key = None
                                    if isinstance(avail, (list, tuple)) and len(avail) == 1:
                                        entry = str(avail[0])
                                        root_key = entry.split('/*')[0] if '/*' in entry else entry
                                    # If we found a plausible root_key, prefer it
                                    if root_key:
                                        # Validate it exists in Faction table and pick its full path if available
                                        fac_row = session.execute(select(Faction).where(Faction.key == root_key)).scalars().first()
                                        if fac_row is not None:
                                            # Set codex_faction if still empty
                                            if args.overwrite or not getattr(v, 'codex_faction', None):
                                                v.codex_faction = root_key
                                            tmp = getattr(fac_row, 'full_path', None) or None
                                            if tmp:
                                                new_fp = list(tmp)
                                            else:
                                                new_fp = [root_key]
                                except Exception:
                                    pass
                            # Fallback: derive from codex_faction by walking parent chain
                            if new_fp is None:
                                try:
                                    cf = getattr(v, 'codex_faction', None)
                                    if isinstance(cf, str) and cf:
                                        fac_row = session.execute(select(Faction).where(Faction.key == cf)).scalars().first()
                                        if fac_row is not None:
                                            tmp = getattr(fac_row, 'full_path', None) or None
                                            if not tmp:
                                                try:
                                                    # Build by climbing parents
                                                    chain: List[str] = []
                                                    cur = fac_row
                                                    guard = 0
                                                    while cur is not None and guard < 20:
                                                        k = getattr(cur, 'key', None)
                                                        if isinstance(k, str) and k:
                                                            chain.append(k)
                                                        pid = getattr(cur, 'parent_id', None)
                                                        if not pid:
                                                            break
                                                        cur = session.get(Faction, pid)
                                                        guard += 1
                                                    if chain:
                                                        tmp = list(reversed(chain))
                                                except Exception:
                                                    tmp = None
                                            if tmp:
                                                new_fp = list(tmp)
                                except Exception:
                                    pass

                            # Decide whether to set/upgrade
                            if isinstance(new_fp, list) and new_fp:
                                # Expand AoS leaf faction to include Grand Alliance if path has only a leaf
                                if len(new_fp) == 1:
                                    leaf = new_fp[0]
                                    ga = AOS_LEAF_TO_GRAND.get(leaf)
                                    if ga:
                                        new_fp = [ga, leaf]
                                existing_fp = getattr(v, 'faction_path', None)
                                cf_try = getattr(v, 'codex_faction', None)
                                should_set = False
                                if args.overwrite or not existing_fp:
                                    should_set = True
                                elif isinstance(existing_fp, list):
                                    # Upgrade if new path is longer or different and existing is leaf/equal to codex_faction
                                    if len(existing_fp) <= 1 and len(new_fp) > len(existing_fp):
                                        if not existing_fp or (cf_try and existing_fp == [cf_try]):
                                            should_set = True
                                if should_set:
                                    v.faction_path = new_fp
                                # Set/upgrade faction_general: upgrade when existing equals leaf or is missing
                                try:
                                    fg = getattr(v, 'faction_general', None)
                                    if args.overwrite or not fg or (isinstance(fg, str) and cf_try and fg == cf_try):
                                        v.faction_general = new_fp[0]
                                except Exception:
                                    pass
                                # Backfill codex_faction from leaf if missing
                                try:
                                    if args.overwrite or not getattr(v, 'codex_faction', None):
                                        v.codex_faction = new_fp[-1]
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        # Asset category: map special Unit.category types to Variant.asset_category
                        try:
                            cat = getattr(urow, 'category', None)
                            if cat:
                                mapped = None
                                if cat in {"endless_spell", "manifestation", "invocation"}:
                                    mapped = "spell"
                                elif cat == "terrain":
                                    mapped = "terrain"
                                elif cat == "regiment":
                                    mapped = "regiment"
                                if mapped and (args.overwrite or not getattr(v, 'asset_category', None)):
                                    v.asset_category = mapped
                        except Exception:
                            pass

                        # Base size (safe subset): only set for single-diameter profiles like infantry_25
                        try:
                            bpk = getattr(urow, 'base_profile_key', None)
                            if bpk and (args.overwrite or getattr(v, 'base_size_mm', None) in (None, 0)):
                                m = re.fullmatch(r"[a-z0-9]+_(\d{2,3})", str(bpk))
                                if m:
                                    size = int(m.group(1))
                                    if 10 <= size <= 200:
                                        v.base_size_mm = size
                        except Exception:
                            pass
                    # If this is a kit container, tag the variant as a squad kit for downstream UI/logic
                    if is_kit_flag and not existing_core:
                        try:
                            v.part_pack_type = v.part_pack_type or "squad_kit"
                            if not v.segmentation:
                                v.segmentation = "multi-part"
                            # Optionally group all children under this kit parent using a shared model_group_id
                            if args.group_kit_children:
                                group_id = v.model_group_id or f"kit:{v.id}"
                                v.model_group_id = group_id
                                # propagate grouping to children
                                parent_rel = (v.rel_path or "").strip().lower()
                                for child_rel, child_v in rel_lower_index.items():
                                    for sep in ("\\", "/"):
                                        prefix = parent_rel + sep
                                        if child_rel != parent_rel and child_rel.startswith(prefix):
                                            try:
                                                if not child_v.model_group_id:
                                                    child_v.model_group_id = group_id
                                            except Exception:
                                                pass
                        except Exception:
                            pass
                    # Create or replace link (skip link mutations when preserving existing core)
                    if not existing_core:
                        if args.overwrite:
                            session.query(VariantUnitLink).filter(VariantUnitLink.variant_id == v.id).delete()
                        # Primary link (top score)
                        session.add(
                            VariantUnitLink(
                                variant_id=v.id,
                                unit_id=ref.unit_id,
                                is_primary=True,
                                match_method="token",
                                match_confidence=min(1.0, score / 20.0),
                                notes=f"via='{via}' sys_hint='{sys_h or ''}' chapter_hint='{chap_hint or ''}' subfaction_hint='{subf_hint or ''}'",
                            )
                        )
                        # Additional co-accepted links (e.g., cross-system duplicates)
                        for r in also_accepted:
                            session.add(
                                VariantUnitLink(
                                    variant_id=v.id,
                                    unit_id=r[0].unit_id,
                                    is_primary=False,
                                    match_method="token",
                                    match_confidence=min(1.0, r[1] / 20.0),
                                    notes=f"via='{r[2]}' sys_hint='{sys_h or ''}' chapter_hint='{chap_hint or ''}' subfaction_hint='{subf_hint or ''}' co-accepted",
                                )
                            )
                    applied += 1

            # Reporting filter: exclude variants with no Warhammer hints and no matches unless explicitly included
            has_any_hint = (sys_h is not None) or bool(matches)
            if args.include_unhinted or has_any_hint:
                proposals.append(prop)
            else:
                skipped_nonwarhammer += 1

            # Hint-only enrichment: if no accepted match and applying, populate coarse faction from text hints
            if args.apply and not accepted:
                try:
                    # Try AoS faction from path tokens
                    aos_leaf = detect_aos_faction_hint(norm_text(v_text))
                    new_fp: Optional[List[str]] = None
                    new_leaf: Optional[str] = None
                    sys_guess = system_hint(v_text)
                    if aos_leaf:
                        new_leaf = aos_leaf
                        ga = AOS_LEAF_TO_GRAND.get(aos_leaf)
                        new_fp = [ga, aos_leaf] if ga else [aos_leaf]
                        # Set system to aos if confident
                        try:
                            if args.overwrite or not getattr(v, 'game_system', None):
                                v.game_system = 'aos'
                        except Exception:
                            pass
                    else:
                        # Try Space Marine chapter hint
                        ch, sf = chap_hint, subf_hint
                        leaf = sf or ch
                        if leaf:
                            new_leaf = leaf
                            # Build via Faction table if present to get parent (e.g., space_marines)
                            try:
                                fac_row = session.execute(select(Faction).where(Faction.key == leaf)).scalars().first()
                                if fac_row is not None:
                                    tmp = getattr(fac_row, 'full_path', None) or None
                                    if not tmp:
                                        chain: List[str] = []
                                        cur = fac_row; guard = 0
                                        while cur is not None and guard < 20:
                                            k = getattr(cur, 'key', None)
                                            if isinstance(k, str) and k:
                                                chain.append(k)
                                            pid = getattr(cur, 'parent_id', None)
                                            if not pid:
                                                break
                                            cur = session.get(Faction, pid)
                                            guard += 1
                                        if chain:
                                            tmp = list(reversed(chain))
                                    if tmp:
                                        new_fp = list(tmp)
                            except Exception:
                                pass

                    # Apply if we derived anything
                    if new_leaf or new_fp:
                        try:
                            if new_leaf and (args.overwrite or not getattr(v, 'codex_faction', None)):
                                v.codex_faction = new_leaf
                        except Exception:
                            pass
                        # If we didn’t set system yet, use sys_guess
                        try:
                            if args.overwrite or not getattr(v, 'game_system', None):
                                if sys_guess:
                                    v.game_system = sys_guess
                        except Exception:
                            pass
                        try:
                            if isinstance(new_fp, list) and new_fp:
                                existing_fp = getattr(v, 'faction_path', None)
                                cf_try = getattr(v, 'codex_faction', None)
                                should_set = False
                                if args.overwrite or not existing_fp:
                                    should_set = True
                                elif isinstance(existing_fp, list):
                                    if len(existing_fp) <= 1 and len(new_fp) > len(existing_fp):
                                        if not existing_fp or (cf_try and existing_fp == [cf_try]):
                                            should_set = True
                                if should_set:
                                    v.faction_path = new_fp
                                # Coarse bucket
                                try:
                                    fg = getattr(v, 'faction_general', None)
                                    if args.overwrite or not fg or (isinstance(fg, str) and cf_try and fg == cf_try):
                                        v.faction_general = new_fp[0]
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass

        if args.apply:
            session.commit()

    # Write report
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({
            "ts": datetime.utcnow().isoformat() + "Z",
            "apply": args.apply,
            "include_kit_children": args.include_kit_children,
            "limit": args.limit,
            "systems": args.systems,
            "min_score": args.min_score,
            "delta": args.delta,
            "overwrite": args.overwrite,
            "exclude_path_equals": args.exclude_path_equals,
            "total_variants": total,
            "applied": applied,
            "skipped_nonwarhammer": skipped_nonwarhammer,
            "skipped_containers": skipped_containers_equals + skipped_containers_auto,
            "skipped_containers_detail": {
                "equals": skipped_containers_equals,
                "auto": skipped_containers_auto,
            },
            "skipped_kit_children": skipped_kit_children,
            "kit_containers_included": kit_containers_included,
            "proposals": proposals,
        }, f, ensure_ascii=False, indent=2)

    # If applying with grouping enabled, propagate grouping to virtual kit children even when parent variant doesn't exist
    if args.apply and args.group_kit_children:
        with get_session() as session:
            for parent_rel, kit_types in virtual_kit_container_map.items():
                # deterministic, compact group id based on parent path
                gid = "kit:" + hashlib.md5(parent_rel.encode("utf-8")).hexdigest()[:12]
                for child_v in parent_children_variants.get(parent_rel, []):
                    try:
                        if not child_v.model_group_id:
                            child_v.model_group_id = gid
                    except Exception:
                        pass
            session.commit()

    print(f"Report written: {out_path}")
    if args.apply:
        print(f"Applied matches: {applied}/{total}")
    if skipped_nonwarhammer:
        print(f"Skipped (non-Warhammer/no-hint): {skipped_nonwarhammer}")
    total_containers = skipped_containers_equals + skipped_containers_auto
    if total_containers:
        msg = []
        if skipped_containers_equals:
            msg.append(f"equals={skipped_containers_equals} -> {', '.join(args.exclude_path_equals or [])}")
        if skipped_containers_auto:
            msg.append(f"auto={skipped_containers_auto}")
        print(f"Skipped (containers): {total_containers} ({'; '.join(msg)})")


if __name__ == "__main__":
    main()
