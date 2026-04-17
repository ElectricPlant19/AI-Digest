"""
Resend email sender. Get a free API key at https://resend.com
"""
import os
from typing import Iterable, Dict

import httpx

from subscribers import unsubscribe_url


def _from_email() -> str:
    return os.environ.get("DIGEST_FROM_EMAIL", "AI Digest <onboarding@resend.dev>")


def _post_resend(api_key: str, payload: dict) -> None:
    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Resend failed [{resp.status_code}]: {resp.text}")


def send_digest_email(subject: str, html_body: str, text_body: str) -> None:
    """Single-recipient send (legacy/fallback path using DIGEST_TO_EMAIL)."""
    api_key = os.environ["RESEND_API_KEY"]
    to_email = os.environ["DIGEST_TO_EMAIL"]
    url = unsubscribe_url(to_email)
    _post_resend(api_key, {
        "from": _from_email(),
        "to": [to_email],
        "subject": subject,
        "html": html_body.replace("{{unsubscribe_url}}", url),
        "text": text_body.replace("{{unsubscribe_url}}", url),
    })


def send_digest_to_subscribers(
    subject: str,
    html_body: str,
    text_body: str,
    subscribers: Iterable[Dict],
) -> Dict[str, int]:
    """Fan-out send: one Resend call per subscriber, with a per-recipient
    unsubscribe link substituted into the {{unsubscribe_url}} placeholder.

    Returns {"sent": n, "failed": m}. Failures are logged but don't abort.
    """
    api_key = os.environ["RESEND_API_KEY"]
    from_email = _from_email()
    sent = 0
    failed = 0

    for sub in subscribers:
        email = sub.get("email")
        if not email:
            continue
        url = unsubscribe_url(email)
        try:
            _post_resend(api_key, {
                "from": from_email,
                "to": [email],
                "subject": subject,
                "html": html_body.replace("{{unsubscribe_url}}", url),
                "text": text_body.replace("{{unsubscribe_url}}", url),
            })
            sent += 1
        except Exception as e:
            failed += 1
            print(f"[email] send failed for {email}: {e}")

    return {"sent": sent, "failed": failed}
