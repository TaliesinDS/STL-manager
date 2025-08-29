from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, Any, Optional

from sqlalchemy import create_engine, text


def db_counts(db_url: str, systems: list[str]) -> Dict[str, Dict[str, int]]:
    eng = create_engine(db_url, future=True)
    out: Dict[str, Dict[str, int]] = {}
    with eng.connect() as c:
        for skey in systems:
            unit_cnt = c.execute(
                text("SELECT COUNT(*) FROM unit WHERE system_id = (SELECT id FROM game_system WHERE key = :k)"), {"k": skey}
            ).scalar_one_or_none() or 0
            faction_cnt = c.execute(
                text("SELECT COUNT(*) FROM faction WHERE system_id = (SELECT id FROM game_system WHERE key = :k)"), {"k": skey}
            ).scalar_one_or_none() or 0
            unit_alias_cnt = c.execute(
                text(
                    """
                    SELECT COUNT(*) FROM unit_alias
                    WHERE unit_id IN (SELECT id FROM unit WHERE system_id = (SELECT id FROM game_system WHERE key = :k))
                    """
                ),
                {"k": skey},
            ).scalar_one_or_none() or 0
            part_cnt = c.execute(
                text("SELECT COUNT(*) FROM part WHERE system_id = (SELECT id FROM game_system WHERE key = :k)"), {"k": skey}
            ).scalar_one_or_none() or 0
            part_alias_cnt = c.execute(
                text(
                    """
                    SELECT COUNT(*) FROM part_alias
                    WHERE part_id IN (SELECT id FROM part WHERE system_id = (SELECT id FROM game_system WHERE key = :k))
                    """
                ),
                {"k": skey},
            ).scalar_one_or_none() or 0

            out[skey] = {
                "units": int(unit_cnt),
                "factions": int(faction_cnt),
                "unit_aliases": int(unit_alias_cnt),
                "parts": int(part_cnt),
                "part_aliases": int(part_alias_cnt),
            }
    return out


# ---------- YAML expected counts (approx) ----------
def _load_yaml(path: Path) -> Any:
    from ruamel.yaml import YAML  # lazy import

    y = YAML(typ="rt")
    y.preserve_quotes = True
    y.allow_duplicate_keys = True
    with path.open("r", encoding="utf-8") as f:
        return y.load(f)


def _count_entries(val: Any) -> int:
    if isinstance(val, dict):
        return sum(1 for k, v in val.items() if isinstance(v, (dict, str)))
    if isinstance(val, list):
        return len(val)
    return 0


def yaml_expected_counts(vocab_dir: Path) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {"w40k": {}, "aos": {}, "heresy": {}, "old_world": {}}

    # W40K units
    w40k_path = vocab_dir / "codex_units_w40k.yaml"
    if w40k_path.exists():
        data = _load_yaml(w40k_path)
        root = (data or {}).get("codex_units", {}).get("warhammer_40k", {})
        units = (root or {}).get("units", {})
        out["w40k"]["units_yaml"] = sum(1 for k, v in (units or {}).items() if isinstance(v, dict))
    # W40K parts (wargear + bodies)
    wg_path = vocab_dir / "wargear_w40k.yaml"
    if wg_path.exists():
        data = _load_yaml(wg_path)
        wargear = (data or {}).get("wargear", {})
        out["w40k"]["wargear_yaml"] = _count_entries(wargear)
    bodies_path = vocab_dir / "bodies_w40k.yaml"
    if bodies_path.exists():
        data = _load_yaml(bodies_path)
        bodies = (data or {}).get("bodies", {})
        out["w40k"]["bodies_yaml"] = _count_entries(bodies)

    # Heresy units
    hh_path = vocab_dir / "codex_units_horus_heresy.yaml"
    if hh_path.exists():
        data = _load_yaml(hh_path)
        root = (data or {}).get("codex_units", {}).get("warhammer_30k", {})
        units = (root or {}).get("units", {})
        out["heresy"]["units_yaml"] = sum(1 for k, v in (units or {}).items() if isinstance(v, dict))

    # AoS approx: grand alliances + specials
    aos_path = vocab_dir / "codex_units_aos.yaml"
    if aos_path.exists():
        data = _load_yaml(aos_path)
        root = (data or {}).get("codex_units", {}).get("age_of_sigmar", {})
        total = 0
        try:
            ga = (root or {}).get("grand_alliances", {})
            for ga_name, ga_node in (ga or {}).items():
                factions = (ga_node or {}).get("factions", {})
                for fac_key, fac_node in (factions or {}).items():
                    ut = (fac_node or {}).get("unit_types", {})
                    for utype, entries in (ut or {}).items():
                        if isinstance(entries, dict):
                            total += len(entries)
                        elif isinstance(entries, list):
                            total += len(entries)
                    # faction-level specials
                    for sect in ["endless_spells", "manifestations", "invocations", "warscroll_terrain"]:
                        total += _count_entries((fac_node or {}).get(sect))
            # top-level specials
            for sect in [
                "shared_endless_spells",
                "regiments_of_renown",
                "shared_manifestations",
                "shared_invocations",
                "shared_terrain",
            ]:
                total += _count_entries((root or {}).get(sect))
        except Exception:
            pass
        out["aos"]["units_yaml_approx"] = total

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Report Units/Parts counts by system from DB; optionally compare to YAML.")
    parser.add_argument("--db-url", help="SQLAlchemy DB URL; defaults to STLMGR_DB_URL or sqlite:///./data/stl_manager_v1.db")
    parser.add_argument("--systems", nargs="*", default=["w40k", "aos", "heresy", "old_world"], help="Systems to include (default: w40k aos heresy old_world)")
    parser.add_argument("--vocab-dir", default=str(Path(__file__).resolve().parents[1] / "vocab"), help="Path to vocab directory (for --yaml)")
    parser.add_argument("--yaml", action="store_true", help="Also compute expected counts from YAML (approx for AoS)")
    args = parser.parse_args()

    db_url = args.db_url or os.environ.get("STLMGR_DB_URL", "sqlite:///./data/stl_manager_v1.db")

    print(f"DB: {db_url}")
    db = db_counts(db_url, args.systems)
    print("\nCounts by system (DB):")
    for sk in args.systems:
        c = db.get(sk, {})
        print(
            f"  {sk}: units={c.get('units', 0)}, factions={c.get('factions', 0)}, unit_aliases={c.get('unit_aliases', 0)}, parts={c.get('parts', 0)}, part_aliases={c.get('part_aliases', 0)}"
        )

    if args.yaml:
        vocab_dir = Path(args.vocab_dir)
        exp = yaml_expected_counts(vocab_dir)
        print("\nYAML expected counts (approx for AoS):")
        for sk in args.systems:
            if sk not in exp:
                continue
            print(f"  {sk}: {exp[sk]}")


if __name__ == "__main__":
    main()
