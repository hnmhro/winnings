"""Participant Service – nimmt automatisch an Gewinnspielen teil."""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis
from playwright.async_api import async_playwright

from .browser import fill_contest_form
from .captcha import solve_captcha

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("participant")

REDIS_URL = os.environ["REDIS_URL"]
DATABASE_URL = os.environ["DATABASE_URL"]
QUEUE_IN = "queue:contest:found"
QUEUE_NOTIFY = "queue:notify"
MAX_PER_DAY = int(os.getenv("MAX_PARTICIPATIONS_PER_DAY", "50"))

PROFILE = {
    "first_name": os.getenv("PROFILE_FIRST_NAME", ""),
    "last_name": os.getenv("PROFILE_LAST_NAME", ""),
    "email": os.getenv("EMAIL_ADDRESS", ""),
    "birth_date": os.getenv("PROFILE_BIRTH_DATE", ""),
    "street": os.getenv("PROFILE_STREET", ""),
    "city": os.getenv("PROFILE_CITY", ""),
    "zip": os.getenv("PROFILE_ZIP", ""),
    "country": os.getenv("PROFILE_COUNTRY", "DE"),
    "phone": os.getenv("PROFILE_PHONE", ""),
}


async def save_contest(db: asyncpg.Connection, data: dict) -> str | None:
    row = await db.fetchrow(
        """
        INSERT INTO contests (url, title, source, prize_description, estimated_value,
                              participation_type, trust_score, requirements, status)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'queued')
        ON CONFLICT (url) DO NOTHING
        RETURNING id::text
        """,
        data["url"], data.get("title"), data.get("source"),
        data.get("prize_description"), data.get("estimated_value"),
        data.get("participation_type", "unknown"), data.get("trust_score", 0),
        json.dumps(data.get("requirements", [])),
    )
    return row["id"] if row else None


async def record_participation(db: asyncpg.Connection, contest_id: str, success: bool, error: str | None = None) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        "UPDATE contests SET status=$1, participated_at=$2 WHERE id=$3",
        "done" if success else "error", now, contest_id,
    )
    await db.execute(
        "INSERT INTO participations (contest_id, method, success, error_message) VALUES ($1,'form',$2,$3)",
        contest_id, success, error,
    )


async def check_daily_limit(redis: aioredis.Redis) -> bool:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"counter:participations:{today}"
    count = int(await redis.get(key) or 0)
    return count < MAX_PER_DAY


async def increment_counter(redis: aioredis.Redis) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"counter:participations:{today}"
    await redis.incr(key)
    await redis.expire(key, 86400 * 2)


async def process_queue(redis: aioredis.Redis, db: asyncpg.Connection) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        while True:
            raw = await redis.blpop(QUEUE_IN, timeout=30)
            if not raw:
                continue

            _, payload = raw
            data = json.loads(payload)

            if not await check_daily_limit(redis):
                logger.warning("Tageslimit erreicht, überspringe %s", data["url"])
                await asyncio.sleep(3600)
                continue

            contest_id = await save_contest(db, data)
            if not contest_id:
                logger.info("Bereits bekannt: %s", data["url"])
                continue

            logger.info("Nehme teil: %s", data.get("title", data["url"]))
            try:
                page = await browser.new_page()
                success = await fill_contest_form(page, data["url"], PROFILE, solve_captcha)
                await page.close()
                await record_participation(db, contest_id, success)
                await increment_counter(redis)
                logger.info("Teilnahme %s: %s", "erfolgreich" if success else "fehlgeschlagen", data["url"])
            except Exception as exc:
                logger.error("Fehler bei Teilnahme %s: %s", data["url"], exc)
                await record_participation(db, contest_id, False, str(exc))

        await browser.close()


async def main() -> None:
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    db = await asyncpg.connect(DATABASE_URL)
    logger.info("Participant Service gestartet.")
    await process_queue(redis, db)


if __name__ == "__main__":
    asyncio.run(main())
