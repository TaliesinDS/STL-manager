import argparse
import json
import os
from datetime import datetime

from scripts.lib.mmf_client import MMFError, get_access_token, paginate_user_collections


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch MyMiniFactory user collections (public) into a report JSON")
    p.add_argument("--username", default=os.environ.get("MMF_USERNAME"), help="MyMiniFactory username (creator); can set MMF_USERNAME env var")
    p.add_argument("--out", default=None, help="Output JSON file (timestamped by default)")
    p.add_argument("--use-api-key", action="store_true", help="Use API key via ?key=... instead of OAuth token")
    p.add_argument("--max-pages", type=int, default=10)
    p.add_argument("--per-page", type=int, default=50)
    p.add_argument("--api-base", default=os.environ.get("MMF_API_BASE"), help="Override API base URL (default env MMF_API_BASE or official)")
    p.add_argument("--auth-base", default=os.environ.get("MMF_AUTH_BASE"), help="Override Auth base URL (default env MMF_AUTH_BASE or official)")
    args = p.parse_args()

    if not args.username:
        raise SystemExit("--username is required (or set MMF_USERNAME)")

    api_key = os.environ.get("MMF_API_KEY")
    client_id = os.environ.get("MMF_CLIENT_ID") or os.environ.get("MMF_CLIENT_KEY")
    client_secret = os.environ.get("MMF_CLIENT_SECRET")

    access_token = None
    if not args.use_api_key:
        if client_id and client_secret:
            try:
                # get_access_token uses env bases (or defaults); allow overrides via env before call
                if args.auth_base:
                    os.environ.setdefault("MMF_AUTH_BASE", args.auth_base)
                access_token = get_access_token(client_id, client_secret)
            except MMFError as e:
                # Some clients may not permit client_credentials; suggest API key fallback
                print(f"Warning: OAuth token fetch failed: {e}. Falling back to API key if available.")
        elif api_key:
            # fallback to api key if no oauth creds
            pass
        else:
            raise SystemExit("Missing MMF_CLIENT_ID/MMF_CLIENT_SECRET or MMF_API_KEY in environment.")

    items = paginate_user_collections(
        args.username,
        access_token=access_token,
        api_key=api_key if (args.use_api_key or not access_token) else None,
        per_page=args.per_page,
        max_pages=args.max_pages,
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.out or f"reports/mmf_collections_{args.username}_{stamp}.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)

    payload = {
        "username": args.username,
        "generated_at": datetime.now().isoformat(),
        "count": len(items),
        "items": items,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(items)} collections to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
