#!/usr/bin/env python3
import sys
from pathlib import Path

# Ensure project root is on sys.path for imports
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import get_session
from db.models import Variant
import json

ids=[66,69,77,78,79,80,82,84,85,86,87,88,89,142,146,149,150,153,154]
out=[]
with get_session() as s:
    rows=s.query(Variant).filter(Variant.id.in_(ids)).all()
    for v in rows:
        out.append({'variant_id':v.id,'rel_path':v.rel_path,'codex_unit_name':v.codex_unit_name,'character_name':v.character_name,'character_aliases':v.character_aliases})
print(json.dumps(out,ensure_ascii=False,indent=2))
