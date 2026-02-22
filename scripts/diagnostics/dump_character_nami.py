from db.models import VocabEntry
from db.session import get_session

with get_session() as session:
    rows = session.query(VocabEntry).filter_by(domain='character').all()
    for r in rows:
        if 'nami' in ([r.key] + (r.aliases or [])):
            print(f"Key: {r.key}, Aliases: {r.aliases}")
