"""Create a fresh SQLite DB file from SQLAlchemy metadata.

This script creates `data/stl_manager_fresh.db` (overwriting if present) and calls
Base.metadata.create_all() to create tables.
"""
import os
from sqlalchemy import create_engine

ROOT = os.path.dirname(os.path.dirname(__file__))
os.chdir(ROOT)

from db.models import Base

DB_PATH = os.path.join('data', 'stl_manager_fresh.db')
DB_URL = f"sqlite:///{DB_PATH}"

os.makedirs('data', exist_ok=True)
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

engine = create_engine(DB_URL)
print('Creating fresh DB at', DB_PATH)
Base.metadata.create_all(bind=engine)
print('Done')
