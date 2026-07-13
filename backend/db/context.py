"""
`get_workspace()` — the FastAPI dependency that resolves a request's
workspace identity and returns its `WorkspaceContext` (see core/context.py).

Identity model (MVP): anonymous-by-default, backed by a signed token.
  - First visit: no valid token -> mint a new workspace_id (uuid4 hex),
    sign it, and hand it back to the client. Schema = "workspace_<id>".
  - Later visits: the client echoes the token -> same workspace_id -> same
    schema -> the same uploaded tables are still there.
  - Token is signed (itsdangerous) so a client can't forge another
    workspace_id and read someone else's schema.
  - TTL: `db/cleanup.py` drops schemas idle longer than WORKSPACE_TTL_DAYS.

Transport: the token travels in the `X-Workspace-Id` request/response header
(the frontend persists it in localStorage), NOT a cookie. Reason: the frontend
(Vercel) and backend (Render) live on different registrable domains, which
makes every browser `fetch` a *cross-site* request. A `SameSite=Lax` cookie is
never sent on cross-site fetches (in any browser, not just Safari), and a
`SameSite=None` third-party cookie is blocked outright by Safari's ITP — so a
cookie can't carry identity here. A request header set from first-party
localStorage sidesteps all of that and works everywhere. A cookie is still set
as a bonus so a future same-site deployment (custom domain, api.<domain>) keeps
working with zero changes; cross-site it's simply ignored.

This is intentionally not full user accounts — swapping in Supabase Auth
later means replacing only this file: resolve workspace_id from the verified
Supabase JWT instead of the token, keep everything downstream unchanged.

Note: this dependency deliberately does NOT call `core.context.set_context()`.
FastAPI/anyio dispatch each sync dependency and the endpoint body as separate
threadpool calls, so a context set here would not reliably be visible in the
endpoint (see core/context.py's docstring). Endpoints take the returned
`WorkspaceContext` value via `Depends(get_workspace)` and open their own
`with use_context(ctx):` block instead.

The freshly-signed token is stashed on `request.state.workspace_token`; a
middleware in main.py copies it onto the `X-Workspace-Id` response header for
every response (including the StreamingResponse ones — headers set on the
injected `Response` are dropped when an endpoint returns its own Response).
"""
import os
import uuid

from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.context import WorkspaceContext
from db.registry import touch_workspace

COOKIE_NAME = "datagen_workspace"
WORKSPACE_HEADER = "X-Workspace-Id"
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


def _verify_token(token: str) -> str | None:
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
    # Prefer the header (cross-site friendly); fall back to the cookie so a
    # same-site custom-domain deployment keeps working with zero client changes.
    token = request.headers.get(WORKSPACE_HEADER) or request.cookies.get(COOKIE_NAME)
    workspace_id = _verify_token(token) if token else None

    if workspace_id is None:
        workspace_id = uuid.uuid4().hex

    signed = _sign_workspace_id(workspace_id)

    # Hand the (re-signed, so its sliding expiry refreshes) token back to the
    # client. request.state is picked up by the middleware in main.py and copied
    # onto the X-Workspace-Id response header, which works even for the
    # StreamingResponse endpoints. The cookie is a same-site-only bonus.
    request.state.workspace_token = signed
    response.set_cookie(
        COOKIE_NAME,
        signed,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite=os.getenv("COOKIE_SAMESITE", "lax"),
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
