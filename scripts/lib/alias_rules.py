from __future__ import annotations

import re
from typing import Dict, List, Optional

# Ambiguous aliases that require supporting franchise evidence
# 'ivy' collides between DC's Poison Ivy and Soulcalibur's Ivy Valentine
# Extend with generic titles/vocations that appear frequently in folder names
# and should never match a character on their own.
_GENERIC_TITLE_TOKENS = {
    # roles / vocations
    "priestess", "priest", "warrior", "knight", "mage", "wizard", "witch",
    "sorceress", "sorcerer", "monk", "druid", "paladin", "barbarian",
    "assassin", "archer", "ranger", "fighter", "cleric", "shaman",
    "necromancer", "acolyte", "bishop",
    # military/common
    "guard", "soldier", "captain", "commander", "general",
    # nobility/titles
    "queen", "king", "princess", "prince", "empress", "emperor",
    "lord", "lady",
    # super generic descriptors
    "hero", "heroine",
}

AMBIGUOUS_ALIASES = {"angel", "sakura", "ivy"} | _GENERIC_TITLE_TOKENS


def is_short_or_numeric(tok: str) -> bool:
    """Return True for very short or alphanumeric codes like '2b', '9s', 'a2', or pure digits.

    Mirrors the logic used historically in franchise/character matching to avoid
    accidental matches from codes or short tokens unless there's supporting context.
    """
    t = (tok or "").strip().lower()
    if not t:
        return False
    if t.isdigit():
        return True
    if len(t) <= 2:
        return True
    return bool(re.fullmatch(r"[a-z]\d|\d[a-z]", t))


def is_valid_franchise_alias(tok: str, fam: Dict[str, str], f_tokens: Dict[str, Dict[str, set]]) -> bool:
    """Return True if token is a valid alias for a franchise (and not an explicit stop token)."""
    if tok not in fam:
        return False
    frk = fam[tok]
    if tok in (f_tokens.get(frk, {}).get('stop', set()) or set()):
        return False
    return True


def has_supporting_franchise_tokens(
    fr_key: str,
    token_list: List[str],
    fam: Dict[str, str],
    f_tokens: Dict[str, Dict[str, set]],
    exclude_token: Optional[str] = None,
) -> bool:
    """True if there is independent evidence of this franchise in tokens.

    Evidence: any other token (not equal to exclude_token) is either a strong/weak
    signal of the franchise or an alias that maps to this franchise and is not a stop token.
    """
    sigs = (f_tokens.get(fr_key, {}).get('strong', set()) or set()) | (
        f_tokens.get(fr_key, {}).get('weak', set()) or set()
    )
    for tt in token_list:
        if exclude_token and tt == exclude_token:
            continue
        if tt in sigs:
            return True
        if tt in fam and fam[tt] == fr_key and tt not in (f_tokens.get(fr_key, {}).get('stop', set()) or set()):
            return True
    return False


def is_valid_character_alias(
    tok: str,
    token_list: List[str],
    fam: Optional[Dict[str, str]] = None,
    f_tokens: Optional[Dict[str, Dict[str, set]]] = None,
    ambiguous_aliases: Optional[set] = None,
) -> bool:
    """Apply standard gating for character aliases.

    - Reject short/numeric tokens (e.g., '002', '2b') unless there is supporting franchise evidence.
    - Reject ambiguous aliases (e.g., 'angel') unless there is supporting franchise evidence.

    If franchise maps are not provided, falls back to allowing only non-short/non-ambiguous aliases.
    """
    ambiguous_aliases = ambiguous_aliases or AMBIGUOUS_ALIASES
    if is_short_or_numeric(tok):
        if fam and f_tokens:
            # Require any supporting franchise evidence for any franchise
            has_support = any(
                has_supporting_franchise_tokens(k, token_list, fam, f_tokens, exclude_token=tok)
                for k in set(fam.values())
            )
            if not has_support:
                return False
        else:
            return False
    if tok in ambiguous_aliases:
        if fam and f_tokens:
            has_support = any(
                has_supporting_franchise_tokens(k, token_list, fam, f_tokens, exclude_token=tok)
                for k in set(fam.values())
            )
            if not has_support:
                return False
        else:
            return False
    return True
