"""Dashboard API – FastAPI Backend."""
import os
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

DATABASE_URL = os.environ.get("DATABASE_URL", "")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    yield
    await app.state.db.close()
    await app.state.redis.aclose()


app = FastAPI(title="Winnings Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/contests")
async def list_contests(status: str | None = None, limit: int = 50, offset: int = 0):
    pool = app.state.db
    if status:
        rows = await pool.fetch(
            """SELECT id, url, title, source, prize_description, estimated_value,
                      deadline, participation_type, trust_score, status,
                      found_at, participated_at
               FROM contests WHERE status = $1
               ORDER BY found_at DESC LIMIT $2 OFFSET $3""",
            status, limit, offset,
        )
    else:
        rows = await pool.fetch(
            """SELECT id, url, title, source, prize_description, estimated_value,
                      deadline, participation_type, trust_score, status,
                      found_at, participated_at
               FROM contests
               ORDER BY found_at DESC LIMIT $1 OFFSET $2""",
            limit, offset,
        )
    return [dict(r) for r in rows]


@app.get("/contests/stats")
async def contest_stats():
    pool = app.state.db
    rows = await pool.fetch(
        "SELECT status, COUNT(*) as count FROM contests GROUP BY status"
    )
    return {r["status"]: r["count"] for r in rows}


@app.get("/emails")
async def list_emails(classification: str | None = None, limit: int = 50):
    pool = app.state.db
    if classification:
        rows = await pool.fetch(
            """SELECT id, subject, sender, classification, win_description,
                      win_value, action_required, action_deadline, notified, received_at
               FROM emails WHERE classification = $1
               ORDER BY received_at DESC LIMIT $2""",
            classification, limit,
        )
    else:
        rows = await pool.fetch(
            """SELECT id, subject, sender, classification, win_description,
                      win_value, action_required, action_deadline, notified, received_at
               FROM emails ORDER BY received_at DESC LIMIT $1""",
            limit,
        )
    return [dict(r) for r in rows]


@app.get("/emails/wins")
async def list_wins():
    pool = app.state.db
    rows = await pool.fetch(
        "SELECT * FROM emails WHERE classification='WIN_NOTIFICATION' ORDER BY received_at DESC"
    )
    return [dict(r) for r in rows]


# Interne Trigger-Endpoints

@app.post("/internal/scrape")
async def trigger_scrape():
    """Weckt den Scraper-Service sofort per Redis-Signal auf."""
    await app.state.redis.lpush("trigger:scrape", "1")
    return {"triggered": "scrape", "message": "Scraper wird gestartet…"}


@app.post("/internal/check-email")
async def trigger_email():
    """Weckt den Email-Manager sofort auf."""
    await app.state.redis.lpush("trigger:email", "1")
    return {"triggered": "check-email", "message": "E-Mail-Check wird gestartet…"}


@app.post("/internal/cleanup")
async def trigger_cleanup():
    pool = app.state.db
    await pool.execute(
        """DELETE FROM contests
           WHERE deadline < NOW() AND status IN ('done','lost','skipped')"""
    )
    return {"triggered": "cleanup"}


@app.delete("/contests/expired")
async def delete_expired_contests():
    """Löscht alle abgelaufenen Gewinnspiele (Deadline vergangen oder älter als 30 Tage)."""
    pool = app.state.db
    result = await pool.fetchval(
        """
        WITH deleted AS (
            DELETE FROM contests
            WHERE
                (deadline IS NOT NULL AND deadline < NOW())
                OR (deadline IS NULL AND found_at < NOW() - INTERVAL '30 days'
                    AND status IN ('found', 'skipped', 'error', 'done', 'lost'))
            RETURNING id
        )
        SELECT COUNT(*) FROM deleted
        """
    )
    return {"deleted": result}


@app.post("/internal/weekly-report")
async def trigger_report():
    return {"triggered": "weekly-report"}
