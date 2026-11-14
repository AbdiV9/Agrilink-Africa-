# Owner: Person 3 (Integration, Logic & API Lead)
"""Farming news from an RSS feed (STRETCH). No key needed.

``get_news(limit=20, crop=None)`` returns::

    {"items": [{"title", "link", "source", "published", "summary"}],
     "source": "live" | "cache" | "sample"}

The feed (``NEWS_FEED_URL``, Google News by default) is cached for an hour.
If it can't be reached, the last good copy is used, or sample headlines
(cached for 10 minutes so offline pages don't keep retrying).
"""

from __future__ import annotations

import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import config

log = logging.getLogger(__name__)

MAX_FEED_BYTES = 2_000_000
SAMPLE_RETRY_SECONDS = 600

_cache: dict[str, tuple[float, list[dict[str, Any]], str]] = {}  # url -> (stored_at, items, source)
_clock = time.time  # tests can replace this


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _iso(date_text: str | None) -> str:
    if not date_text:
        return ""
    try:
        return parsedate_to_datetime(date_text).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        return date_text.strip()


def parse_feed(xml_text: str | bytes) -> list[dict[str, Any]]:
    """Parse RSS 2.0 (or Atom) into news items, newest first."""
    root = ET.fromstring(xml_text)
    items: list[dict[str, Any]] = []
    atom = "{http://www.w3.org/2005/Atom}"
    for node in root.iter("item"):
        title = _strip_html(node.findtext("title") or "")
        source = (node.findtext("source") or "").strip()
        if not source and " - " in title:  # Google News: "Headline - Publisher"
            title, source = title.rsplit(" - ", 1)
        items.append({
            "title": title,
            "link": (node.findtext("link") or "").strip(),
            "source": source,
            "published": _iso(node.findtext("pubDate")),
            "summary": _strip_html(node.findtext("description") or "")[:300],
        })
    for node in root.iter(f"{atom}entry"):
        link = node.find(f"{atom}link")
        items.append({
            "title": _strip_html(node.findtext(f"{atom}title") or ""),
            "link": link.get("href", "") if link is not None else "",
            "source": _strip_html(node.findtext(f"{atom}author/{atom}name") or ""),
            "published": node.findtext(f"{atom}updated") or "",
            "summary": _strip_html(node.findtext(f"{atom}summary") or "")[:300],
        })
    items = [i for i in items if i["title"] and i["link"].startswith(("http://", "https://"))]
    items.sort(key=lambda i: i["published"], reverse=True)
    return items


def _fetch(url: str) -> list[dict[str, Any]]:
    import requests

    resp = requests.get(url, timeout=10, headers={"User-Agent": f"{config.APP_NAME}/{config.APP_VERSION}"})
    resp.raise_for_status()
    return parse_feed(resp.content[:MAX_FEED_BYTES])


def sample_news() -> list[dict[str, Any]]:
    """Offline headlines so the page still has something useful."""
    now = datetime.now(timezone.utc)
    rows = [
        ("Maize prices ease as long-rains harvest reaches markets", "AgriLink sample",
         "Traders in Nakuru and Eldoret report more supply, pushing wholesale prices down for the third week."),
        ("Coffee farmers see strong demand ahead of export season", "AgriLink sample",
         "Cooperatives in Kenya and Uganda say buyers are paying premiums for well-graded beans."),
        ("How to store grain safely and avoid post-harvest losses", "AgriLink sample",
         "Hermetic bags and drying to 13% moisture can cut storage losses by more than half."),
        ("Cocoa prices stay high as West African supply stays tight", "AgriLink sample",
         "Farmers in Ghana and Côte d'Ivoire are urged to protect trees from black pod during the rains."),
        ("Short rains forecast: plan beans and vegetables now", "AgriLink sample",
         "Forecasters expect near-normal rainfall in East Africa; early planting is advised."),
        ("Tomato prices swing as transport costs rise", "AgriLink sample",
         "Selling closer to home or in groups can help farmers keep more of the price."),
    ]
    return [{"title": t, "link": "https://www.fao.org/africa/news/en/", "source": s,
             "published": (now - timedelta(hours=6 * i)).isoformat(), "summary": summary}
            for i, (t, s, summary) in enumerate(rows)]


def _all_news(url: str) -> tuple[list[dict[str, Any]], str]:
    cached = _cache.get(url)
    if cached and _clock() - cached[0] < config.NEWS_CACHE_SECONDS:
        return cached[1], "cache" if cached[2] == "live" else cached[2]
    try:
        items = _fetch(url)
        if not items:
            raise ValueError("Feed had no items")
        _cache[url] = (_clock(), items, "live")
        return items, "live"
    except Exception as exc:
        log.warning("News feed unavailable (%s); using %s", exc, "cache" if cached else "sample")
        if cached and cached[2] == "live":
            return cached[1], "cache"
        sample = sample_news()
        _cache[url] = (_clock() - config.NEWS_CACHE_SECONDS + SAMPLE_RETRY_SECONDS, sample, "sample")
        return sample, "sample"


def get_news(limit: int = 20, crop: str | None = None) -> dict[str, Any]:
    """Latest farming news, optionally only items mentioning ``crop``. Never raises."""
    items, source = _all_news(config.NEWS_FEED_URL)
    if crop:
        word = crop.lower().rstrip("s")
        items = [i for i in items if word in f"{i['title']} {i['summary']}".lower()]
    return {"items": items[: max(1, int(limit))], "source": source}
