"""
Source fetchers: RSS feeds + optional Tavily web search.
Filters for recent, agentic-AI-relevant items.
"""
import os
import re
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import feedparser
import httpx


# ---- Curate your sources here ----
# High-signal RSS feeds covering AI agents, tooling, and research.
RSS_FEEDS = [
    # Individual researchers / practitioners
    ("Simon Willison", "https://simonwillison.net/atom/everything/"),
    ("Import AI (Jack Clark)", "https://jack-clark.net/feed/"),
    ("Sebastian Raschka", "https://magazine.sebastianraschka.com/feed"),
    # Labs & companies
    ("Anthropic News", "https://www.anthropic.com/news/rss.xml"),
    ("OpenAI Blog", "https://openai.com/blog/rss.xml"),
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml"),
    ("Google DeepMind Blog", "https://deepmind.google/blog/rss.xml"),
    # News
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    # Aggregators
    ("Hacker News front page", "https://hnrss.org/frontpage?points=150"),
]

# Nitter mirrors Twitter and exposes per-user RSS at {instance}/{handle}/rss.
# Public instances break often — we try each in order until one responds.
# Swap in fresh instances from https://github.com/zedeus/nitter/wiki/Instances when these die.
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
]

# AI-adjacent handles to pull. Edit freely.
TWITTER_HANDLES = [
    "karpathy",
    "sama",
    "ylecun",
    "jeremyphoward",
    "AnthropicAI",
    "OpenAI",
    "GoogleDeepMind",
    "DrJimFan",
    "svpino",
    "hwchase17",
    "_philschmid",
    "rasbt",
]

# Keywords we care about. If an item mentions none of these, we drop it.
RELEVANCE_KEYWORDS = [
    "agent", "agentic", "agents",
    "tool use", "tool-use", "function call",
    "mcp", "model context protocol",
    "llm", "claude", "gpt", "gemini", "openai", "anthropic", "mistral", "llama",
    "autonomous", "workflow", "orchestration",
    "langchain", "langgraph", "llamaindex", "crewai", "autogen",
    "rag", "retrieval", "vector",
    "fine-tun", "post-train", "rlhf", "rlaif",
    "browser use", "computer use", "coding agent",
    "open source model", "open-weight",
]


@dataclass
class Item:
    source: str
    title: str
    url: str
    published: datetime
    summary: str

    @property
    def dedup_key(self) -> str:
        # Normalize URL + title to catch duplicates across aggregators.
        norm = re.sub(r"[^a-z0-9]", "", (self.url + self.title).lower())
        return hashlib.sha1(norm.encode()).hexdigest()


def _clean(text: str) -> str:
    """Strip HTML tags and excess whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _is_relevant(item: Item) -> bool:
    blob = f"{item.title} {item.summary}".lower()
    return any(kw in blob for kw in RELEVANCE_KEYWORDS)


def _parse_date(entry) -> Optional[datetime]:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        val = entry.get(key)
        if val:
            return datetime(*val[:6], tzinfo=timezone.utc)
    return None


def fetch_rss_items(lookback_hours: int) -> List[Item]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    items: List[Item] = []

    for name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {name}: failed to parse ({e})")
            continue

        count_for_feed = 0
        for entry in feed.entries:
            published = _parse_date(entry)
            if not published or published < cutoff:
                continue

            item = Item(
                source=name,
                title=_clean(entry.get("title", "")),
                url=entry.get("link", ""),
                published=published,
                summary=_clean(entry.get("summary", ""))[:800],
            )
            if item.title and item.url:
                items.append(item)
                count_for_feed += 1
        print(f"  - {name}: {count_for_feed} fresh items")
    return items


def fetch_twitter_items(lookback_hours: int) -> List[Item]:
    """Fetch recent posts from configured Twitter handles via Nitter RSS.

    Tries each Nitter instance in order per handle; stops at the first one
    that returns entries. Silently skips handles when every instance fails.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    items: List[Item] = []

    for handle in TWITTER_HANDLES:
        feed = None
        for instance in NITTER_INSTANCES:
            url = f"{instance}/{handle}/rss"
            try:
                parsed = feedparser.parse(url)
            except Exception as e:  # noqa: BLE001
                print(f"  ! Twitter @{handle} via {instance}: parse failed ({e})")
                continue
            if parsed.entries:
                feed = parsed
                break

        if feed is None:
            print(f"  ! Twitter @{handle}: no Nitter instance returned entries")
            continue

        count_for_handle = 0
        for entry in feed.entries:
            published = _parse_date(entry)
            if not published or published < cutoff:
                continue

            item = Item(
                source=f"Twitter: @{handle}",
                title=_clean(entry.get("title", "")),
                url=entry.get("link", ""),
                published=published,
                summary=_clean(entry.get("summary", ""))[:800],
            )
            if item.title and item.url:
                items.append(item)
                count_for_handle += 1
        print(f"  - Twitter @{handle}: {count_for_handle} fresh items")

    return items


def fetch_tavily_items(lookback_hours: int) -> List[Item]:
    """Optional: use Tavily search API to catch items RSS missed.
    Set TAVILY_API_KEY in env to enable. Free tier gives you 1k/month.
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return []

    queries = [
        "AI agent framework release",
        "LLM agent tool use new",
        "MCP model context protocol",
        "agentic AI benchmark",
    ]
    items: List[Item] = []
    for q in queries:
        try:
            resp = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": q,
                    "topic": "news",
                    "days": max(1, lookback_hours // 24),
                    "max_results": 5,
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:  # noqa: BLE001
            print(f"  ! Tavily query '{q}' failed: {e}")
            continue

        for r in data.get("results", []):
            items.append(Item(
                source=f"Tavily: {q}",
                title=r.get("title", ""),
                url=r.get("url", ""),
                published=datetime.now(timezone.utc),  # Tavily doesn't return dates reliably
                summary=(r.get("content") or "")[:800],
            ))
    print(f"  - Tavily: {len(items)} items")
    return items


def fetch_all_items(lookback_hours: int = 24) -> List[Item]:
    print("Fetching from RSS feeds...")
    rss = fetch_rss_items(lookback_hours)

    print("Fetching from Twitter (Nitter RSS)...")
    twitter = fetch_twitter_items(lookback_hours)

    print("Fetching from Tavily (if configured)...")
    tavily = fetch_tavily_items(lookback_hours)

    # Dedupe
    seen = {}
    for item in rss + twitter + tavily:
        seen.setdefault(item.dedup_key, item)
    unique = list(seen.values())

    # Filter for relevance
    relevant = [i for i in unique if _is_relevant(i)]

    # Sort newest first
    relevant.sort(key=lambda i: i.published, reverse=True)

    # Cap to avoid overloading the summarizer
    return relevant[:40]
