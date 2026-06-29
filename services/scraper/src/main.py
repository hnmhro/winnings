"""Scraper Service – findet Gewinnspiele und stellt sie in die Queue."""
import asyncio
import json
import logging
import os

import httpx
import redis.asyncio as aioredis
from bs4 import BeautifulSoup

from .analyzer import analyze_contest
from .sources.portal import scrape_portal, scrape_rss_feed

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("scraper")

REDIS_URL = os.environ["REDIS_URL"]
MIN_TRUST = float(os.getenv("MIN_TRUST_SCORE", "0.7"))
QUEUE_CONTEST = "queue:contest:found"

SOURCES = [
    {
        "name": "Lottobay RSS",
        "type": "rss",
        "url": "https://www.lottobay.de/feed/",
    },
    {
        "name": "Gewinnspiele.de",
        "type": "portal",
        "url": "https://www.gewinnspiele.de/aktuelle-gewinnspiele/",
        "link_selector": "article a.entry-title-link",
        "title_selector": None,
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
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:4000]


async def process_contest_candidate(redis: aioredis.Redis, url: str, title: str, source: str) -> None:
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
        return

    trust = result.get("trust_score", 0.0)
    if trust < MIN_TRUST:
        logger.info("Übersprungen (trust=%.2f): %s", trust, url)
        return

    if result.get("skip_reason"):
        logger.info("Übersprungen (%s): %s", result["skip_reason"], url)
        return

    message = {
        "url": url,
        "title": title,
        "source": source,
        **result,
    }
    await redis.rpush(QUEUE_CONTEST, json.dumps(message))
    logger.info("Gefunden (trust=%.2f, ~%s€): %s", trust, result.get("estimated_value"), title)


async def run_scrape_cycle(redis: aioredis.Redis) -> None:
    logger.info("Starte Scrape-Zyklus...")
    for source in SOURCES:
        logger.info("Scrape Quelle: %s", source["name"])
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

        tasks = [
            process_contest_candidate(redis, c["url"], c["title"], source["name"])
            for c in candidates if c.get("url")
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("Scrape-Zyklus abgeschlossen.")


async def main() -> None:
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    interval = int(os.getenv("SCRAPE_INTERVAL_HOURS", "6")) * 3600

    while True:
        await run_scrape_cycle(redis)
        logger.info("Nächster Zyklus in %dh", interval // 3600)
        await asyncio.sleep(interval)


if __name__ == "__main__":
    asyncio.run(main())
