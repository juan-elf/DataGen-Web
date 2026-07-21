"""
DELETE /workspace — drop everything the caller uploaded, on demand.

The TTL sweep (db/cleanup.py) already removes idle workspaces after
WORKSPACE_TTL_DAYS, but "it'll be gone in a week" is a promise, not a control.
This gives a visitor an immediate, verifiable way to remove their data — which
is the honest answer to "why should I upload anything to your server?".

Safe by construction: there is no workspace id parameter. The schema dropped is
always the caller's own, derived from their signed token by get_workspace().
"""
import re

import psycopg2
from fastapi import APIRouter, Depends, HTTPException

from api.chat import evict_agent
from core.context import WorkspaceContext
from core.database import _parse_connection_url
from core.profiler import invalidate_profile_cache
from db.context import get_workspace
from db.registry import delete_workspace as registry_delete_workspace

router = APIRouter()

_SCHEMA_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@router.delete("/workspace")
def delete_my_workspace(ctx: WorkspaceContext = Depends(get_workspace)):
    # The schema name is derived from a token we signed, so it can't be forged —
    # but this is interpolated into DDL, so validate it anyway (defense in depth).
    if not _SCHEMA_RE.match(ctx.schema):
        raise HTTPException(400, "Invalid workspace schema.")

    dsn = ctx.write_dsn or ctx.dsn
    try:
        conn = psycopg2.connect(**_parse_connection_url(dsn))
        conn.autocommit = True
        try:
            cur = conn.cursor()
            cur.execute(f'DROP SCHEMA IF EXISTS "{ctx.schema}" CASCADE')
            cur.close()
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(500, f"Failed to delete workspace: {type(e).__name__}: {e}")

    registry_delete_workspace(dsn, ctx.workspace_id)
    invalidate_profile_cache(ctx.schema)
    evict_agent(ctx.workspace_id)

    return {"success": True, "deleted_workspace": ctx.workspace_id}
