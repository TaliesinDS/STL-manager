# Python Cheatsheet (STL-manager focused)

Quick reference of Python language basics, stdlib modules and common project patterns you will use frequently in this repo.

## Core language
- Function: `def fn(x: int) -> int:`
- Class: `class Foo:` with `__init__` and instance methods
- Conditionals / loops: `if` / `elif` / `else`, `for item in iterable:`, `while` loops
- Context manager: `with open(path, 'r', encoding='utf-8') as f:`
- Exceptions: `try: ... except Exception as e: ... finally: ...`
- Comprehensions: `[x*2 for x in xs]`, `{k:v for k,v in pairs}`
- Unpacking: `a, *rest = seq`, dict unpack: `f(**kwargs)`
- Generators: `def gen(): yield x`
- Async basics (optional): `async def`, `await`, use only if using async libs

## Common idioms
- Truthiness: `if mylist:` is True for non-empty
- EAFP: Try to do it and catch exceptions rather than pre-checking in many cases
- Use `pathlib.Path` for paths (cross-platform)

## Useful stdlib modules
- `pathlib` — Path operations
  ```py
  from pathlib import Path
  p = Path('data') / 'stl_manager_v1.db'
  p.exists()
  ```
- `json` — read/write JSON
- `logging` / `structlog` — structured logs
- `datetime` — timestamps (`datetime.utcnow()`)
- `concurrent.futures` — simple thread pool for background jobs
  ```py
  from concurrent.futures import ThreadPoolExecutor
  with ThreadPoolExecutor(max_workers=4) as ex:
      fut = ex.submit(task, arg)
  ```
- `subprocess` — run external commands

## Virtual env & packaging quick commands
```powershell
# create venv (Windows)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Project patterns (SQLAlchemy + FastAPI)

Session pattern (sync SQLAlchemy):
```py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(STLMGR_DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
```

FastAPI dependency injection (example):
```py
from fastapi import Depends, FastAPI

app = FastAPI()

@app.get('/variants')
def list_variants(session: Session = Depends(get_session)):
    return session.query(Variant).limit(50).all()
```

Alembic quick pattern
- Keep `alembic/` scaffold and revision files under source control.
- Generate: `alembic revision --autogenerate -m "msg"` then `alembic upgrade head`.

## Common helpers & snippets

Normalize name (simple):
```py
import unicodedata, re

def normalize_name(s: str) -> str:
    s = unicodedata.normalize('NFKC', s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", '_', s)
    return s.strip('_')
```

Safe DB upsert pattern (SQLAlchemy ORM):
```py
obj = session.query(VocabEntry).filter_by(domain='franchise', key=key).one_or_none()
if obj is None:
    obj = VocabEntry(domain='franchise', key=key, meta={})
    session.add(obj)
    session.commit()
else:
    obj.meta.update(new_meta)
    session.commit()
```

## Testing & linting
- Run tests: `pytest -q`
- Lint/format: `ruff . --fix` (or use pre-commit hooks)
- Type check: `mypy src_or_package`

## Debugging tips
- Use `python -m pdb script.py` or `breakpoint()` (Python 3.7+) to inspect.
- Use the REPL for quick experiments: `python -c "from pathlib import Path; print(Path('.').resolve())"`.

## Quick references
- Official Python docs: https://docs.python.org/3/
- SQLAlchemy 2.x docs: https://docs.sqlalchemy.org/
- FastAPI docs: https://fastapi.tiangolo.com/

---
Small, project-focused cheatsheet. If you want, I can expand sections (SQLAlchemy examples, Alembic tips, sample tests) into separate files.
