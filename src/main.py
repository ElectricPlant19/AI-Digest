"""
AI Agentic Tools Daily Digest Bot
Pulls fresh articles from RSS + web search, summarizes with Claude, emails a TLDR.
"""
import os
import sys
from datetime import datetime, timezone

from config import load_config
from sources import fetch_all_items
from summarize import summarize_digest
from email_sender import send_digest_to_subscribers
from subscribers import load_subscribers


def main() -> int:
    load_config()
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting AI digest run...")

    # 1. Gather fresh items from all sources (last 24h)
    items = fetch_all_items(lookback_hours=24)
    print(f"Fetched {len(items)} items after dedup + filtering.")

    if not items:
        print("No new items worth summarizing today. Skipping email.")
        return 0

    # 2. Send to Claude for a TLDR grouped by theme
    digest_html, digest_text = summarize_digest(items)
    print(f"Summary generated ({len(digest_text)} chars).")

    # 3. Resolve recipient list (fallback to DIGEST_TO_EMAIL if list empty)
    subs = load_subscribers()
    if not subs and os.getenv("DIGEST_TO_EMAIL"):
        subs = [{"email": os.environ["DIGEST_TO_EMAIL"]}]
    if not subs:
        print("No subscribers configured. Skipping email.")
        return 0

    # 4. Fan out to every subscriber
    subject = f"🤖 AI Agents Daily — {datetime.now().strftime('%b %d, %Y')}"
    stats = send_digest_to_subscribers(
        subject=subject,
        html_body=digest_html,
        text_body=digest_text,
        subscribers=subs,
    )
    print(f"Email sent to {stats['sent']} subscribers ({stats['failed']} failed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
