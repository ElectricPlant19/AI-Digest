"""
POST /api/subscribe  { "email": "..." }
Appends to subscribers.json in the repo via GitHub Contents API.
"""
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

from api._shared import (
    valid_email,
    read_subscribers,
    write_subscribers,
    json_response,
)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode("utf-8") or "{}")
            email = (body.get("email") or "").strip().lower()

            if not valid_email(email):
                return json_response(self, 400, {"error": "Please enter a valid email address."})

            # Retry once on concurrency conflict
            for attempt in range(2):
                try:
                    subs, sha = read_subscribers()
                    existing = {s.get("email", "").lower() for s in subs}
                    if email in existing:
                        return json_response(self, 200, {"message": "You're already subscribed."})
                    subs.append({
                        "email": email,
                        "subscribed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    })
                    write_subscribers(subs, sha, f"chore(subscribers): add {email}")
                    return json_response(self, 200, {"message": "You're in. Check your inbox tomorrow morning."})
                except RuntimeError as e:
                    if "conflict" in str(e) and attempt == 0:
                        continue
                    raise

        except Exception as e:
            return json_response(self, 500, {"error": f"Server error: {e}"})
