"""
TTL sweep for idle workspace schemas — keeps the free-tier Supabase instance
from filling up with abandoned anonymous workspaces.

Run it two ways:
  1. `python -m db.cleanup`                — one-shot, e.g. from a GitHub Actions cron
  2. `POST /admin/cleanup` (api/admin.py)   — same sweep, triggered over HTTP,
     guarded by the `CLEANUP_TOKEN` env var
"""
import os

import psycopg2
from dotenv import load_dotenv

from core.database import _parse_connection_url
from db.registry import list_expired, delete_workspace

load_dotenv()

DEFAULT_TTL_DAYS = int(os.getenv("WORKSPACE_TTL_DAYS", "7"))


def sweep_expired_workspaces(dsn: str, ttl_days: int = DEFAULT_TTL_DAYS) -> list[str]:
    """Drop every workspace schema whose last_active_at is older than ttl_days.
    Returns the list of dropped workspace_ids."""
    expired = list_expired(dsn, ttl_days)
    dropped: list[str] = []

    for entry in expired:
        schema = entry["schema_name"]
        conn = psycopg2.connect(**_parse_connection_url(dsn))
        conn.autocommit = True
        try:
            cur = conn.cursor()
            cur.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            cur.close()
        finally:
            conn.close()
        delete_workspace(dsn, entry["workspace_id"])
        dropped.append(entry["workspace_id"])

    return dropped


if __name__ == "__main__":
    write_dsn = os.environ.get("WRITE_DATABASE_URL") or os.environ["DATABASE_URL"]
    dropped_ids = sweep_expired_workspaces(write_dsn)
    print(f"Swept {len(dropped_ids)} expired workspace(s): {dropped_ids}")
