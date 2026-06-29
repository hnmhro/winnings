"""Notifier Service – sendet Benachrichtigungen bei Gewinnen."""
import asyncio
import json
import logging
import os

import redis.asyncio as aioredis

from .telegram import send_telegram_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("notifier")

REDIS_URL = os.environ["REDIS_URL"]
QUEUE_NOTIFY = "queue:notify"


def format_win_message(data: dict) -> str:
    lines = [
        "GEWINN ERKANNT!",
        "",
        f"Betreff: {data.get('subject', 'Unbekannt')}",
        f"Absender: {data.get('sender', 'Unbekannt')}",
    ]
    if data.get("win_description"):
        lines.append(f"Gewinn: {data['win_description']}")
    if data.get("win_value"):
        lines.append(f"Wert: ca. {data['win_value']:.0f} EUR")
    if data.get("action_required"):
        lines.append(f"Aktion erforderlich: {data['action_required']}")
    if data.get("action_deadline"):
        lines.append(f"Frist: {data['action_deadline']}")
    return "\n".join(lines)


async def process_notifications(redis: aioredis.Redis) -> None:
    logger.info("Notifier gestartet, warte auf Benachrichtigungen...")
    while True:
        raw = await redis.blpop(QUEUE_NOTIFY, timeout=30)
        if not raw:
            continue

        _, payload = raw
        data = json.loads(payload)
        msg_type = data.get("type", "INFO")

        if msg_type == "WIN":
            text = format_win_message(data)
            logger.info("Sende Gewinn-Benachrichtigung!")
            await send_telegram_message(text)
        else:
            logger.info("Benachrichtigung: %s", data)


async def main() -> None:
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    await process_notifications(redis)


if __name__ == "__main__":
    asyncio.run(main())
