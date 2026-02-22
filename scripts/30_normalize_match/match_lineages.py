from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]

from db.models import Lineage, Variant  # type: ignore
from db.session import get_session, reconfigure  # type: ignore

WORD_SEP_RE = re.compile(r"[\W_]+", re.UNICODE)


def norm_text(s: str) -> str:
    s = (s or "").lower()
    s = WORD_SEP_RE.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


# Equivalence patterns to catch morphological variants not present in aliases
# e.g., 'demoness' should satisfy 'demon'/'daemon' lineage phrases
SPECIAL_EQUIV: Dict[str, List[re.Pattern]] = {
    'demon': [
        re.compile(r"\bdemoness(es)?\b"),
        re.compile(r"\bdaemoness(es)?\b"),
        re.compile(r"\bdaemonette(s)?\b"),
    ],
    'daemon': [
        re.compile(r"\bdemoness(es)?\b"),
        re.compile(r"\bdaemoness(es)?\b"),
        re.compile(r"\bdaemonette(s)?\b"),
    ],
    'knight': [
        re.compile(r"\bsir\b"),
    ],
    'human': [
        re.compile(r"\bfreeguild\b"),
        re.compile(r"\bgeneral\b"),
    ],
    'dragon': [
        re.compile(r"\bdraggon(s)?\b"),
    ],
    'zombie dragon': [
        re.compile(r"\bzombie draggon(s)?\b"),
    ],
    'stag': [
        re.compile(r"\bantler(s)?\b"),
        re.compile(r"\bantlerguard(s)?\b"),
    ],
    # Generic plural/synonym handling for common mounts
    'horse': [re.compile(r"\bhorses\b")],
    'wolf': [re.compile(r"\bwolves\b"), re.compile(r"\bdire wolf(ves)?\b"), re.compile(r"\bwarg(s)?\b"), re.compile(r"\bgiant wolf(ves)?\b")],
    'boar': [re.compile(r"\bboars\b")],
    'bear': [re.compile(r"\bbears\b"), re.compile(r"\bpolar bear(s)?\b")],
    'bat': [re.compile(r"\bbats\b"), re.compile(r"\bfell bat(s)?\b")],
    'wyvern': [re.compile(r"\bwyverns\b")],
    'drake': [re.compile(r"\bdrakes\b")],
    'dragon': [re.compile(r"\bdragons\b"), re.compile(r"\bdraggon(s)?\b")],  # noqa: F601
    'griffon': [re.compile(r"\bgriffons\b")],
    'gryphon': [re.compile(r"\bgryphons\b")],
    'griffin': [re.compile(r"\bgriffins\b")],
    'pegasus': [re.compile(r"\bpegasi\b")],
    'manticore': [re.compile(r"\bmanticores\b")],
    'chimera': [re.compile(r"\bchimeras\b")],
    'stag': [re.compile(r"\bstags\b"), re.compile(r"\bantler(s)?\b"), re.compile(r"\bantlerguard(s)?\b")],  # noqa: F601
    'elk': [re.compile(r"\belks\b"), re.compile(r"\bmoose\b")],
    'lion': [re.compile(r"\blions\b")],
    'sabretooth': [re.compile(r"\bsab(er|re)[- ]?tooth(ed)?(s)?\b"), re.compile(r"\bsaber(cat|tusk)s?\b"), re.compile(r"\bsabre(cat|tusk)s?\b")],
    'raptor': [re.compile(r"\braptors\b"), re.compile(r"\bvelociraptor(s)?\b")],
    'camel': [re.compile(r"\bcamels\b"), re.compile(r"\bdromedary(s)?\b")],
    'ram': [re.compile(r"\brams\b"), re.compile(r"\bgoat(s)?\b")],
    'rhinox': [re.compile(r"\brhino(ceros|s)?\b")],
    'elephant': [re.compile(r"\belephants\b"), re.compile(r"\bwar elephant(s)?\b")],
    'mammoth': [re.compile(r"\bmammoths\b")],
    'spider': [re.compile(r"\bspiders\b"), re.compile(r"\bgiant spider(s)?\b")],
    'scorpion': [re.compile(r"\bscorpions\b"), re.compile(r"\bgiant scorpion(s)?\b")],
    'serpent': [re.compile(r"\bserpents\b"), re.compile(r"\bsnake(s)?\b"), re.compile(r"\bpython(s)?\b")],
    'lizard': [re.compile(r"\blizards\b"), re.compile(r"\bgiant lizard(s)?\b"), re.compile(r"\bcold one(s)?\b")],
    'eagle': [re.compile(r"\beagles\b"), re.compile(r"\bgiant eagle(s)?\b")],
    'unicorn': [re.compile(r"\bunicorns\b")],
}


def _phrase_match(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    if re.search(rf"\b{re.escape(phrase)}\b", text):
        return True
    eqs = SPECIAL_EQUIV.get(phrase)
    if eqs:
        for pat in eqs:
            if pat.search(text):
                return True
    return False


# Rider-over-mount heuristics
ANIMAL_MOUNT_KEYS: Set[str] = {
    'horse','horses',
    'wolf','wolves','dire wolf','warg','giant wolf',
    'boar','boars',
    'bear','bears','polar bear',
    'bat','bats','fell bat',
    'wyvern','wyverns',
    'drake','drakes',
    'dragon','dragons','zombie dragon',
    'griffon','gryphon','griffin','griffons','gryphons','griffins',
    'hippogriff','hippogryph','pegasus','pegasi',
    'rhinox','rhino','rhinoceros',
    'manticore','manticores','chimera','chimeras',
    'stag','stags','deer','elk','elks','moose','lion','lions',
    'sabretooth','saber-tooth','sabertooth','sabercat','sabretusk','sabertusk',
    'raptor','raptors','velociraptor',
    'zebra','zebras','camel','camels','dromedary','ram','rams','goat','goats',
    'elephant','elephants','mammoth','mammoths',
    'spider','spiders','giant spider',
    'scorpion','scorpions','giant scorpion',
    'serpent','serpents','snake','snakes','python','pythons',
    'lizard','lizards','giant lizard','cold one','cold ones',
    'eagle','giant eagle','unicorn','unicorns',
    'terrorgheist','terrorgheists',
    'beast',
    'runetusk','antlerguard',
    # Warhammer AoS / WHFB specific mounts and common fantasy mounts
    'demigryph','demigryphs',
    'gryph charger','gryph chargers','gryph-charger','gryph-chargers',
    'dracoline','dracolines',
    'dracoth','dracoths',
    'mournfang','mournfangs',
    'stonehorn','stonehorns',
    'thundertusk','thundertusks',
    'carnosaur','carnosaurs',
    'stegadon','stegadons',
    'terradon','terradons',
    'ripperdactyl','ripperdactyls',
    'fellbeast','fellbeasts',
    'roc','rocs',
    'hippocampus','hippocampi',
    'steed','steeds','warhorse','war horse','war-horse','nightmare','nightmares',
    'bull','bulls','yak','yaks'
}
HUMANOID_RIDER_KEYS: Set[str] = {
    'ghoul','vampire','zombie','skeleton','lich','wight','wraith','human','elf','dwarf','orc','goblin','hobgoblin','ogre','troll','halfling','gnome','tiefling','aasimar'
}
RIDER_ROLE_TOKENS: Set[str] = {
    'king','queen','prince','princess','duke','duchess','lord','lady','captain','knight','rider','champion','marshal','general','warlord','chieftain','archregent','regent','cardinal','archbishop'
}

# Primary keys that represent roles/classes rather than species/races
ROLE_SUBLINEAGE_KEYS: Set[str] = {
    'knight', 'barbarian'
}


def _has_any_token(text: str, tokens: Set[str]) -> bool:
    for t in tokens:
        if re.search(rf"\b{re.escape(t)}\b", text):
            return True
    return False


def _pre_on_segment(text: str) -> str:
    # Take substring before ' on ' if present
    m = re.split(r"\bon\b", text, maxsplit=1)
    if len(m) >= 2:
        return m[0].strip()
    return text

def _post_on_segment(text: str) -> str:
    m = re.split(r"\bon\b", text, maxsplit=1)
    if len(m) >= 2:
        return m[1].strip()
    return ""


def detect_rider_context(text: str) -> bool:
    # primary cues
    if re.search(r"\b(riding|mounted|cavalry|mount)\b", text):
        return True
    # Generic 'on' + known mount tokens
    if re.search(r"\bon\b", text) and _has_any_token(text, ANIMAL_MOUNT_KEYS):
        return True
    # 'X on Y' with rider cues before 'on' implies rider scenario even if Y is unknown to mount list
    if re.search(r"\bon\b", text):
        pre_on = _pre_on_segment(text)
        if _has_any_token(pre_on, HUMANOID_RIDER_KEYS) or _has_any_token(pre_on, RIDER_ROLE_TOKENS):
            return True
    # role + animal co-mention implies rider scenario
    if _has_any_token(text, RIDER_ROLE_TOKENS) and _has_any_token(text, ANIMAL_MOUNT_KEYS):
        return True
    return False


def _rider_preference_bonus(key: str, pre_on: str, leaf_txt: str) -> float:
    k = key.strip().lower()
    bonus = 0.0
    # Base preference: ghoul > vampire > lich > wight/wraith > skeleton > zombie
    if k == 'ghoul':
        bonus += 0.6
    elif k == 'vampire':
        bonus += 0.4
    elif k in ('lich',):
        bonus += 0.35
    elif k in ('wight','wraith'):
        bonus += 0.25
    elif k in ('skeleton',):
        bonus += 0.1
    elif k == 'zombie':
        bonus -= 0.2
    # Contextual boosts: name appears in rider segment or leaf folder/file
    if re.search(rf"\b{re.escape(k)}\b", pre_on):
        bonus += 0.4
    if re.search(rf"\b{re.escape(k)}\b", leaf_txt):
        bonus += 0.2
    return bonus


def text_for_variant(v: Variant) -> str:
    parts: List[str] = []
    try:
        if v.rel_path:
            parts.append(v.rel_path)
    except Exception:
        pass
    try:
        if v.filename:
            parts.append(v.filename)
    except Exception:
        pass
    try:
        eng = getattr(v, 'english_tokens', None) or []
        if isinstance(eng, list) and eng:
            parts.append(" ".join([str(t) for t in eng if isinstance(t, str)]))
    except Exception:
        pass
    try:
        for t in (v.raw_path_tokens or []):
            if isinstance(t, str):
                parts.append(t)
    except Exception:
        pass
    return norm_text(" ".join(parts))


def _path_segments(rel_path: Optional[str]) -> List[str]:
    if not rel_path:
        return []
    raw = re.split(r"[\\/]+", rel_path)
    segs: List[str] = []
    NOISE = {
        "stl", "stls", "supported stl", "unsupported", "presupported", "__macosx",
        "combined", "lychee", "lys", "one page rules", "opr", "campaign", "supported",
    }
    for s in raw:
        n = norm_text(s)
        if not n or n in NOISE:
            continue
        segs.append(n)
    return segs


MONTHS = {"january","february","march","april","may","june","july","august","september","october","november","december"}
COLLECTION_NOISE = {"campaign","supported","support","stl","stls","lys","presupported","unsupported","release","releases","bundle","collection","set"}


def _is_collection_like(seg: str) -> bool:
    s = seg.strip().lower()
    if not s:
        return False
    if s in MONTHS or s in COLLECTION_NOISE:
        return True
    # Year markers (e.g., 2021, 2025-09)
    if re.search(r"\b(19|20)\d{2}\b", s):
        return True
    if re.search(r"\b(19|20)\d{2}[-_\s]?\d{1,2}\b", s):
        return True
    return False


def get_leaf_context_parts(v: Variant) -> Tuple[List[str], str]:
    segs: List[str] = []
    try:
        all_segs = _path_segments(getattr(v, 'rel_path', None))
    except Exception:
        all_segs = []
    # Take up to two non-collection-like leaf segments as local context
    for s in reversed(all_segs):
        if not _is_collection_like(s):
            segs.append(s)
            if len(segs) >= 2:
                break
    filename_txt = ""
    try:
        if v.filename:
            filename_txt = norm_text(v.filename)
    except Exception:
        pass
    return segs, filename_txt


def leaf_context_text(v: Variant) -> str:
    segs, filename_txt = get_leaf_context_parts(v)
    parts: List[str] = []
    parts.extend(segs)
    if filename_txt:
        parts.append(filename_txt)
    return norm_text(" ".join(parts))


def leaf_local_match(v: Variant, phrase: str) -> bool:
    # True if phrase appears in filename or last non-collection-like leaf segment
    try:
        fname = norm_text(v.filename) if getattr(v, 'filename', None) else ''
    except Exception:
        fname = ''
    if fname and _phrase_match(fname, phrase):
        return True
    try:
        segs = _path_segments(getattr(v, 'rel_path', None))
    except Exception:
        segs = []
    for s in reversed(segs):
        if _is_collection_like(s):
            continue
        if _phrase_match(s, phrase):
            return True
        break
    return False





def _is_local_strong(phrase: str, v: Variant) -> bool:
    segs, filename_txt = get_leaf_context_parts(v)
    # Strong if present in filename
    if phrase and re.search(rf"\b{re.escape(phrase)}\b", filename_txt):
        return True
    # Strong if present in a non-equal leaf segment (e.g., 'goblin archers'), not if the segment is exactly 'goblin'
    for s in segs:
        if not phrase:
            continue
        if s == phrase:
            continue
        if re.search(rf"\b{re.escape(phrase)}\b", s):
            return True
    return False


@dataclass
class Candidate:
    family_key: str
    primary_key: Optional[str]
    family_name: Optional[str]
    name: str
    score: float
    basis: str  # e.g., 'sublineage_strong', 'family_strong', 'weak_consensus'


def build_lineage_index(session) -> Tuple[
    Dict[str, List[Tuple[str, Optional[str], str]]],  # strong_idx: phrase -> list[(family, primary, 'strong')]
    Dict[str, List[Tuple[str, Optional[str], str]]],  # weak_idx
    Dict[Tuple[str, Optional[str]], Dict[str, List[str]]],  # locale_aliases map per family (primary ignored)
    Dict[Tuple[str, Optional[str]], List[str]],  # excludes per row (union family+sub)
    Dict[Tuple[str, Optional[str]], Tuple[str, str]],  # names per row (family_name, name)
    Dict[str, List[str]],  # context_tags per family_key
]:
    rows: List[Lineage] = session.query(Lineage).all()
    strong_idx: Dict[str, List[Tuple[str, Optional[str], str]]] = {}
    weak_idx: Dict[str, List[Tuple[str, Optional[str], str]]] = {}
    locale_map: Dict[Tuple[str, Optional[str]], Dict[str, List[str]]] = {}
    excludes_map: Dict[Tuple[str, Optional[str]], List[str]] = {}
    names: Dict[Tuple[str, Optional[str]], Tuple[str, str]] = {}
    family_context: Dict[str, List[str]] = {}

    # Build family-level rows first to propagate context/excludes
    families: Dict[str, Lineage] = {}
    for r in rows:
        if r.primary_key is None:
            families[r.family_key] = r

    for r in rows:
        key = (r.family_key, r.primary_key)
        fam_row = families.get(r.family_key)
        names[key] = (getattr(r, 'family_name', None), getattr(r, 'name', r.primary_key or r.family_key))
        # Context: saved per family
        if r.primary_key is None:
            family_context[r.family_key] = list(getattr(r, 'context_tags', []) or [])

        # Excludes: union family excludes + sub excludes
        ex: List[str] = []
        for src in (fam_row, r):
            try:
                for t in (getattr(src, 'excludes', []) or []):
                    if isinstance(t, str) and t:
                        ex.append(t)
            except Exception:
                pass
        excludes_map[key] = sorted({norm_text(e) for e in ex if e})

        # Locale aliases: only family level defined in YAML commonly
        loc_aliases = {}
        try:
            if r.primary_key is None:
                for loc, arr in (getattr(r, 'locale_aliases', {}) or {}).items():
                    vals = []
                    for a in (arr or []):
                        if isinstance(a, str) and a:
                            vals.append(norm_text(a))
                    if vals:
                        loc_aliases[loc] = vals
        except Exception:
            pass
        if loc_aliases:
            locale_map[key] = loc_aliases

        # Aliases
        strong_aliases = []
        weak_aliases = []
        # include display name as strong alias by default
        try:
            if isinstance(r.name, str) and r.name:
                strong_aliases.append(r.name)
        except Exception:
            pass
        for a in (getattr(r, 'aliases_strong', []) or []):
            if isinstance(a, str) and a:
                strong_aliases.append(a)
        for a in (getattr(r, 'aliases_weak', []) or []):
            if isinstance(a, str) and a:
                weak_aliases.append(a)
        # add canonical family key/primary key tokens as weak signals (snake to space)
        try:
            strong_aliases.append((r.primary_key or r.family_key).replace('_', ' '))
        except Exception:
            pass

        strong_aliases = sorted({norm_text(x) for x in strong_aliases if x})
        weak_aliases = sorted({norm_text(x) for x in weak_aliases if x})

        for p in strong_aliases:
            strong_idx.setdefault(p, []).append((r.family_key, r.primary_key, 'strong'))
        for p in weak_aliases:
            weak_idx.setdefault(p, []).append((r.family_key, r.primary_key, 'weak'))

    return strong_idx, weak_idx, locale_map, excludes_map, names, family_context


def contains_any(text: str, phrases: List[str]) -> bool:
    for p in phrases:
        if not p:
            continue
        if re.search(rf"\b{re.escape(p)}\b", text):
            return True
    return False


def _has_family_context(text: str, fam: str, names: Dict[Tuple[str, Optional[str]], Tuple[str, str]]) -> bool:
    # Tokens that imply explicit family/race context: family key and display name
    cues: List[str] = []
    fam_key = (fam or '').replace('_', ' ').strip()
    if fam_key:
        cues.append(fam_key)
    try:
        fam_name = (names.get((fam, None), (None, None))[1] or '')
        if fam_name:
            cues.append(fam_name)
    except Exception:
        pass
    for cue in cues:
        if cue and re.search(rf"\b{re.escape(cue)}\b", text):
            return True
    # Special-case: common human faction cues
    if fam == 'human':
        for cue in ['human','humans','man','men','woman','women','freeguild','free guild','cities of sigmar','city of sigmar','sigmar']:
            if re.search(rf"\b{re.escape(cue)}\b", text):
                return True
    return False


def match_lineage_for_variant(
    v: Variant,
    text_norm: str,
    strong_idx,
    weak_idx,
    locale_map,
    excludes_map,
    names,
    family_context,
) -> Tuple[Optional[Candidate], List[Candidate]]:
    # Gate by context: current YAML is fantasy; skip explicit w40k/heresy by default
    sys_key = (getattr(v, 'game_system', None) or '').lower().strip()
    if sys_key in {'w40k', 'heresy'}:
        return None, []

    # Gather hits
    hits: Dict[Tuple[str, Optional[str]], Dict[str, int]] = {}
    leaf_txt = leaf_context_text(v)
    # strong English/base
    for phrase, items in strong_idx.items():
        if not phrase:
            continue
        if _phrase_match(text_norm, phrase):
            for fam, pri, _ in items:
                bucket = 'strong' if _is_local_strong(phrase, v) else 'weak'
                # Demote role-based sublineages unless explicit family context exists
                if pri and pri in ROLE_SUBLINEAGE_KEYS and bucket == 'strong':
                    if not _has_family_context(text_norm, fam, names):
                        bucket = 'weak'
                rec = hits.setdefault((fam, pri), {'strong': 0, 'weak': 0, 'weak_local': 0})
                rec[bucket] += 1
                if bucket == 'weak' and leaf_local_match(v, phrase):
                    rec['weak_local'] += 1
    # locale-aware (family level only)
    tok_loc = (getattr(v, 'token_locale', None) or '').strip().lower()
    if tok_loc:
        for (fam, pri), locs in locale_map.items():
            if pri is not None:
                continue
            arr = locs.get(tok_loc) or []
            for phrase in arr:
                if _phrase_match(text_norm, phrase):
                    bucket = 'strong' if _is_local_strong(phrase, v) else 'weak'
                    rec = hits.setdefault((fam, None), {'strong': 0, 'weak': 0, 'weak_local': 0})
                    rec[bucket] += 1
                    if bucket == 'weak' and leaf_local_match(v, phrase):
                        rec['weak_local'] += 1

    # weak
    for phrase, items in weak_idx.items():
        if not phrase:
            continue
        if _phrase_match(text_norm, phrase):
            for fam, pri, _ in items:
                rec = hits.setdefault((fam, pri), {'strong': 0, 'weak': 0, 'weak_local': 0})
                rec['weak'] += 1
                if leaf_local_match(v, phrase):
                    rec['weak_local'] += 1

    if not hits:
        return None, []

    # Apply excludes and context filters
    filtered: Dict[Tuple[str, Optional[str]], Dict[str, int]] = {}
    for key, cnt in hits.items():
        fam, pri = key
        ex = excludes_map.get((fam, pri)) or []
        # also union family-level excludes when matching a sublineage
        ex_fam = excludes_map.get((fam, None)) or []
        ex_all = sorted(set(ex) | set(ex_fam))
        if ex_all and contains_any(text_norm, ex_all):
            continue
        # context tag 'fantasy' is satisfied by default; keep
        filtered[key] = cnt

    if not filtered:
        return None, []

    # Score: strong=2.5, weak=1.0; slight bonus for sublineage specificity
    cands: List[Candidate] = []
    for (fam, pri), cnt in filtered.items():
        s = 2.5 * cnt.get('strong', 0) + 1.0 * cnt.get('weak', 0)
        if pri is not None:
            s += 0.75
        fam_name, nm = names.get((fam, pri), (None, pri or fam))
        # Basis
        if cnt.get('strong', 0) > 0 and pri is not None:
            basis = 'sublineage_strong'
        elif cnt.get('strong', 0) > 0:
            basis = 'family_strong'
        else:
            basis = 'weak_consensus'
        cands.append(Candidate(fam, pri, fam_name, nm, s, basis))

    # Rider-over-mount bias: if riding context detected, nudge scores
    if cands and detect_rider_context(text_norm):
        pre_on = _pre_on_segment(text_norm)
        leaf_txt = leaf_context_text(v)
        for i, c in enumerate(cands):
            key = (c.primary_key or c.family_key or '').strip().lower()
            rider_bonus = 0.0
            mount_penalty = 0.0
            # Stronger bias if rider tokens appear before 'on'
            if _has_any_token(pre_on, HUMANOID_RIDER_KEYS) or _has_any_token(pre_on, RIDER_ROLE_TOKENS):
                rider_bonus = 1.25
                mount_penalty = 1.0
            else:
                rider_bonus = 0.75
                mount_penalty = 0.75
            if key in HUMANOID_RIDER_KEYS:
                # Slightly stronger preference for riders in mounted contexts
                cands[i].score += (rider_bonus + 0.25) + _rider_preference_bonus(key, pre_on, leaf_txt)
            elif key in ANIMAL_MOUNT_KEYS:
                # Slightly stronger penalty for mounts in mounted contexts
                cands[i].score -= (mount_penalty + 0.25)

        # Rider-first heuristic: In an "X on Y" pattern with rider cues before 'on',
        # prefer the best humanoid candidate X even if the mount Y is a strong match or not listed.
        if _has_any_token(pre_on, HUMANOID_RIDER_KEYS) or _has_any_token(pre_on, RIDER_ROLE_TOKENS):
            rider_cands = []
            for c in cands:
                key = (c.primary_key or c.family_key or '').strip().lower()
                if key not in HUMANOID_RIDER_KEYS:
                    continue
                names_to_probe = [key]
                try:
                    if c.name:
                        names_to_probe.append(norm_text(c.name))
                except Exception:
                    pass
                try:
                    if c.family_name:
                        names_to_probe.append(norm_text(c.family_name))
                except Exception:
                    pass
                if any(_phrase_match(pre_on, nm) for nm in names_to_probe if nm):
                    rider_cands.append(c)
            # If no explicit name match before 'on', but rider cues exist, still prefer best humanoid
            if not rider_cands:
                rider_cands = [c for c in cands if ((c.primary_key or '').lower() in HUMANOID_RIDER_KEYS) or ((c.family_key or '').lower() in HUMANOID_RIDER_KEYS)]
            if rider_cands:
                rider_cands.sort(key=lambda c: c.score, reverse=True)
                rider_pick = rider_cands[0]
                alt = [c for c in cands if c is not rider_pick][:4]
                return rider_pick, alt

    # Prefer highest score; require min acceptance: any strong OR sum weak >= 2 (per family or sublineage)
    cands.sort(key=lambda c: c.score, reverse=True)
    top = cands[0]
    # Aggregate weak hits by family
    fam_weak_totals: Dict[str, int] = {}
    for (fam, pri), cnt in filtered.items():
        fam_weak_totals[fam] = fam_weak_totals.get(fam, 0) + cnt.get('weak', 0)

    accept = False
    if any(filtered[(top.family_key, top.primary_key)].get('strong', 0) > 0 for _ in [0]):
        accept = True
    else:
        # top has no strong; require >=2 weak for the same family and at least 1 leaf-local weak,
        # and no conflicting family with >=2 weak
        if top.primary_key is None:
            if fam_weak_totals.get(top.family_key, 0) >= 2 and filtered[(top.family_key, top.primary_key)].get('weak_local', 0) >= 1:
                # ensure no other family has comparable weak sum
                rivals = [w for f, w in fam_weak_totals.items() if f != top.family_key and w >= 2]
                accept = len(rivals) == 0
        else:
            # sublineage weak-only: require >=2 weak on that sublineage and at least one local weak
            if filtered[(top.family_key, top.primary_key)].get('weak', 0) >= 2 and filtered[(top.family_key, top.primary_key)].get('weak_local', 0) >= 1:
                # also require no other sublineage with >=2 weak from a different family
                others = [cnt for (fam, pri), cnt in filtered.items() if fam != top.family_key and cnt.get('weak', 0) >= 2]
                accept = len(others) == 0

    # Rider-preference override: prefer rider if competitive in mounted contexts
    chosen: Optional[Candidate] = None
    if not accept and detect_rider_context(text_norm):
        pre_on = _pre_on_segment(text_norm)
        leaf_txt = leaf_context_text(v)
        rider_cands = [c for c in cands if ((c.primary_key or '').lower() in HUMANOID_RIDER_KEYS) or ((c.family_key or '').lower() in HUMANOID_RIDER_KEYS)]
        if rider_cands and (_has_any_token(pre_on, HUMANOID_RIDER_KEYS) or _has_any_token(pre_on, RIDER_ROLE_TOKENS)):
            rider_cands.sort(key=lambda c: c.score, reverse=True)
            rider_top = rider_cands[0]
            # Apply a slight edge if the preferred rider (e.g., ghoul) is present in pre_on/leaf
            rider_edge = _rider_preference_bonus((rider_top.primary_key or rider_top.family_key or ''), pre_on, leaf_txt)
            threshold = 0.75 - min(0.35, rider_edge)  # make easier to win when ghoul is evident
            if rider_top.score >= 2.0 and rider_top.score >= (top.score - threshold):
                chosen = rider_top
                accept = True

    if accept:
        primary = chosen or top
        alt = [c for c in cands if c is not primary][:4]
        return primary, alt
    # Local context undead vs ratfolk tiebreaker: prefer Undead when leaf hints say 'tomb' etc.
    leaf_txt = leaf_context_text(v)
    undead_hint = bool(re.search(r"(tomb|necropolis|crypt|grave|wight|skeleton|zombie|ghoul|mummy|tombshade)", leaf_txt))
    rat_hint = bool(re.search(r"\b(ratkin|ratmen|ratfolk|skaven|ratogre|rodent|vermin)\b", leaf_txt))
    if undead_hint and not rat_hint and cands:
        # find best Undead candidate
        undead_cands = [c for c in cands if c.family_key == 'undead']
        if undead_cands:
            undead_cands.sort(key=lambda c: c.score, reverse=True)
            undead_top = undead_cands[0]
            # within 0.5 of top is good enough given strong local hint
            if undead_top.score >= (cands[0].score - 0.5):
                return undead_top, [c for c in cands if c is not undead_top][:4]
    return None, cands[:5]


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Match Variants to canonical Lineages (dry-run by default)")
    p.add_argument("--db-url", default=None, help="Override database URL")
    p.add_argument("--limit", type=int, default=0, help="Process at most N variants (0=all)")
    p.add_argument("--apply", action="store_true", help="Apply matches to Variant.lineage_* fields (default: dry-run)")
    p.add_argument("--overwrite", action="store_true", help="When applying, overwrite existing lineage fields")
    p.add_argument("--out", default=None, help="Write JSON report to this path (default: reports/match_lineages_YYYYMMDD_HHMMSS.json)")
    p.add_argument("--append-timestamp", action="store_true", help="Append timestamp before extension to avoid overwrites when using --out")
    p.add_argument("--include-unmatched", action="store_true", help="Include unmatched variants in the report")
    args = p.parse_args(argv)

    # Reconfigure DB if provided (avoids env var quoting issues on Windows)
    if args.db_url:
        try:
            reconfigure(args.db_url)
        except Exception:
            pass

    # Output path
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if args.out:
        base = Path(args.out)
        if args.append_timestamp:
            out_path = base.with_name(f"{base.stem}_{ts}{'_apply' if args.apply else ''}{base.suffix or '.json'}")
        else:
            out_path = base
    else:
        out_path = reports_dir / f"match_lineages_{ts}{'_apply' if args.apply else ''}.json"

    total = 0
    applied = 0
    matched_family = 0
    matched_primary = 0
    skipped_scifi = 0
    proposals: List[Dict[str, Any]] = []

    with get_session() as session:
        strong_idx, weak_idx, locale_map, excludes_map, names, family_context = build_lineage_index(session)

        q = session.query(Variant)
        if args.limit and args.limit > 0:
            q = q.limit(args.limit)
        variants = q.all()
        for v in variants:
            total += 1
            sys_key = (getattr(v, 'game_system', None) or '').lower().strip()
            if sys_key in {'w40k', 'heresy'}:
                skipped_scifi += 1
                if args.include_unmatched:
                    proposals.append({
                        "variant_id": v.id,
                        "rel_path": v.rel_path,
                        "reason": "skipped_scifi",
                    })
                continue

            v_text = text_for_variant(v)
            accepted, alternates = match_lineage_for_variant(
                v, v_text, strong_idx, weak_idx, locale_map, excludes_map, names, family_context
            )

            entry: Dict[str, Any] = {
                "variant_id": v.id,
                "rel_path": v.rel_path,
                "filename": v.filename,
                "accepted": None,
                "alternates": [
                    {
                        "family_key": a.family_key,
                        "primary_key": a.primary_key,
                        "family_name": a.family_name,
                        "name": a.name,
                        "score": a.score,
                        "basis": a.basis,
                    } for a in alternates
                ],
            }

            if accepted:
                entry["accepted"] = {
                    "family_key": accepted.family_key,
                    "primary_key": accepted.primary_key,
                    "family_name": accepted.family_name,
                    "name": accepted.name,
                    "score": accepted.score,
                    "basis": accepted.basis,
                }
                matched_family += 1
                if accepted.primary_key:
                    matched_primary += 1
                if args.apply:
                    try:
                        if args.overwrite or not getattr(v, 'lineage_family', None):
                            v.lineage_family = accepted.family_key
                        if accepted.primary_key and (args.overwrite or not getattr(v, 'lineage_primary', None)):
                            v.lineage_primary = accepted.primary_key
                        # store the display name tokens as lineage_aliases for convenience
                        la = []
                        if accepted.family_name:
                            la.append(accepted.family_name)
                        if accepted.name and accepted.name != accepted.family_name:
                            la.append(accepted.name)
                        if la:
                            try:
                                if args.overwrite or not getattr(v, 'lineage_aliases', None):
                                    v.lineage_aliases = la
                            except Exception:
                                pass
                        # Populate mount_lineages for mounted contexts (extract from post-'on' segment)
                        try:
                            if detect_rider_context(v_text):
                                post_on = _post_on_segment(v_text)
                                mount_hits: Dict[Tuple[str, Optional[str]], Dict[str, int]] = {}
                                # Check strong aliases for mounts
                                for phrase, items in strong_idx.items():
                                    if not phrase:
                                        continue
                                    if _phrase_match(post_on, phrase):
                                        for fam, pri, bucket in items:
                                            key = (fam, pri)
                                            rec = mount_hits.setdefault(key, {'strong': 0, 'weak': 0})
                                            rec['strong'] += 1
                                # Check weak aliases for mounts
                                for phrase, items in weak_idx.items():
                                    if not phrase:
                                        continue
                                    if _phrase_match(post_on, phrase):
                                        for fam, pri, bucket in items:
                                            key = (fam, pri)
                                            rec = mount_hits.setdefault(key, {'strong': 0, 'weak': 0})
                                            rec['weak'] += 1
                                # Filter to animal mounts
                                mounts: List[Dict[str, Optional[str]]] = []
                                for (fam, pri), cnt in mount_hits.items():
                                    nm = (pri or fam or '').strip().lower()
                                    if nm in ANIMAL_MOUNT_KEYS:
                                        mounts.append({
                                            'family_key': fam,
                                            'primary_key': pri,
                                            'name': names.get((fam, pri), (None, pri or fam))[1],
                                            'basis': 'strong' if cnt.get('strong', 0) > 0 else 'weak'
                                        })
                                # Also capture literal mount tokens in post_on (union with lineage-based)
                                literals = []
                                for mk in sorted(ANIMAL_MOUNT_KEYS, key=len, reverse=True):
                                    if _phrase_match(post_on, mk):
                                        literals.append({'family_key': None, 'primary_key': None, 'name': mk, 'basis': 'literal'})
                                if literals:
                                    mounts = (mounts or []) + literals
                                if mounts:
                                    # If any canonical mount(s) detected, drop literal-only entries
                                    try:
                                        if any((m.get('family_key') is not None) for m in mounts):
                                            mounts = [m for m in mounts if m.get('family_key') is not None]
                                    except Exception:
                                        pass
                                    # Dedupe by normalized name; prefer canonical (with family_key) over literal
                                    dedup: Dict[str, Dict[str, Optional[str]]] = {}
                                    for m in mounts:
                                        nm = norm_text(str(m.get('name') or ''))
                                        if not nm:
                                            continue
                                        prev = dedup.get(nm)
                                        if prev is None:
                                            dedup[nm] = m
                                        else:
                                            # If previous is literal and current is canonical, replace
                                            if (prev.get('family_key') is None) and (m.get('family_key') is not None):
                                                dedup[nm] = m
                                    v.mount_lineages = list(dedup.values())
                        except Exception:
                            pass
                        v.lineage_confidence = 'high' if accepted.basis.endswith('strong') else 'medium'
                        applied += 1
                    except Exception:
                        pass
            else:
                if args.include_unmatched:
                    entry["reason"] = "no_match"
            proposals.append(entry)

        if args.apply:
            session.commit()

    with out_path.open("w", encoding="utf-8") as f:
        json.dump({
            "ts": datetime.utcnow().isoformat() + "Z",
            "apply": args.apply,
            "total_variants": total,
            "matched_family": matched_family,
            "matched_primary": matched_primary,
            "skipped_scifi": skipped_scifi,
            "proposals": proposals,
        }, f, ensure_ascii=False, indent=2)

    print(f"Report written: {out_path}")
    if args.apply:
        print(f"Applied lineage matches: {applied}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
