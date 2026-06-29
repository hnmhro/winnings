"""Scraper für Gewinnspiel-Portale und RSS-Feeds."""
import logging

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


async def scrape_rss_feed(feed_url: str) -> list[dict]:
    """RSS-Feed mit httpx laden (User-Agent), dann mit feedparser parsen."""
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            resp = await client.get(feed_url)
            if resp.status_code != 200:
                logger.warning("RSS %s -> HTTP %d", feed_url, resp.status_code)
                return []
            content = resp.text

        feed = feedparser.parse(content)
        entries = feed.entries

        if not entries:
            logger.warning("RSS leer oder kein gültiges Format: %s", feed_url)
            return []

        results = [
            {"url": e.get("link", ""), "title": e.get("title", "")}
            for e in entries
            if e.get("link") and e["link"].startswith("http")
        ]
        logger.info("RSS %s: %d Einträge", feed_url, len(results))
        return results

    except Exception as exc:
        logger.warning("RSS-Fehler %s: %s", feed_url, exc)
        return []


async def scrape_portal(
    base_url: str,
    link_selector: str,
    title_selector: str | None,
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
    import urllib.parse
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=de&gl=DE&ceid=DE:de"
    return await scrape_rss_feed(url)
