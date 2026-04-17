"""
Subscriber list helpers.

The list is stored as `subscribers.json` at the repo root. The Vercel
serverless functions in `/api` edit it via the GitHub Contents API; the
pipeline reads it directly from the checked-out working tree.

Unsubscribe URLs are HMAC-signed with UNSUB_SECRET so the same secret
deployed to Vercel can verify tokens the pipeline mints.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import List, Dict
from urllib.parse import urlencode


REPO_ROOT = Path(__file__).resolve().parent.parent
SUBSCRIBERS_FILE = REPO_ROOT / "subscribers.json"


def load_subscribers() -> List[Dict]:
    if not SUBSCRIBERS_FILE.exists():
        return []
    with SUBSCRIBERS_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return [s for s in data if s.get("email")]


def _sign(email: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        email.lower().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def unsubscribe_url(email: str) -> str:
    base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    secret = os.environ.get("UNSUB_SECRET", "")
    if not base or not secret:
        return ""
    token = _sign(email, secret)
    return f"{base}/api/unsubscribe?" + urlencode({"email": email, "token": token})


def verify_token(email: str, token: str, secret: str) -> bool:
    return hmac.compare_digest(_sign(email, secret), token or "")
