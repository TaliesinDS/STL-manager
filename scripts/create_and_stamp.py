from sqlalchemy import create_engine, inspect
from db.models import Base

DB_PATH = 'sqlite:///./data/stl_manager_clean.db'

engine = create_engine(DB_PATH)
print('Creating tables in', DB_PATH)
Base.metadata.create_all(engine)
ins = inspect(engine)
print('\nTables now present:')
for t in ins.get_table_names():
    print(' -', t)

print('\nDone.')
