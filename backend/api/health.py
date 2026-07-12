"""
Health check endpoints.

`GET /health` is cheap (no DB) — used by uptime checks.
`GET /health/db` also runs `SELECT 1` against Postgres — this is the one a
keep-alive cron should hit periodically, since Supabase free-tier projects
pause after a week of no activity (see DataGenWeb.md §8).
"""
import os

import psycopg2
from fastapi import APIRouter

from core.database import _parse_connection_url

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/db")
def health_db():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        return {"status": "error", "detail": "DATABASE_URL not set"}
    try:
        conn = psycopg2.connect(**_parse_connection_url(dsn))
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        finally:
            conn.close()
        return {"status": "ok", "db": "reachable"}
    except Exception as e:
        return {"status": "error", "detail": f"{type(e).__name__}: {e}"}
