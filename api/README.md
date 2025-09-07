STL Manager API (prototype)

Run locally (Windows PowerShell):

```powershell
Set-Location c:/Users/akortekaas/Documents/GitHub/STL-manager
$env:STLMGR_DB_URL="sqlite:///./data/stl_manager_v1.db";
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Endpoints:
- `GET /health` – service status
- `GET /variants?q=&system=&faction=&limit=&offset=` – paginated list
- `GET /variants/{id}` – variant detail with files

Notes:
- Uses existing SQLAlchemy models and session; respects `STLMGR_DB_URL`.
- CORS is open for local dev; tighten before production.
