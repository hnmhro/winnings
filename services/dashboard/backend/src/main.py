"""Dashboard API – FastAPI Backend."""
import os
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL = os.environ.get("DATABASE_URL", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    yield
    await app.state.db.close()


app = FastAPI(title="Winnings Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/contests")
async def list_contests(status: str | None = None, limit: int = 50, offset: int = 0):
    pool = app.state.db
    where = "WHERE status = $1" if status else ""
    args = [status, limit, offset] if status else [limit, offset]
    limit_placeholder = "$2" if status else "$1"
    offset_placeholder = "$3" if status else "$2"

    query = f"""
        SELECT id, url, title, source, prize_description, estimated_value,
               deadline, participation_type, trust_score, status,
               found_at, participated_at
        FROM contests
        {where}
        ORDER BY found_at DESC
        LIMIT {limit_placeholder} OFFSET {offset_placeholder}
    """
    rows = await pool.fetch(query, *args)
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
    where = "WHERE classification = $1" if classification else ""
    args = [classification, limit] if classification else [limit]
    placeholder = "$2" if classification else "$1"

    query = f"""
        SELECT id, subject, sender, classification, win_description,
               win_value, action_required, action_deadline, notified, received_at
        FROM emails
        {where}
        ORDER BY received_at DESC
        LIMIT {placeholder}
    """
    rows = await pool.fetch(query, *args)
    return [dict(r) for r in rows]


@app.get("/emails/wins")
async def list_wins():
    pool = app.state.db
    rows = await pool.fetch(
        """SELECT * FROM emails WHERE classification='WIN_NOTIFICATION'
           ORDER BY received_at DESC"""
    )
    return [dict(r) for r in rows]


# Interne Trigger-Endpoints (vom Scheduler aufgerufen)
@app.post("/internal/scrape")
async def trigger_scrape():
    return {"triggered": "scrape"}


@app.post("/internal/check-email")
async def trigger_email():
    return {"triggered": "check-email"}


@app.post("/internal/cleanup")
async def trigger_cleanup():
    pool = app.state.db
    deleted = await pool.fetchval(
        "DELETE FROM contests WHERE deadline < NOW() AND status IN ('done','lost','skipped') RETURNING COUNT(*)"
    )
    return {"deleted": deleted}


@app.post("/internal/weekly-report")
async def trigger_report():
    return {"triggered": "weekly-report"}
