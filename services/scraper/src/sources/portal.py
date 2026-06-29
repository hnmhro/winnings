"""Scraper für Gewinnspiel-Portale."""
import logging

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


async def scrape_portal(base_url: str, link_selector: str, title_selector: str) -> list[dict]:
    """Generischer Scraper für Gewinnspiel-Portale."""
    found = []
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30) as client:
        try:
            resp = await client.get(base_url)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Portal nicht erreichbar %s: %s", base_url, exc)
            return found

        soup = BeautifulSoup(resp.text, "html.parser")
        for link in soup.select(link_selector)[:20]:
            href = link.get("href", "")
            if href and href.startswith("http"):
                title_el = link.select_one(title_selector) if title_selector else link
                title = title_el.get_text(strip=True) if title_el else href
                found.append({"url": href, "title": title})

    return found


async def scrape_rss_feed(feed_url: str) -> list[dict]:
    """Liest RSS-Feed und extrahiert Gewinnspiel-Links."""
    import feedparser  # type: ignore

    feed = feedparser.parse(feed_url)
    return [
        {"url": entry.get("link", ""), "title": entry.get("title", "")}
        for entry in feed.entries
        if entry.get("link")
    ]
