"""Scraper Service – findet Gewinnspiele, speichert in DB, signalierbar per Redis."""
import asyncio
import json
import logging
import os

import asyncpg
import httpx
import redis.asyncio as aioredis
from bs4 import BeautifulSoup

from .analyzer import analyze_contest
from .sources.portal import scrape_google_news, scrape_portal, scrape_rss_feed

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("scraper")

REDIS_URL = os.environ["REDIS_URL"]
DATABASE_URL = os.environ["DATABASE_URL"]
MIN_TRUST = float(os.getenv("MIN_TRUST_SCORE", "0.6"))
QUEUE_CONTEST = "queue:contest:found"
TRIGGER_KEY = "trigger:scrape"

# Google News RSS – zuverlässig, kein API-Key, auf Deutsch gefiltert
GOOGLE_NEWS_QUERIES = [
    "gewinnspiel jetzt teilnehmen",
    "gewinnspiel mitmachen 2026",
    "verlosung gewinnen kostenlos",
    "preisausschreiben teilnehmen",
    "gewinnspiel sofort teilnehmen",
    "jetzt gewinnen anmelden kostenlos",
    "verlosung kostenlos mitmachen",
    "preisausschreiben 2026 Deutschland",
]

# Reddit RSS – kostenlos, kein API-Key
REDDIT_FEEDS = [
    "https://www.reddit.com/r/Gewinnspiele/.rss",
    "https://www.reddit.com/r/de+Germany+Gewinnspiel/search.rss?q=gewinnspiel&sort=new",
]

SOURCES = [
    # Portale
    {
        "name": "Lottobay.de",
        "type": "portal",
        "url": "https://www.lottobay.de/gewinnspiele/",
        "link_selector": "h2 a, h3 a, .entry-title a, article a",
    },
    {
        "name": "Gewinnarena.de",
        "type": "portal",
        "url": "https://www.gewinnarena.de/",
        "link_selector": "h2 a, h3 a, .contest-title a, article a",
    },
    # Supermärkte & Einzelhandel
    {
        "name": "REWE Gewinnspiele",
        "type": "portal",
        "url": "https://www.rewe.de/gewinnspiele/",
        "link_selector": "a[href*='gewinn'], .teaser a, article a, h2 a, h3 a",
    },
    {
        "name": "Kaufland Gewinnspiele",
        "type": "portal",
        "url": "https://www.kaufland.de/content/service/gewinnspiele/",
        "link_selector": "a[href*='gewinn'], .product-card a, article a, h2 a",
    },
    {
        "name": "Lidl Gewinnspiele",
        "type": "portal",
        "url": "https://www.lidl.de/aktionen/gewinnspiele",
        "link_selector": "a[href*='gewinn'], .offer-item a, article a, h2 a",
    },
    {
        "name": "EDEKA Gewinnspiele",
        "type": "portal",
        "url": "https://www.edeka.de/aktionen/gewinnspiele/",
        "link_selector": "a[href*='gewinn'], .teaser a, article a, h2 a",
    },
    {
        "name": "DM Gewinnspiele",
        "type": "portal",
        "url": "https://www.dm.de/gewinnspiele/",
        "link_selector": "a[href*='gewinn'], .tile a, article a, h2 a",
    },
    {
        "name": "Rossmann Gewinnspiele",
        "type": "portal",
        "url": "https://www.rossmann.de/de/gewinnspiele/",
        "link_selector": "a[href*='gewinn'], .product a, article a, h2 a",
    },
    # Medien & Zeitschriften
    {
        "name": "Brigitte Gewinnspiele",
        "type": "portal",
        "url": "https://www.brigitte.de/gewinnspiele/",
        "link_selector": "h2 a, h3 a, .teaser__headline a, article a",
    },
    {
        "name": "Chefkoch Gewinnspiele",
        "type": "portal",
        "url": "https://www.chefkoch.de/gewinnspiele/",
        "link_selector": "h2 a, h3 a, .ds-teaser-link, article a",
    },
    {
        "name": "RTL Gewinnspiele",
        "type": "portal",
        "url": "https://www.rtl.de/gewinnspiele/",
        "link_selector": "h2 a, h3 a, .teaser a, article a",
    },
    {
        "name": "Stern Gewinnspiele",
        "type": "portal",
        "url": "https://www.stern.de/leben/freizeit/gewinnspiele/",
        "link_selector": "h2 a, h3 a, .article-teaser a, article a",
    },
    {
        "name": "Focus Gewinnspiele",
        "type": "portal",
        "url": "https://www.focus.de/gewinnspiele/",
        "link_selector": "h2 a, h3 a, .teaser a, article a",
    },
    {
        "name": "ProSieben Gewinnspiele",
        "type": "portal",
        "url": "https://www.prosieben.de/gewinnspiele/",
        "link_selector": "h2 a, h3 a, .teaser a, article a, .content-card a",
    },
    {
        "name": "Cosmopolitan Gewinnspiele",
        "type": "portal",
        "url": "https://www.cosmopolitan.de/gewinnspiele/",
        "link_selector": "h2 a, h3 a, .listicle a, article a",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


async def fetch_page_content(url: str) -> str:
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=20) as client:
        resp = await client.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:4000]


async def save_contest_to_db(db: asyncpg.Connection, data: dict) -> bool:
    """Speichert Gewinnspiel direkt in DB. Gibt True zurück wenn neu."""
    row = await db.fetchrow(
        """
        INSERT INTO contests (url, title, source, prize_description, estimated_value,
                              participation_type, trust_score, requirements, status)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'found')
        ON CONFLICT (url) DO NOTHING
        RETURNING id
        """,
        data["url"],
        data.get("title"),
        data.get("source"),
        data.get("prize_description"),
        data.get("estimated_value"),
        data.get("participation_type", "unknown"),
        float(data.get("trust_score", 0)),
        json.dumps(data.get("requirements", [])),
    )
    return row is not None


async def process_candidate(
    redis: aioredis.Redis,
    db: asyncpg.Connection,
    url: str,
    title: str,
    source: str,
) -> None:
    already = await redis.sismember("seen:urls", url)
    if already:
        return
    await redis.sadd("seen:urls", url)
    logger.info("Analysiere: %s", title or url)

    try:
        content = await fetch_page_content(url)
        result = await analyze_contest(url, title, content)
    except Exception as exc:
        logger.warning("Analyse fehlgeschlagen für %s: %s", url, exc)
        return

    if not result.get("is_contest"):
        logger.debug("Kein Gewinnspiel: %s", url)
        return

    if not result.get("is_active", True):
        logger.info("Abgelaufen/beendet (%s): %s", result.get("skip_reason", "inaktiv"), url)
        return

    if result.get("skip_reason"):
        logger.info("Übersprungen (%s): %s", result["skip_reason"], url)
        return

    trust = float(result.get("trust_score", 0.0))
    if trust < MIN_TRUST:
        logger.info("Übersprungen (trust=%.2f): %s", trust, url)
        return

    contest_data = {"url": url, "title": title, "source": source, **result}

    is_new = await save_contest_to_db(db, contest_data)
    if is_new:
        await redis.rpush(QUEUE_CONTEST, json.dumps(contest_data))
        logger.info(
            "NEU (trust=%.2f, ~%s€): %s",
            trust,
            result.get("estimated_value", "?"),
            title or url,
        )
    else:
        logger.debug("Bereits bekannt: %s", url)


async def run_scrape_cycle(redis: aioredis.Redis, db: asyncpg.Connection) -> int:
    logger.info("=== Starte Scrape-Zyklus ===")
    all_candidates: list[tuple[str, str, str]] = []  # (url, title, source)

    # Google News Suchen
    for query in GOOGLE_NEWS_QUERIES:
        logger.info("Google News: '%s'", query)
        try:
            results = await scrape_google_news(query)
            logger.info("  -> %d Treffer", len(results))
            for r in results:
                all_candidates.append((r["url"], r.get("title", ""), f"Google News"))
        except Exception as exc:
            logger.error("Google News Fehler '%s': %s", query, exc)

    # Reddit RSS
    for feed_url in REDDIT_FEEDS:
        logger.info("Reddit RSS: %s", feed_url)
        try:
            results = await scrape_rss_feed(feed_url)
            logger.info("  -> %d Einträge", len(results))
            for r in results:
                all_candidates.append((r["url"], r.get("title", ""), "Reddit"))
        except Exception as exc:
            logger.error("Reddit Fehler: %s", exc)

    # Portal-Quellen
    for source in SOURCES:
        logger.info("Portal: %s", source["name"])
        try:
            candidates = await scrape_portal(
                source["url"],
                source.get("link_selector", "h2 a, h3 a, article a"),
                source.get("title_selector"),
            )
            logger.info("  -> %d Kandidaten", len(candidates))
            for c in candidates:
                all_candidates.append((c["url"], c.get("title", ""), source["name"]))
        except Exception as exc:
            logger.error("Portal Fehler %s: %s", source["name"], exc)

    # Duplikate entfernen
    seen_urls: set[str] = set()
    unique = []
    for url, title, src in all_candidates:
        if url and url.startswith("http") and url not in seen_urls:
            seen_urls.add(url)
            unique.append((url, title, src))

    logger.info("Gesamt: %d einzigartige Kandidaten zur Analyse", len(unique))

    tasks = [process_candidate(redis, db, url, title, src) for url, title, src in unique]
    await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("=== Scrape-Zyklus fertig ===")
    return len(unique)


async def main() -> None:
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    db = await asyncpg.connect(DATABASE_URL)
    interval = int(os.getenv("SCRAPE_INTERVAL_HOURS", "6")) * 3600

    logger.info("Scraper gestartet. Intervall: %dh, MIN_TRUST: %.1f", interval // 3600, MIN_TRUST)

    # Sofort beim Start laufen
    await run_scrape_cycle(redis, db)

    while True:
        # Warte auf manuellen Trigger ODER Ablauf des Intervalls
        logger.info("Warte auf Trigger oder %dh-Intervall...", interval // 3600)
        triggered = await redis.blpop(TRIGGER_KEY, timeout=interval)
        if triggered:
            logger.info("Manueller Trigger empfangen!")
        await run_scrape_cycle(redis, db)


if __name__ == "__main__":
    asyncio.run(main())
