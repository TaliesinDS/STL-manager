import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

MMF_BASE = os.environ.get("MMF_API_BASE", "https://www.myminifactory.com/api/v2")
AUTH_BASE = os.environ.get("MMF_AUTH_BASE", "https://auth.myminifactory.com")


class MMFError(Exception):
    pass


def _http_request(url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, data: Optional[bytes] = None) -> Dict[str, Any]:
    req = urllib.request.Request(url, data=data, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            ct = resp.headers.get("Content-Type", "application/json")
            raw = resp.read()
            if "application/json" in ct:
                return json.loads(raw.decode("utf-8"))
            return {"raw": raw.decode("utf-8", errors="replace"), "status": resp.status}
    except Exception as e:
        raise MMFError(f"HTTP {method} {url} failed: {e}")


def get_access_token(client_id: str, client_secret: str, *, grant_type: str = "client_credentials") -> str:
    # Note: Official docs show authorization_code and implicit flows. For non-user access to public endpoints,
    # prefer API key when possible. If client credentials are enabled, obtain a token like below; otherwise, fall back to key.
    token_url = f"{AUTH_BASE}/v1/oauth/tokens"
    data = urllib.parse.urlencode({
        "grant_type": grant_type,
        # client_credentials typically uses HTTP Basic auth; emulate with header
    }).encode("utf-8")
    basic = urllib.parse.quote(client_id) + ":" + urllib.parse.quote(client_secret)
    basic_b64 = __import__("base64").b64encode(basic.encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Basic {basic_b64}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    resp = _http_request(token_url, method="POST", headers=headers, data=data)
    token = resp.get("access_token")
    if not token:
        raise MMFError(f"No access_token in token response: {resp}")
    return token


def get_user_collections(username: str, *, access_token: Optional[str] = None, api_key: Optional[str] = None, page: int = 1, per_page: int = 50) -> Dict[str, Any]:
    # Endpoint: GET /users/{username}/collections with either OAuth2 or key
    qs = {"page": str(page), "per_page": str(per_page)}
    if api_key:
        qs["key"] = api_key
    url = f"{MMF_BASE}/users/{urllib.parse.quote(username)}/collections?{urllib.parse.urlencode(qs)}"
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return _http_request(url, headers=headers)


def get_collection(collection_id: str, *, access_token: Optional[str] = None, api_key: Optional[str] = None, page: int = 1, per_page: int = 50) -> Dict[str, Any]:
    qs = {"page": str(page), "per_page": str(per_page)}
    if api_key:
        qs["key"] = api_key
    url = f"{MMF_BASE}/collections/{urllib.parse.quote(collection_id)}?{urllib.parse.urlencode(qs)}"
    headers = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return _http_request(url, headers=headers)


def paginate_user_collections(username: str, *, access_token: Optional[str] = None, api_key: Optional[str] = None, per_page: int = 50, max_pages: int = 20) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        data = get_user_collections(username, access_token=access_token, api_key=api_key, page=page, per_page=per_page)
        page_items = data.get("items") or data.get("objects") or data.get("data") or []
        if not page_items:
            break
        items.extend(page_items)
        total = data.get("total_count")
        if total is not None and len(items) >= int(total):
            break
        time.sleep(0.2)
    return items
