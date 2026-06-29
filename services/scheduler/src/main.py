"""Scheduler Service – koordiniert alle zeitgesteuerten Aufgaben."""
import asyncio
import logging
import os

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("scheduler")

API_BASE = "http://dashboard-backend:8000"


async def trigger(endpoint: str) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            await client.post(f"{API_BASE}{endpoint}")
            logger.info("Ausgelöst: %s", endpoint)
        except Exception as exc:
            logger.warning("Trigger fehlgeschlagen %s: %s", endpoint, exc)


async def job_scrape() -> None:
    logger.info("[JOB] Scrape-Zyklus starten")
    await trigger("/internal/scrape")


async def job_check_email() -> None:
    logger.info("[JOB] E-Mail prüfen")
    await trigger("/internal/check-email")


async def job_cleanup() -> None:
    logger.info("[JOB] Cleanup")
    await trigger("/internal/cleanup")


async def job_weekly_report() -> None:
    logger.info("[JOB] Wochenbericht")
    await trigger("/internal/weekly-report")


async def main() -> None:
    scheduler = AsyncIOScheduler()

    scrape_hours = int(os.getenv("SCRAPE_INTERVAL_HOURS", "6"))
    email_minutes = int(os.getenv("EMAIL_CHECK_INTERVAL_MINUTES", "15"))

    scheduler.add_job(job_scrape, "interval", hours=scrape_hours, id="scrape")
    scheduler.add_job(job_check_email, "interval", minutes=email_minutes, id="email")
    scheduler.add_job(job_cleanup, "cron", hour=3, minute=0, id="cleanup")
    scheduler.add_job(job_weekly_report, "cron", day_of_week="mon", hour=8, id="report")

    scheduler.start()
    logger.info(
        "Scheduler aktiv. Scrape alle %dh, E-Mail alle %dmin.",
        scrape_hours, email_minutes,
    )

    # Scheduler beim Start direkt ausführen
    await job_scrape()
    await job_check_email()

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
