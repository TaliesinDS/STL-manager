"""Set or update alembic_version in a SQLite DB file.

Usage: python scripts/set_alembic_version.py <path-to-db-file> <revision-id>
"""
import sqlite3
import sys
from pathlib import Path

if len(sys.argv) < 3:
    print("Usage: set_alembic_version.py <db_path> <revision>")
    sys.exit(2)

db_path = Path(sys.argv[1])
rev = sys.argv[2]

if not db_path.exists():
    print(f"DB file does not exist: {db_path}")
    sys.exit(2)

conn = sqlite3.connect(str(db_path))
cur = conn.cursor()
# Ensure alembic_version table exists
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
if not cur.fetchone():
    print('alembic_version table not found, creating it')
    cur.execute('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)')
    conn.commit()

cur.execute('SELECT version_num FROM alembic_version')
rows = cur.fetchall()
print('Before:', rows)
if rows:
    cur.execute('UPDATE alembic_version SET version_num = ?', (rev,))
else:
    cur.execute('INSERT INTO alembic_version (version_num) VALUES (?)', (rev,))
conn.commit()
cur.execute('SELECT version_num FROM alembic_version')
print('After:', cur.fetchall())
conn.close()
