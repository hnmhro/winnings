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
from .sources.portal import scrape_portal, scrape_rss_feed

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("scraper")

REDIS_URL = os.environ["REDIS_URL"]
DATABASE_URL = os.environ["DATABASE_URL"]
MIN_TRUST = float(os.getenv("MIN_TRUST_SCORE", "0.6"))
QUEUE_CONTEST = "queue:contest:found"
TRIGGER_KEY = "trigger:scrape"

SOURCES = [
    {
        "name": "Dein-Gewinn.de RSS",
        "type": "rss",
        "url": "https://www.dein-gewinn.de/feed/",
    },
    {
        "name": "Gewinnspiele-Aktuell RSS",
        "type": "rss",
        "url": "https://www.gewinnspiele-aktuell.de/feed/",
    },
    {
        "name": "Gewinne.de RSS",
        "type": "rss",
        "url": "https://www.gewinne.de/feed/",
    },
    {
        "name": "Meingewinnspiel.de RSS",
        "type": "rss",
        "url": "https://www.meingewinnspiel.de/feed/",
    },
    {
        "name": "Gewinnspiele.eu Portal",
        "type": "portal",
        "url": "https://www.gewinnspiele.eu/",
        "link_selector": "h2.entry-title a, h3.entry-title a, article a",
        "title_selector": None,
    },
    {
        "name": "Preisraetter.de RSS",
        "type": "rss",
        "url": "https://www.preisraetter.de/feed/",
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

    trust = float(result.get("trust_score", 0.0))
    if trust < MIN_TRUST:
        logger.info("Übersprungen (trust=%.2f): %s", trust, url)
        return

    if result.get("skip_reason"):
        logger.info("Übersprungen (%s): %s", result["skip_reason"], url)
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
    found = 0
    for source in SOURCES:
        logger.info("Scrape: %s", source["name"])
        try:
            if source["type"] == "rss":
                candidates = await scrape_rss_feed(source["url"])
            else:
                candidates = await scrape_portal(
                    source["url"],
                    source.get("link_selector", "a"),
                    source.get("title_selector"),
                )
        except Exception as exc:
            logger.error("Fehler bei Quelle %s: %s", source["name"], exc)
            continue

        logger.info("%d Kandidaten von %s", len(candidates), source["name"])
        tasks = [
            process_candidate(redis, db, c["url"], c.get("title", ""), source["name"])
            for c in candidates
            if c.get("url") and c["url"].startswith("http")
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        found += len(tasks)

    logger.info("=== Scrape-Zyklus fertig (%d verarbeitet) ===", found)
    return found


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
