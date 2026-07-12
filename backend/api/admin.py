"""
POST /admin/cleanup — HTTP-triggerable version of `db/cleanup.py`, so a
GitHub Actions cron can sweep idle workspace schemas without SSH/exec access
to the backend host. Guarded by a bearer token (`CLEANUP_TOKEN`), not cookie
auth — this is a service-to-service call, not a browser one.
"""
import os

from fastapi import APIRouter, Header, HTTPException

from db.cleanup import DEFAULT_TTL_DAYS, sweep_expired_workspaces

router = APIRouter()


@router.post("/admin/cleanup")
def cleanup(authorization: str = Header(default="")):
    expected = os.getenv("CLEANUP_TOKEN")
    if not expected:
        raise HTTPException(503, "CLEANUP_TOKEN not configured on this deployment")
    if authorization != f"Bearer {expected}":
        raise HTTPException(401, "Invalid or missing bearer token")

    dsn = os.getenv("WRITE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(500, "DATABASE_URL not set")

    dropped = sweep_expired_workspaces(dsn, DEFAULT_TTL_DAYS)
    return {"swept": len(dropped), "workspace_ids": dropped, "ttl_days": DEFAULT_TTL_DAYS}
