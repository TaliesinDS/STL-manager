from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Set

from sqlalchemy import select

import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.models import Variant, Unit, GameSystem, Faction, VariantUnitLink  # type: ignore
from db.session import get_session  # type: ignore


WORD_SEP_RE = re.compile(r"[\W_]+", re.UNICODE)


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
    if any(k in t for k in ["aos", "age of sigmar", "sigmar"]):
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
    unit_rows = session.execute(
        select(Unit.id, Unit.system_id, Unit.faction_id, Unit.key, Unit.name, Unit.aliases, Unit.category)
    ).all()
    for u in unit_rows:
        u_id = u.id
        u_system_id = u.system_id
        u_faction_id = u.faction_id
        u_key = u.key
        u_name = u.name
        u_aliases = u.aliases
        u_category = u.category
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


def score_match(alias_phrase: str, unit: UnitRef, v_text: str, sys_hint: Optional[str]) -> float:
    # base scores
    score = 10.0
    # longer phrases weigh a bit more
    score += min(5.0, len(alias_phrase) / 10.0)
    # system consistency boost
    if sys_hint and unit.system_key == sys_hint:
        score += 3.0
    # light faction boost if faction token present in text
    if unit.faction_key and re.search(rf"\b{re.escape(unit.faction_key)}\b", v_text):
        score += 2.0
    return score


def find_best_matches(
    idx: Dict[str, List[UnitRef]],
    v_text: str,
    sys_hint: Optional[str],
    mount_children: Optional[Dict[str, List[UnitRef]]] = None,
    spells_by_faction: Optional[Dict[str, List[UnitRef]]] = None,
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
            results.append((ref, score_match(phrase, ref, v_text, sys_hint), phrase))

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
    args = parser.parse_args()

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
    skipped_containers = 0
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
        if args.limit and args.limit > 0:
            q = q.limit(args.limit)
        variants = session.execute(q).scalars().all()

        # Prepare exclude set (lowercased)
        exclude_equals = set(s.lower() for s in (args.exclude_path_equals or []))

        for v in variants:
            total += 1
            # Early skip: container-only variants by exact rel_path match
            try:
                rel_lower = (v.rel_path or "").strip().lower()
            except Exception:
                rel_lower = ""
            if rel_lower and rel_lower in exclude_equals:
                skipped_containers += 1
                continue
            v_text = text_for_variant(v)
            sys_h = system_hint(v_text) or (v.game_system.lower() if v.game_system else None)
            matches = find_best_matches(unit_idx, v_text, sys_h, mount_children, spells_by_faction)
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

            prop = {
                "variant_id": v.id,
                "rel_path": v.rel_path,
                "filename": v.filename,
                "system_hint": sys_h,
                "chapter_hint": chap_hint,
                "subfaction_hint": subf_hint,
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
                    # Optionally skip if already has links/fields and not overwriting
                    if not args.overwrite:
                        if v.game_system or v.codex_unit_name:
                            # Even if we don't overwrite, still record the proposal if it passes reporting filter below
                            has_any_hint = (sys_h is not None) or bool(matches)
                            if args.include_unhinted or has_any_hint:
                                proposals.append(prop)
                            else:
                                skipped_nonwarhammer += 1
                            continue
                    # Set variant columns. If multiple accepted across systems, avoid
                    # forcing a single game_system; otherwise set to the primary.
                    if not also_accepted:
                        v.game_system = ref.system_key
                    v.codex_unit_name = ref.unit_name
                    # Prefer explicit subfaction > chapter from path; otherwise
                    # fall back to unit's faction.
                    if subf_hint:
                        v.codex_faction = subf_hint
                    elif chap_hint:
                        v.codex_faction = chap_hint
                    elif ref.faction_key:
                        v.codex_faction = ref.faction_key
                    # Create or replace link
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

        if args.apply:
            session.commit()

    # Write report
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({
            "ts": datetime.utcnow().isoformat() + "Z",
            "apply": args.apply,
            "limit": args.limit,
            "systems": args.systems,
            "min_score": args.min_score,
            "delta": args.delta,
            "overwrite": args.overwrite,
            "exclude_path_equals": args.exclude_path_equals,
            "total_variants": total,
            "applied": applied,
            "skipped_nonwarhammer": skipped_nonwarhammer,
            "skipped_containers": skipped_containers,
            "proposals": proposals,
        }, f, ensure_ascii=False, indent=2)

    print(f"Report written: {out_path}")
    if args.apply:
        print(f"Applied matches: {applied}/{total}")
    if skipped_nonwarhammer:
        print(f"Skipped (non-Warhammer/no-hint): {skipped_nonwarhammer}")
    if skipped_containers:
        print(f"Skipped (container rel_path equals): {skipped_containers} -> {', '.join(args.exclude_path_equals or [])}")


if __name__ == "__main__":
    main()
