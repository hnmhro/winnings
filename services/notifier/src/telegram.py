"""Telegram-Benachrichtigungen."""
import logging
import os

import httpx

logger = logging.getLogger("notifier.telegram")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


async def send_telegram_message(text: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram nicht konfiguriert (BOT_TOKEN oder CHAT_ID fehlt).")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
            })
            resp.raise_for_status()
            logger.info("Telegram-Nachricht gesendet.")
            return True
        except Exception as exc:
            logger.error("Telegram-Fehler: %s", exc)
            return False
