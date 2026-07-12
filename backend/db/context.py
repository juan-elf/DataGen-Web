"""
`get_workspace()` — the FastAPI dependency that resolves a request's
workspace identity and returns its `WorkspaceContext` (see core/context.py).

Identity model (MVP): anonymous-by-default, backed by a signed cookie.
  - First visit: no valid cookie -> mint a new workspace_id (uuid4 hex),
    sign it, set-cookie it back. Schema = "workspace_<id>".
  - Later visits: cookie verifies -> same workspace_id -> same schema ->
    same uploaded tables are still there.
  - Cookie is signed (itsdangerous) so a client can't forge another
    workspace_id and read someone else's schema.
  - TTL: `db/cleanup.py` drops schemas idle longer than WORKSPACE_TTL_DAYS.

This is intentionally not full user accounts — swapping in Supabase Auth
later means replacing only this file: resolve workspace_id from the verified
Supabase JWT instead of the cookie, keep everything downstream unchanged.

Note: this dependency deliberately does NOT call `core.context.set_context()`.
FastAPI/anyio dispatch each sync dependency and the endpoint body as separate
threadpool calls, so a context set here would not reliably be visible in the
endpoint (see core/context.py's docstring). Endpoints take the returned
`WorkspaceContext` value via `Depends(get_workspace)` and open their own
`with use_context(ctx):` block instead.
"""
import os
import uuid

from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.context import WorkspaceContext
from db.registry import touch_workspace

COOKIE_NAME = "datagen_workspace"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

_SECRET_KEY = os.getenv("SECRET_KEY")
if not _SECRET_KEY:
    _SECRET_KEY = uuid.uuid4().hex
    print(
        "[WARN] SECRET_KEY not set — using an ephemeral key for this process. "
        "Workspace cookies will stop verifying after a restart. "
        "Set SECRET_KEY in backend/.env for stable workspaces."
    )

_serializer = URLSafeTimedSerializer(_SECRET_KEY, salt="datagen-workspace")


def _verify_cookie(token: str) -> str | None:
    try:
        return _serializer.loads(token, max_age=COOKIE_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def _sign_workspace_id(workspace_id: str) -> str:
    return _serializer.dumps(workspace_id)


def _read_dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(503, "Backend misconfigured: DATABASE_URL is not set.")
    return dsn


def _write_dsn() -> str | None:
    return os.getenv("WRITE_DATABASE_URL")


def get_workspace(request: Request, response: Response) -> WorkspaceContext:
    """
    FastAPI dependency: resolves (or mints) the caller's workspace and
    updates its last_active_at for the TTL sweep.

    Deliberately a plain sync function (not async def) — every call inside
    it (psycopg2) is blocking, and FastAPI runs sync dependencies in a
    threadpool automatically.
    """
    cookie_token = request.cookies.get(COOKIE_NAME)
    workspace_id = _verify_cookie(cookie_token) if cookie_token else None

    if workspace_id is None:
        workspace_id = uuid.uuid4().hex
        response.set_cookie(
            COOKIE_NAME,
            _sign_workspace_id(workspace_id),
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=os.getenv("COOKIE_SECURE", "true").lower() == "true",
        )

    schema = f"workspace_{workspace_id}"
    ctx = WorkspaceContext(
        workspace_id=workspace_id,
        schema=schema,
        dsn=_read_dsn(),
        write_dsn=_write_dsn(),
    )

    touch_workspace(ctx.write_dsn or ctx.dsn, workspace_id, schema)
    return ctx
