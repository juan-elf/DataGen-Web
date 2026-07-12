"""
Workspace registry — tracks every workspace schema in `public.datagen_workspaces`
so the TTL cleanup sweep (`db/cleanup.py`) knows what exists and how stale it is.

This table lives in the shared `public` schema (not inside any workspace
schema) since it spans all workspaces.
"""
from datetime import datetime, timezone

import psycopg2

from core.database import _parse_connection_url


def _connect(dsn: str):
    conn = psycopg2.connect(**_parse_connection_url(dsn))
    conn.autocommit = True
    return conn


def ensure_registry_table(dsn: str) -> None:
    conn = _connect(dsn)
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.datagen_workspaces (
                workspace_id   TEXT PRIMARY KEY,
                schema_name    TEXT UNIQUE NOT NULL,
                created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                last_active_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        cur.close()
    finally:
        conn.close()


def touch_workspace(dsn: str, workspace_id: str, schema_name: str) -> None:
    """Insert-or-update the workspace's last_active_at (called on every request)."""
    conn = _connect(dsn)
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO public.datagen_workspaces (workspace_id, schema_name, last_active_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (workspace_id)
            DO UPDATE SET last_active_at = EXCLUDED.last_active_at
        """, (workspace_id, schema_name, datetime.now(timezone.utc)))
        cur.close()
    finally:
        conn.close()


def list_expired(dsn: str, ttl_days: int) -> list[dict]:
    conn = _connect(dsn)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT workspace_id, schema_name, last_active_at
            FROM public.datagen_workspaces
            WHERE last_active_at < now() - (%s || ' days')::interval
        """, (ttl_days,))
        rows = cur.fetchall()
        cur.close()
        return [
            {"workspace_id": r[0], "schema_name": r[1], "last_active_at": r[2]}
            for r in rows
        ]
    finally:
        conn.close()


def delete_workspace(dsn: str, workspace_id: str) -> None:
    conn = _connect(dsn)
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM public.datagen_workspaces WHERE workspace_id = %s",
            (workspace_id,),
        )
        cur.close()
    finally:
        conn.close()
