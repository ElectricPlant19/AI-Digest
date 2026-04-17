"""
GET /api/unsubscribe?email=...&token=...
Verifies HMAC token, removes the email from subscribers.json,
then 302-redirects to /unsubscribed.html.
"""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from _shared import (
    valid_email,
    verify_token,
    read_subscribers,
    write_subscribers,
    json_response,
)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        email = (qs.get("email", [""])[0] or "").strip().lower()
        token = qs.get("token", [""])[0]

        if not valid_email(email) or not verify_token(email, token):
            return json_response(self, 400, {"error": "Invalid or expired unsubscribe link."})

        try:
            for attempt in range(2):
                try:
                    subs, sha = read_subscribers()
                    new_subs = [s for s in subs if s.get("email", "").lower() != email]
                    if len(new_subs) != len(subs):
                        write_subscribers(new_subs, sha, f"chore(subscribers): remove {email}")
                    break
                except RuntimeError as e:
                    if "conflict" in str(e) and attempt == 0:
                        continue
                    raise
        except Exception as e:
            return json_response(self, 500, {"error": f"Server error: {e}"})

        # Redirect to the static confirmation page
        self.send_response(302)
        self.send_header("Location", "/unsubscribed.html")
        self.end_headers()
