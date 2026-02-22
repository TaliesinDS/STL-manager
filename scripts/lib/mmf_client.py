import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

MMF_BASE = os.environ.get("MMF_API_BASE", "https://www.myminifactory.com/api/v2")
AUTH_BASE = os.environ.get("MMF_AUTH_BASE", "https://auth.myminifactory.com")

_log = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds; doubles each retry


class MMFError(Exception):
    pass


def _http_request(url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, data: Optional[bytes] = None) -> Dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
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
        except urllib.error.HTTPError as e:
            # Don't retry client errors (4xx) except 429 (rate limit)
            if 400 <= e.code < 500 and e.code != 429:
                raise MMFError(f"HTTP {method} {url} failed: {e}")
            last_exc = e
        except Exception as e:
            last_exc = e
        if attempt < _MAX_RETRIES:
            delay = _BACKOFF_BASE * (2 ** attempt)
            _log.warning("MMF request failed (attempt %d/%d), retrying in %.1fs: %s",
                         attempt + 1, _MAX_RETRIES + 1, delay, last_exc)
            time.sleep(delay)
    raise MMFError(f"HTTP {method} {url} failed after {_MAX_RETRIES + 1} attempts: {last_exc}")


def get_access_token(client_id: str, client_secret: str, *, grant_type: str = "client_credentials") -> str:
    # Note: Official docs highlight authorization_code/implicit. Some environments support client_credentials; if not,
    # prefer using an API key via `key` query parameter.
    token_url = f"{AUTH_BASE}/v1/oauth/tokens"
    data = urllib.parse.urlencode({
        "grant_type": grant_type,
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
    qs = {"page": str(page), "per_page": str(per_page)}
    if api_key:
        qs["key"] = api_key
    if access_token:
        qs["access_token"] = access_token
    url = f"{MMF_BASE}/users/{urllib.parse.quote(username)}/collections?{urllib.parse.urlencode(qs)}"
    return _http_request(url)


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


def get_user_posts(username: str, *, access_token: Optional[str] = None, api_key: Optional[str] = None, page: int = 1, per_page: int = 50) -> Dict[str, Any]:
    qs = {"page": str(page), "per_page": str(per_page)}
    if api_key:
        qs["key"] = api_key
    if access_token:
        qs["access_token"] = access_token
    url = f"{MMF_BASE}/users/{urllib.parse.quote(username)}/posts?{urllib.parse.urlencode(qs)}"
    return _http_request(url)


def paginate_user_posts(username: str, *, access_token: Optional[str] = None, api_key: Optional[str] = None, per_page: int = 50, max_pages: int = 20) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        data = get_user_posts(username, access_token=access_token, api_key=api_key, page=page, per_page=per_page)
        page_items = data.get("items") or data.get("data") or []
        if not page_items:
            break
        items.extend(page_items)
        total = data.get("total_count")
        if total is not None and len(items) >= int(total):
            break
        time.sleep(0.2)
    return items

def list_collections(*, username: Optional[str] = None, page: int = 1, per_page: int = 50, access_token: Optional[str] = None, api_key: Optional[str] = None) -> Dict[str, Any]:
    qs: Dict[str, str] = {"page": str(page), "per_page": str(per_page)}
    if username:
        qs["username"] = username
    if api_key:
        qs["key"] = api_key
    if access_token:
        qs["access_token"] = access_token
    url = f"{MMF_BASE}/collections?{urllib.parse.urlencode(qs)}"
    return _http_request(url)


class _CollectionsHTMLParser(HTMLParser):
    def __init__(self, username: str) -> None:
        super().__init__()
        self.username = username
        self.links: List[Dict[str, str]] = []
        self._capture_text_for: Optional[str] = None
        self._current_text: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = None
        for k, v in attrs:
            if k == "href":
                href = v
                break
        if not href:
            return
        # Match collection links: /users/{username}/collection/{slug}
        expected_prefix = f"/users/{self.username}/collection/"
        if href.startswith(expected_prefix):
            self._capture_text_for = href
            self._current_text = []

    def handle_data(self, data):
        if self._capture_text_for is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._capture_text_for is not None:
            text = ("".join(self._current_text)).strip()
            self.links.append({
                "href": self._capture_text_for,
                "text": text,
            })
            self._capture_text_for = None
            self._current_text = []


def _slug_from_href(href: str) -> str:
    # last path segment
    try:
        slug = href.rstrip("/").split("/")[-1]
        return urllib.parse.unquote(slug)
    except Exception:
        return href


def _title_from_slug(slug: str) -> str:
    parts = slug.replace("_", "-").split("-")
    small = {"of", "the", "and", "in", "on"}
    title_parts: List[str] = []
    for i, p in enumerate(parts):
        if not p:
            continue
        word = p.lower()
        if i > 0 and word in small:
            title_parts.append(word)
        else:
            title_parts.append(word.capitalize())
    return " ".join(title_parts)


def scrape_user_collections(username: str, *, limit: int = 50) -> List[Dict[str, Any]]:
    url = f"https://www.myminifactory.com/users/{urllib.parse.quote(username)}/collections"
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36")
        req.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8")
        req.add_header("Accept-Language", "en-US,en;q=0.9")
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise MMFError(f"Scrape GET {url} failed: {e}")
    parser = _CollectionsHTMLParser(username)
    parser.feed(html)
    seen = set()
    items: List[Dict[str, Any]] = []
    for link in parser.links:
        href = link.get("href") or ""
        if not href or href in seen:
            continue
        seen.add(href)
        slug = _slug_from_href(href)
        name = link.get("text") or _title_from_slug(slug)
        items.append({
            "slug": slug,
            "name": name,
            "url": f"https://www.myminifactory.com{href}",
        })
        if len(items) >= limit:
            break
    return items
