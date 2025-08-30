import sqlite3
import sys
from pathlib import Path

p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('data/stl_manager_autogen.db')
if not p.exists():
    print(f"File not found: {p}")
    sys.exit(2)

conn = sqlite3.connect(str(p))
cur = conn.cursor()
print('Inspecting', p)
print('-' * 60)
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
rows = cur.fetchall()
print('Tables:')
for r in rows:
    print(' -', r[0])

print('\nContents of alembic_version (if present):')
try:
    cur.execute('SELECT * FROM alembic_version')
    av = cur.fetchall()
    if av:
        for row in av:
            print(' ', row)
    else:
        print('  <empty>')
except Exception as e:
    print('  could not read alembic_version:', e)

conn.close()
