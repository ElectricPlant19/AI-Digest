"""
Shared helpers for Vercel serverless functions.
Reads / writes subscribers.json in the GitHub repo via the Contents API.
"""
import base64
import hashlib
import hmac
import json
import os
import re
from typing import Tuple, List, Dict

import urllib.request
import urllib.error


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
SUBSCRIBERS_PATH = "subscribers.json"


def valid_email(email: str) -> bool:
    return bool(email) and len(email) <= 254 and EMAIL_RE.match(email) is not None


def _gh_request(method: str, url: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "ai-digest-bot-subscribe")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads((e.read() or b"{}").decode("utf-8") or "{}")


def _contents_url(repo: str) -> str:
    return f"https://api.github.com/repos/{repo}/contents/{SUBSCRIBERS_PATH}"


def read_subscribers() -> Tuple[List[Dict], str]:
    """Returns (subscribers, blob_sha). Creates empty list if file missing."""
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPO"]
    status, data = _gh_request("GET", _contents_url(repo), token)
    if status == 404:
        return [], ""
    if status >= 400:
        raise RuntimeError(f"GitHub GET failed [{status}]: {data}")
    content = base64.b64decode(data.get("content", "")).decode("utf-8") or "[]"
    subs = json.loads(content)
    return subs, data.get("sha", "")


def write_subscribers(subs: List[Dict], sha: str, message: str) -> None:
    token = os.environ["GITHUB_TOKEN"]
    repo = os.environ["GITHUB_REPO"]
    branch = os.environ.get("GITHUB_BRANCH", "main")
    payload = {
        "message": message,
        "content": base64.b64encode(
            (json.dumps(subs, indent=2) + "\n").encode("utf-8")
        ).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    status, data = _gh_request("PUT", _contents_url(repo), token, payload)
    if status == 409 or status == 422:
        # Optimistic-concurrency miss — re-read and retry once.
        fresh, new_sha = read_subscribers()
        # Caller passed the desired final list; re-apply by merging their
        # intent is tricky. Simplest: they should retry at a higher level.
        raise RuntimeError(f"GitHub PUT conflict [{status}]: retry needed")
    if status >= 400:
        raise RuntimeError(f"GitHub PUT failed [{status}]: {data}")


def verify_token(email: str, token: str) -> bool:
    secret = os.environ.get("UNSUB_SECRET", "")
    if not secret or not token:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        email.lower().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, token)


def json_response(handler, status: int, body: dict) -> None:
    payload = json.dumps(body).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(payload)
