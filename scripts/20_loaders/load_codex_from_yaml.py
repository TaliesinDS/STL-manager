from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ruamel.yaml import YAML
from sqlalchemy import select
import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.models import Base, GameSystem, Faction, Unit, UnitAlias, Part, PartAlias
from sqlalchemy.orm import Session
from sqlalchemy import create_engine


def ensure_tables(db_url: str) -> None:
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)


def upsert_system(session: Session, key: str, name: str) -> GameSystem:
    sys_obj = session.execute(select(GameSystem).where(GameSystem.key == key)).scalar_one_or_none()
    if sys_obj is None:
        sys_obj = GameSystem(key=key, name=name)
        session.add(sys_obj)
        session.flush()
    else:
        if sys_obj.name != name:
            sys_obj.name = name
    return sys_obj


def upsert_faction(
    session: Session,
    system: GameSystem,
    key: str,
    name: str,
    parent: Optional[Faction] = None,
    full_path: Optional[List[str]] = None,
    aliases: Optional[List[str]] = None,
) -> Faction:
    stmt = select(Faction).where(Faction.system_id == system.id, Faction.key == key)
    f = session.execute(stmt).scalar_one_or_none()
    if f is None:
        f = Faction(
            system_id=system.id,
            key=key,
            name=name,
            parent_id=parent.id if parent else None,
            full_path=full_path or [],
            aliases=aliases or [],
        )
        session.add(f)
        session.flush()
    else:
        f.name = name
        f.parent_id = parent.id if parent else None
        f.full_path = full_path or f.full_path or []
        if aliases:
            existing = set(f.aliases or [])
            for a in aliases:
                if a not in existing:
                    existing.add(a)
            f.aliases = sorted(existing)
    return f


def upsert_unit(
    session: Session,
    system: GameSystem,
    faction: Optional[Faction],
    key: str,
    name: str,
    role: Optional[str],
    unique_flag: bool,
    aliases: List[str],
    legal_in_editions: List[str],
    available_to: Dict[str, Any],
    base_profile_key: Optional[str],
    source_file: str,
    source_anchor: Optional[str],
    category: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    raw_data: Optional[Dict[str, Any]] = None,
) -> Unit:
    stmt = select(Unit).where(Unit.system_id == system.id, Unit.key == key)
    u = session.execute(stmt).scalar_one_or_none()
    if u is None:
        u = Unit(
            system_id=system.id,
            faction_id=faction.id if faction else None,
            key=key,
            name=name,
            role=role,
            unique_flag=unique_flag,
            category=category,
            aliases=aliases,
            legal_in_editions=legal_in_editions,
            available_to=available_to,
            base_profile_key=base_profile_key,
            attributes=attributes or {},
            raw_data=raw_data or {},
            source_file=source_file,
            source_anchor=source_anchor,
        )
        session.add(u)
        session.flush()
    else:
        u.faction_id = faction.id if faction else None
        u.name = name
        u.role = role
        u.unique_flag = unique_flag
        u.category = category
        u.aliases = aliases
        u.legal_in_editions = legal_in_editions
        u.available_to = available_to
        u.base_profile_key = base_profile_key
        u.attributes = attributes or {}
        u.raw_data = raw_data or {}
        u.source_file = source_file
        u.source_anchor = source_anchor
    # refresh unit_alias rows
    session.query(UnitAlias).filter(UnitAlias.unit_id == u.id).delete()
    for a in aliases:
        session.add(UnitAlias(unit_id=u.id, alias=a))
    return u


def load_yaml(path: Path) -> Any:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.allow_duplicate_keys = True
    with path.open("r", encoding="utf-8") as f:
        return yaml.load(f)


def infer_system_from_filename(path: Path) -> Tuple[str, str]:
    name = path.name
    if "w40k" in name:
        return ("w40k", "Warhammer 40,000")
    if "aos" in name:
        return ("aos", "Age of Sigmar")
    if "horus_heresy" in name or "heresy" in name:
        return ("heresy", "Horus Heresy")
    if "oldworld" in name or "old_world" in name:
        return ("old_world", "Warhammer: The Old World")
    return ("w40k", "Warhammer 40,000")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load codex units and parts from YAML into DB")
    parser.add_argument("--file", required=True, help="Path to YAML file (codex_units_*.yaml, wargear_w40k.yaml, bodies_w40k.yaml)")
    parser.add_argument("--system", choices=["w40k", "aos", "heresy", "old_world"], help="Override inferred system key")
    parser.add_argument("--commit", action="store_true", help="Commit changes; otherwise dry-run")
    parser.add_argument("--db-url", help="SQLAlchemy DB URL, e.g., sqlite:///./data/stl_manager_v1.db")
    args = parser.parse_args()

    db_url = args.db_url or os.environ.get("STLMGR_DB_URL", "sqlite:///./data/stl_manager.db")
    os.environ["STLMGR_DB_URL"] = db_url
    from db.session import get_session
    ensure_tables(db_url)

    yaml_path = Path(args.file)
    data = load_yaml(yaml_path)

    sys_key, sys_name = infer_system_from_filename(yaml_path)
    if args.system:
        sys_key = args.system
        sys_name = {
            "w40k": "Warhammer 40,000",
            "aos": "Age of Sigmar",
            "heresy": "Horus Heresy",
            "old_world": "Warhammer: The Old World",
        }[sys_key]

    with get_session() as session:
        Base.metadata.create_all(session.get_bind())
        system = upsert_system(session, sys_key, sys_name)

        def upsert_part(
            system: GameSystem,
            faction: Optional[Faction],
            key: str,
            name: str,
            part_type: str,
            category: Optional[str],
            slot: Optional[str],
            slots: Optional[List[str]],
            aliases: List[str],
            legal_in_editions: List[str],
            legends_in_editions: List[str],
            available_to: List[str],
            attributes: Dict[str, Any],
            raw_data: Dict[str, Any],
            source_anchor: Optional[str],
        ) -> Part:
            stmt = select(Part).where(Part.system_id == system.id, Part.key == key)
            p = session.execute(stmt).scalar_one_or_none()
            if p is None:
                p = Part(
                    system_id=system.id,
                    faction_id=faction.id if faction else None,
                    key=key,
                    name=name,
                    part_type=part_type,
                    category=category,
                    slot=slot,
                    slots=slots or [],
                    aliases=aliases,
                    legal_in_editions=legal_in_editions,
                    legends_in_editions=legends_in_editions,
                    available_to=available_to,
                    attributes=attributes,
                    raw_data=raw_data,
                    source_file=str(yaml_path.as_posix()),
                    source_anchor=source_anchor,
                )
                session.add(p)
                session.flush()
            else:
                p.faction_id = faction.id if faction else None
                p.name = name
                p.part_type = part_type
                p.category = category
                p.slot = slot
                p.slots = slots or []
                p.aliases = aliases
                p.legal_in_editions = legal_in_editions
                p.legends_in_editions = legends_in_editions
                p.available_to = available_to
                p.attributes = attributes or {}
                p.raw_data = raw_data or {}
                p.source_file = str(yaml_path.as_posix())
                p.source_anchor = source_anchor
            session.query(PartAlias).filter(PartAlias.part_id == p.id).delete()
            for a in aliases:
                session.add(PartAlias(part_id=p.id, alias=a))
            return p

        is_parts_wargear = isinstance(data.get("wargear"), dict)
        is_parts_bodies = isinstance(data.get("bodies"), dict)

        if is_parts_wargear or is_parts_bodies:
            system = upsert_system(session, sys_key or "w40k", sys_name or "Warhammer 40,000")

            if is_parts_wargear:
                for key, node in data["wargear"].items():
                    name = node.get("name") or key.replace("_", " ").title()
                    category = node.get("category")
                    slot = node.get("slot")
                    slots = node.get("slots") or []
                    aliases = list(node.get("aliases", []) or [])
                    legal = list(node.get("legal_in_editions", []) or [])
                    legends = list(node.get("legends_in_editions", []) or [])
                    available_to = list(node.get("available_to", []) or [])
                    core_keys = {"name", "category", "slot", "slots", "aliases", "legal_in_editions", "legends_in_editions", "available_to"}
                    extra = {k: v for k, v in (node or {}).items() if k not in core_keys}
                    upsert_part(
                        system,
                        None,
                        key,
                        name,
                        part_type="wargear",
                        category=category,
                        slot=slot,
                        slots=slots,
                        aliases=aliases,
                        legal_in_editions=legal,
                        legends_in_editions=legends,
                        available_to=available_to,
                        attributes=extra,
                        raw_data=node,
                        source_anchor=f"wargear.{key}",
                    )

            if is_parts_bodies:
                for key, node in data["bodies"].items():
                    name = node.get("name") or key.replace("_", " ").title()
                    faction_key = node.get("faction")
                    faction = None
                    if faction_key:
                        faction = session.execute(
                            select(Faction).where(Faction.system_id == system.id, Faction.key == faction_key)
                        ).scalar_one_or_none()
                        if faction is None:
                            faction = upsert_faction(session, system, faction_key, faction_key.replace("_", " ").title())
                    body_class = node.get("class")
                    slots = list(node.get("slots", []) or [])
                    aliases = list(node.get("aliases", []) or [])
                    legal = list(node.get("legal_in_editions", []) or [])
                    legends = list(node.get("legends_in_editions", []) or [])
                    available_to = []
                    core_keys = {"name", "faction", "class", "slots", "aliases", "legal_in_editions", "legends_in_editions", "available_to", "notes"}
                    extra = {k: v for k, v in (node or {}).items() if k not in core_keys}
                    upsert_part(
                        system,
                        faction,
                        key,
                        name,
                        part_type="body",
                        category=body_class,
                        slot=None,
                        slots=slots,
                        aliases=aliases,
                        legal_in_editions=legal,
                        legends_in_editions=legends,
                        available_to=available_to,
                        attributes=extra,
                        raw_data=node,
                        source_anchor=f"bodies.{key}",
                    )

        else:
            units_root = data
            if isinstance(data.get("codex_units"), dict):
                sys_branch_map = {
                    "w40k": "warhammer_40k",
                    "aos": "age_of_sigmar",
                    "heresy": "horus_heresy",
                    "old_world": "old_world",
                }
                preferred_key = sys_branch_map.get(sys_key)
                branch = None
                if preferred_key and isinstance(data["codex_units"].get(preferred_key), dict):
                    branch = data["codex_units"][preferred_key]
                else:
                    branches = [v for v in data["codex_units"].values() if isinstance(v, dict)]
                    if len(branches) == 1:
                        branch = branches[0]
                if branch is not None:
                    units_root = branch

            factions_obj = units_root.get("factions") or {}

            def handle_units(
                faction_key: Optional[str],
                faction_name: Optional[str],
                units_obj: Dict[str, Any],
                source_anchor: Optional[str] = None,
                parent: Optional[Faction] = None,
                force_category: Optional[str] = None,
            ) -> None:
                faction: Optional[Faction] = None
                if faction_key and faction_name:
                    faction = upsert_faction(session, system, faction_key, faction_name, parent=parent)

                for unit_key, u_node in (units_obj or {}).items():
                    name = u_node.get("name") or unit_key.replace("_", " ").title()
                    role = u_node.get("role")
                    unique_flag = bool(u_node.get("unique", False))
                    aliases = list(u_node.get("aliases", []) or [])
                    legal = list(u_node.get("legal_in_editions", []) or [])
                    at_raw = u_node.get("available_to")
                    available_to = at_raw if at_raw is not None else {}
                    base_profile = u_node.get("base_profile") or u_node.get("base_profile_key")
                    category = force_category or u_node.get("category") or "unit"
                    core_keys = {"name", "role", "unique", "aliases", "legal_in_editions", "available_to", "base_profile", "base_profile_key", "category"}
                    extra_attrs: Dict[str, Any] = {k: v for k, v in (u_node or {}).items() if k not in core_keys}
                    upsert_unit(
                        session,
                        system,
                        faction,
                        unit_key,
                        name,
                        role,
                        unique_flag,
                        aliases,
                        legal,
                        available_to,
                        base_profile,
                        source_file=str(yaml_path.as_posix()),
                        source_anchor=source_anchor,
                        category=category,
                        attributes=extra_attrs,
                        raw_data=u_node,
                    )

            for f_key, f in factions_obj.items():
                f_name = f.get("name") or f_key.replace("_", " ").title()
                parent_top = upsert_faction(session, system, f_key, f_name)
                if isinstance(f.get("units"), dict):
                    handle_units(f_key, f_name, f.get("units"), source_anchor=f"factions.{f_key}.units")

                special_map = {
                    "endless_spells": "endless_spell",
                    "manifestations": "manifestation",
                    "invocations": "invocation",
                    "warscroll_terrain": "terrain",
                }
                for sect, cat in special_map.items():
                    if isinstance(f.get(sect), dict):
                        handle_units(
                            f_key,
                            f_name,
                            f.get(sect),
                            source_anchor=f"factions.{f_key}.{sect}",
                            force_category=cat,
                        )

                for subkey in ("subfactions", "chapters", "orders", "septs", "dynasties", "hives", "temples", "legions"):
                    if isinstance(f.get(subkey), dict):
                        for sf_key, sf in f[subkey].items():
                            sf_name = sf.get("name") or sf_key.replace("_", " ").title()
                            parent = upsert_faction(session, system, f_key, f_name)
                            subf = upsert_faction(session, system, sf_key, sf_name, parent=parent)
                            if isinstance(sf.get("units"), dict):
                                handle_units(
                                    sf_key,
                                    sf_name,
                                    sf.get("units"),
                                    source_anchor=f"factions.{f_key}.{subkey}.{sf_key}.units",
                                    parent=parent,
                                )

            top_units = units_root.get("units")
            if isinstance(top_units, dict):
                handle_units(None, None, top_units, source_anchor="units")

            if isinstance(units_root.get("grand_alliances"), dict):
                editions = []
                try:
                    editions = list((units_root.get("meta", {}) or {}).get("editions", []) or [])
                except Exception:
                    editions = []

                role_by_unit_type = {
                    "leaders": "leader",
                    "battleline": "battleline",
                    "infantry": "infantry",
                    "cavalry": "cavalry",
                    "monsters": "monster",
                    "behemoths": "behemoth",
                    "artillery": "artillery",
                    "chariots": "chariot",
                    "swarms": "swarm",
                }

                for ga_name, ga in units_root["grand_alliances"].items():
                    ga_key = str(ga_name).strip().lower()
                    ga_parent = upsert_faction(session, system, ga_key, ga_name)
                    factions_map = (ga or {}).get("factions") or {}
                    for fac_key, fac_node in factions_map.items():
                        fac_name = fac_node.get("display_name") or fac_key.replace("_", " ").title()
                        _fac = upsert_faction(session, system, fac_key, fac_name, parent=ga_parent)
                        unit_types = (fac_node or {}).get("unit_types") or {}
                        for utype, entries in unit_types.items():
                            norm: Dict[str, Any] = {}
                            if isinstance(entries, dict):
                                norm = entries
                            elif isinstance(entries, list):
                                for uid in entries:
                                    if not isinstance(uid, str):
                                        continue
                                    norm[uid] = {
                                        "name": uid.replace("_", " ").title(),
                                        "role": role_by_unit_type.get(utype),
                                        "legal_in_editions": editions,
                                        "available_to": [f"{ga_key}/{fac_key}"],
                                    }
                            if norm:
                                handle_units(
                                    fac_key,
                                    fac_name,
                                    norm,
                                    source_anchor=f"grand_alliances.{ga_name}.factions.{fac_key}.unit_types.{utype}",
                                    parent=ga_parent,
                                )

                        fac_special_map = {
                            "endless_spells": "endless_spell",
                            "manifestations": "manifestation",
                            "invocations": "invocation",
                            "warscroll_terrain": "terrain",
                        }
                        for sect, cat in fac_special_map.items():
                            val = fac_node.get(sect)
                            if isinstance(val, dict):
                                handle_units(
                                    fac_key,
                                    fac_name,
                                    val,
                                    source_anchor=f"grand_alliances.{ga_name}.factions.{fac_key}.{sect}",
                                    parent=ga_parent,
                                    force_category=cat,
                                )
                            elif isinstance(val, list):
                                conv: Dict[str, Any] = {}
                                for item in val:
                                    if isinstance(item, str):
                                        conv[item] = {"name": item.replace("_", " ").title()}
                                    elif isinstance(item, dict):
                                        kid = item.get("id") or item.get("key")
                                        if not kid:
                                            continue
                                        conv[kid] = dict(item)
                                if conv:
                                    handle_units(
                                        fac_key,
                                        fac_name,
                                        conv,
                                        source_anchor=f"grand_alliances.{ga_name}.factions.{fac_key}.{sect}",
                                        parent=ga_parent,
                                        force_category=cat,
                                    )

            top_special_map = {
                "shared_endless_spells": "endless_spell",
                "regiments_of_renown": "regiment",
                "shared_manifestations": "manifestation",
                "shared_invocations": "invocation",
                "shared_terrain": "terrain",
            }
            for sect, cat in top_special_map.items():
                val = units_root.get(sect)
                if isinstance(val, dict):
                    handle_units(None, None, val, source_anchor=sect, force_category=cat)
                elif isinstance(val, list):
                    conv: Dict[str, Any] = {}
                    for item in val:
                        if isinstance(item, str):
                            conv[item] = {"name": item.replace("_", " ").title()}
                        elif isinstance(item, dict):
                            kid = item.get("id") or item.get("key")
                            if not kid:
                                continue
                            conv[kid] = dict(item)
                    if conv:
                        handle_units(None, None, conv, source_anchor=sect, force_category=cat)

        if args.commit:
            session.commit()
            print("Committed codex load.")
        else:
            session.rollback()
            print("Dry-run complete (no changes committed).")


if __name__ == "__main__":
    main()
