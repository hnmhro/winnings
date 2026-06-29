"""Scraper für Gewinnspiel-Portale und RSS-Feeds."""
import logging
import urllib.parse
from datetime import datetime, timezone, timedelta

import feedparser
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9",
}

MAX_ARTICLE_AGE_DAYS = 30


def _parse_published(entry: dict) -> datetime | None:
    """Extrahiert das Veröffentlichungsdatum aus einem feedparser-Eintrag."""
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        t = entry.get(field)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def _is_recent(entry: dict) -> bool:
    """Gibt True zurück wenn der Artikel jünger als MAX_ARTICLE_AGE_DAYS ist."""
    published = _parse_published(entry)
    if published is None:
        return True  # Kein Datum → nicht filtern
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_ARTICLE_AGE_DAYS)
    return published >= cutoff


async def scrape_rss_feed(feed_url: str) -> list[dict]:
    """RSS-Feed mit httpx laden, nach Datum filtern, mit feedparser parsen."""
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            resp = await client.get(feed_url)
            if resp.status_code != 200:
                logger.warning("RSS %s -> HTTP %d", feed_url, resp.status_code)
                return []

        feed = feedparser.parse(resp.text)
        if not feed.entries:
            logger.warning("RSS leer: %s", feed_url)
            return []

        total = len(feed.entries)
        recent = [e for e in feed.entries if _is_recent(e)]
        filtered = total - len(recent)
        if filtered:
            logger.info("RSS %s: %d Einträge (%d zu alt gefiltert)", feed_url, len(recent), filtered)

        return [
            {
                "url": e.get("link", ""),
                "title": e.get("title", ""),
                "published": _parse_published(e).isoformat() if _parse_published(e) else None,
            }
            for e in recent
            if e.get("link") and e["link"].startswith("http")
        ]

    except Exception as exc:
        logger.warning("RSS-Fehler %s: %s", feed_url, exc)
        return []


async def scrape_portal(
    base_url: str,
    link_selector: str,
    title_selector: str | None = None,
) -> list[dict]:
    """Generischer Portal-Scraper mit BeautifulSoup."""
    found = []
    try:
        async with httpx.AsyncClient(
            headers=HEADERS, follow_redirects=True, timeout=20, verify=False
        ) as client:
            resp = await client.get(base_url)
            if resp.status_code != 200:
                logger.warning("Portal %s -> HTTP %d", base_url, resp.status_code)
                return found

        soup = BeautifulSoup(resp.text, "html.parser")
        for link in soup.select(link_selector)[:30]:
            href = link.get("href", "")
            if not href or not href.startswith("http"):
                continue
            title_el = link.select_one(title_selector) if title_selector else link
            title = (title_el or link).get_text(strip=True)
            if title:
                found.append({"url": href, "title": title})

    except Exception as exc:
        logger.warning("Portal nicht erreichbar %s: %s", base_url, exc)

    return found


async def scrape_google_news(query: str) -> list[dict]:
    """Google News RSS – kostenlos, kein API-Key, sehr zuverlässig."""
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=de&gl=DE&ceid=DE:de&after={_cutoff_date()}"
    return await scrape_rss_feed(url)


def _cutoff_date() -> str:
    """Gibt das Cutoff-Datum im Google-News-Format zurück (YYYY-MM-DD)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_ARTICLE_AGE_DAYS)
    return cutoff.strftime("%Y-%m-%d")
