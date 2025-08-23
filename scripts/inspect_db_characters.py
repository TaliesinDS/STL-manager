#!/usr/bin/env python3
"""Inspect the canonical DB for the `character` table and show a small sample.

This script uses the project's `db.session` and `db.models` to avoid quoting issues in PowerShell one-liners.
"""
import sys
from pathlib import Path
sys.path.insert(0, '.')
from sqlalchemy import text
from db.session import engine, SessionLocal
from db.models import Character

print('DB_URL from session engine:', engine.url)
# list tables
with engine.connect() as conn:
    rs = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
    tables = [r[0] for r in rs.fetchall()]
print('tables:', tables)

s = SessionLocal()
try:
    count = s.query(Character).count()
    print('db_character_count', count)
    if count > 0:
        for ch in s.query(Character).limit(10).all():
            print('SAMPLE:', ch.id, ch.name, 'aliases=', ch.aliases, 'franchise=', ch.franchise)
finally:
    s.close()
