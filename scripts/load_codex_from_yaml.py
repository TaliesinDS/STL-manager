from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ruamel.yaml import YAML
from sqlalchemy import select
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.models import Base, GameSystem, Faction, Unit, UnitAlias, Part, PartAlias
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
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


def upsert_faction(session: Session, system: GameSystem, key: str, name: str,
                   parent: Optional[Faction] = None, full_path: Optional[List[str]] = None,
                   aliases: Optional[List[str]] = None) -> Faction:
    stmt = select(Faction).where(Faction.system_id == system.id, Faction.key == key)
    f = session.execute(stmt).scalar_one_or_none()
    if f is None:
        f = Faction(system_id=system.id, key=key, name=name, parent_id=parent.id if parent else None,
                    full_path=full_path or [], aliases=aliases or [])
        session.add(f)
        session.flush()
    else:
        f.name = name
        f.parent_id = parent.id if parent else None
        f.full_path = full_path or f.full_path or []
        if aliases:
            # merge unique
            existing = set(f.aliases or [])
            for a in aliases:
                if a not in existing:
                    existing.add(a)
            f.aliases = sorted(existing)
    return f


def upsert_unit(session: Session, system: GameSystem, faction: Optional[Faction], key: str, name: str,
                role: Optional[str], unique_flag: bool, aliases: List[str], legal_in_editions: List[str],
                available_to: Dict[str, Any], base_profile_key: Optional[str], source_file: str,
                source_anchor: Optional[str], category: Optional[str] = None,
                attributes: Optional[Dict[str, Any]] = None, raw_data: Optional[Dict[str, Any]] = None) -> Unit:
    stmt = select(Unit).where(Unit.system_id == system.id, Unit.key == key)
    u = session.execute(stmt).scalar_one_or_none()
    if u is None:
        u = Unit(system_id=system.id, faction_id=faction.id if faction else None,
                 key=key, name=name, role=role, unique_flag=unique_flag,
                 category=category, aliases=aliases, legal_in_editions=legal_in_editions,
                 available_to=available_to, base_profile_key=base_profile_key,
                 attributes=attributes or {}, raw_data=raw_data or {}, source_file=source_file, source_anchor=source_anchor)
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
    # Use round-trip loader to support duplicate keys and preserve structure similar to authoring tools
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    # Allow duplicate keys; last wins
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
    # default fallback
    return ("w40k", "Warhammer 40,000")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load codex units and parts from YAML into DB")
    parser.add_argument("--file", required=True, help="Path to YAML file (codex_units_*.yaml, wargear_w40k.yaml, bodies_w40k.yaml)")
    parser.add_argument("--system", choices=["w40k","aos","heresy","old_world"], help="Override inferred system key")
    parser.add_argument("--commit", action="store_true", help="Commit changes; otherwise dry-run")
    parser.add_argument("--db-url", help="SQLAlchemy DB URL, e.g., sqlite:///./data/stl_manager_v1.db")
    args = parser.parse_args()

    db_url = args.db_url or os.environ.get("STLMGR_DB_URL", "sqlite:///./data/stl_manager.db")
    # Set env before importing session so engine binds to the chosen DB
    os.environ["STLMGR_DB_URL"] = db_url
    # Late import to respect DB URL
    from db.session import get_session
    ensure_tables(db_url)

    yaml_path = Path(args.file)
    data = load_yaml(yaml_path)

    # determine system (files without a system keyword default to 40k)
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
        # Ensure tables exist against the actual session engine as well (covers env/engine mismatches)
        Base.metadata.create_all(session.get_bind())
        system = upsert_system(session, sys_key, sys_name)

        def upsert_part(system: GameSystem, faction: Optional[Faction], key: str, name: str,
                        part_type: str, category: Optional[str], slot: Optional[str], slots: Optional[List[str]],
                        aliases: List[str], legal_in_editions: List[str], legends_in_editions: List[str],
                        available_to: List[str], attributes: Dict[str, Any], raw_data: Dict[str, Any],
                        source_anchor: Optional[str]) -> Part:
            stmt = select(Part).where(Part.system_id == system.id, Part.key == key)
            p = session.execute(stmt).scalar_one_or_none()
            if p is None:
                p = Part(system_id=system.id, faction_id=faction.id if faction else None,
                         key=key, name=name, part_type=part_type, category=category,
                         slot=slot, slots=slots or [], aliases=aliases,
                         legal_in_editions=legal_in_editions, legends_in_editions=legends_in_editions,
                         available_to=available_to, attributes=attributes, raw_data=raw_data,
                         source_file=str(yaml_path.as_posix()), source_anchor=source_anchor)
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

        # Detect which schema to ingest: codex units vs parts
        is_parts_wargear = isinstance(data.get("wargear"), dict)
        is_parts_bodies = isinstance(data.get("bodies"), dict)

        if is_parts_wargear or is_parts_bodies:
            # Parts ingestion (40K only by default)
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
                    core_keys = {"name","category","slot","slots","aliases","legal_in_editions","legends_in_editions","available_to"}
                    extra = {k: v for k, v in (node or {}).items() if k not in core_keys}
                    upsert_part(system, None, key, name, part_type="wargear", category=category, slot=slot, slots=slots,
                                aliases=aliases, legal_in_editions=legal, legends_in_editions=legends,
                                available_to=available_to, attributes=extra, raw_data=node, source_anchor=f"wargear.{key}")

            if is_parts_bodies:
                for key, node in data["bodies"].items():
                    name = node.get("name") or key.replace("_", " ").title()
                    faction_key = node.get("faction")
                    faction = None
                    if faction_key:
                        faction = session.execute(select(Faction).where(Faction.system_id == system.id, Faction.key == faction_key)).scalar_one_or_none()
                        if faction is None:
                            # create minimal faction placeholder if missing
                            faction = upsert_faction(session, system, faction_key, faction_key.replace("_"," ").title())
                    body_class = node.get("class")
                    slots = list(node.get("slots", []) or [])
                    aliases = list(node.get("aliases", []) or [])
                    legal = list(node.get("legal_in_editions", []) or [])
                    legends = list(node.get("legends_in_editions", []) or [])
                    available_to = []  # bodies typically faction-scoped; keep empty list or [faction_key]
                    core_keys = {"name","faction","class","slots","aliases","legal_in_editions","legends_in_editions","available_to","notes"}
                    extra = {k: v for k, v in (node or {}).items() if k not in core_keys}
                    upsert_part(system, faction, key, name, part_type="body", category=body_class, slot=None, slots=slots,
                                aliases=aliases, legal_in_editions=legal, legends_in_editions=legends,
                                available_to=available_to, attributes=extra, raw_data=node, source_anchor=f"bodies.{key}")

        else:
            # Units ingestion
            # The YAML schemas differ slightly per file; we expect a top-level 'factions' object for 40K/AoS
            factions_obj = data.get("factions") or {}

            def handle_units(faction_key: Optional[str], faction_name: Optional[str], units_obj: Dict[str, Any], source_anchor: Optional[str] = None, parent: Optional[Faction] = None, force_category: Optional[str] = None) -> None:
                faction: Optional[Faction] = None
                if faction_key and faction_name:
                    faction = upsert_faction(session, system, faction_key, faction_name, parent=parent)

                for unit_key, u_node in (units_obj or {}).items():
                    name = u_node.get("name") or unit_key.replace("_", " ").title()
                    role = u_node.get("role")
                    unique_flag = bool(u_node.get("unique", False))
                    aliases = list(u_node.get("aliases", []) or [])
                    legal = list(u_node.get("legal_in_editions", []) or [])
                    available_to = dict(u_node.get("available_to", {}) or {})
                    base_profile = u_node.get("base_profile") or u_node.get("base_profile_key")
                    category = force_category or u_node.get("category") or "unit"
                    # Everything not part of the core columns becomes attributes
                    core_keys = {"name","role","unique","aliases","legal_in_editions","available_to","base_profile","base_profile_key","category"}
                    extra_attrs: Dict[str, Any] = {k: v for k, v in (u_node or {}).items() if k not in core_keys}
                    upsert_unit(session, system, faction, unit_key, name, role, unique_flag,
                                aliases, legal, available_to, base_profile,
                                source_file=str(yaml_path.as_posix()), source_anchor=source_anchor,
                                category=category, attributes=extra_attrs, raw_data=u_node)

            # 40K/AoS top-level: factions: { key: { name, units, subfactions? } }
            for f_key, f in factions_obj.items():
                f_name = f.get("name") or f_key.replace("_", " ").title()
                # units directly under faction
                if isinstance(f.get("units"), dict):
                    handle_units(f_key, f_name, f.get("units"), source_anchor=f"factions.{f_key}.units")

                # AoS special categories under faction (import as units with category)
                special_map = {
                    "endless_spells": "endless_spell",
                    "manifestations": "manifestation",
                    "invocations": "invocation",
                    "warscroll_terrain": "terrain",
                }
                for sect, cat in special_map.items():
                    if isinstance(f.get(sect), dict):
                        handle_units(f_key, f_name, f.get(sect), source_anchor=f"factions.{f_key}.{sect}", force_category=cat)

                # subfactions or chapters etc.
                # For 40K we may have `chapters` or similar keys under available_to; here we look for nested structures named consistently
                for subkey in ("subfactions", "chapters", "orders", "septs", "dynasties", "hives", "temples"):
                    if isinstance(f.get(subkey), dict):
                        for sf_key, sf in f[subkey].items():
                            sf_name = sf.get("name") or sf_key.replace("_", " ").title()
                            parent = upsert_faction(session, system, f_key, f_name)
                            subf = upsert_faction(session, system, sf_key, sf_name, parent=parent)
                            if isinstance(sf.get("units"), dict):
                                handle_units(sf_key, sf_name, sf.get("units"), source_anchor=f"factions.{f_key}.{subkey}.{sf_key}.units", parent=parent)

            # AoS: top-level shared sections (e.g., shared_endless_spells, regiments_of_renown)
            top_special_map = {
                "shared_endless_spells": "endless_spell",
                "regiments_of_renown": "regiment",
                "shared_manifestations": "manifestation",
                "shared_invocations": "invocation",
                "shared_terrain": "terrain",
            }
            for sect, cat in top_special_map.items():
                if isinstance(data.get(sect), dict):
                    # No faction context; treat as cross-faction. faction=None, but category set.
                    handle_units(None, None, data.get(sect), source_anchor=sect, force_category=cat)

        if args.commit:
            session.commit()
            print("Committed codex load.")
        else:
            session.rollback()
            print("Dry-run complete (no changes committed).")


if __name__ == "__main__":
    main()
