"""Email Manager – überwacht Postfach und erkennt Gewinn-Benachrichtigungen."""
import asyncio
import email
import json
import logging
import os
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis
from imapclient import IMAPClient

from .classifier import classify_email

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("email-manager")

REDIS_URL = os.environ["REDIS_URL"]
DATABASE_URL = os.environ["DATABASE_URL"]
QUEUE_NOTIFY = "queue:notify"

IMAP_HOST = os.environ["EMAIL_IMAP_HOST"]
IMAP_PORT = int(os.getenv("EMAIL_IMAP_PORT", "993"))
EMAIL_ADDR = os.environ["EMAIL_ADDRESS"]
EMAIL_PASS = os.environ["EMAIL_PASSWORD"]
CHECK_INTERVAL = int(os.getenv("EMAIL_CHECK_INTERVAL_SECONDS", "900"))


def get_email_body(msg: email.message.Message) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body += part.get_payload(decode=True).decode("utf-8", errors="replace")
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
    return body[:3000]


async def process_message(
    redis: aioredis.Redis,
    db: asyncpg.Connection,
    uid: int,
    raw: bytes,
) -> None:
    msg = email.message_from_bytes(raw)
    message_id = msg.get("Message-ID", str(uid))
    subject = msg.get("Subject", "(kein Betreff)")
    sender = msg.get("From", "")
    body = get_email_body(msg)

    already = await db.fetchval("SELECT id FROM emails WHERE message_id=$1", message_id)
    if already:
        return

    logger.info("Klassifiziere: %s von %s", subject, sender)
    result = await classify_email(subject, sender, body)
    classification = result.get("classification", "UNKNOWN")

    await db.execute(
        """
        INSERT INTO emails (message_id, subject, sender, classification,
                            win_description, win_value, action_required,
                            action_deadline, raw_body)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        ON CONFLICT (message_id) DO NOTHING
        """,
        message_id, subject, sender, classification,
        result.get("win_description"), result.get("win_value"),
        result.get("action_required"), result.get("action_deadline"),
        body,
    )

    if classification == "WIN_NOTIFICATION":
        logger.info("GEWINN ERKANNT: %s – %s", subject, result.get("win_description"))
        await redis.rpush(QUEUE_NOTIFY, json.dumps({
            "type": "WIN",
            "subject": subject,
            "sender": sender,
            "win_description": result.get("win_description"),
            "win_value": result.get("win_value"),
            "action_required": result.get("action_required"),
            "action_deadline": result.get("action_deadline"),
        }))


async def check_inbox(redis: aioredis.Redis, db: asyncpg.Connection) -> None:
    logger.info("Prüfe Postfach...")
    try:
        with IMAPClient(IMAP_HOST, port=IMAP_PORT, ssl=True) as imap:
            imap.login(EMAIL_ADDR, EMAIL_PASS)
            imap.select_folder("INBOX")
            uids = imap.search(["UNSEEN"])
            logger.info("%d ungelesene E-Mails", len(uids))
            if uids:
                messages = imap.fetch(uids, ["RFC822"])
                for uid, data in messages.items():
                    await process_message(redis, db, uid, data[b"RFC822"])
    except Exception as exc:
        logger.error("IMAP-Fehler: %s", exc)


async def main() -> None:
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    db = await asyncpg.connect(DATABASE_URL)
    logger.info("Email Manager gestartet. Prüfe alle %ds.", CHECK_INTERVAL)

    await check_inbox(redis, db)

    while True:
        triggered = await redis.blpop("trigger:email", timeout=CHECK_INTERVAL)
        if triggered:
            logger.info("Manueller Trigger empfangen!")
        await check_inbox(redis, db)


if __name__ == "__main__":
    asyncio.run(main())
