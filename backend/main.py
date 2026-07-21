"""
DataGen web backend — FastAPI app.

Reuses the DataGen engine (core/) unchanged in shape from the CLI project at
universal-sql-agent — only the data layer became schema-per-workspace
Postgres instead of a global SQLite path / DATABASE_URL. See
core/context.py and db/context.py for how that isolation works.
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from api import admin, analysis, chat, health, report, sample, upload, workspace  # noqa: E402
from db.context import WORKSPACE_HEADER  # noqa: E402
from db.registry import ensure_registry_table  # noqa: E402

app = FastAPI(title="DataGen Web Backend", version="0.1.0")

_origins_env = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
_allowed_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Browsers can only read a custom response header if it's whitelisted here.
    # This is how the frontend receives the workspace id to persist in localStorage.
    expose_headers=[WORKSPACE_HEADER],
)


@app.middleware("http")
async def attach_workspace_header(request: Request, call_next):
    """Copy the token stashed by get_workspace() onto the response header.

    Done in middleware (not in get_workspace itself) because headers set on the
    dependency-injected Response are dropped when an endpoint returns its own
    Response — which the SSE endpoints (/chat, /report) do.
    """
    response = await call_next(request)
    token = getattr(request.state, "workspace_token", None)
    if token:
        response.headers[WORKSPACE_HEADER] = token
    return response


@app.on_event("startup")
def on_startup() -> None:
    dsn = os.getenv("WRITE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not dsn:
        return
    try:
        ensure_registry_table(dsn)
    except Exception as e:
        raise RuntimeError(
            "Gagal membuat tabel registry workspace (public.datagen_workspaces). "
            "Role di WRITE_DATABASE_URL (atau DATABASE_URL) butuh izin CREATE pada "
            "schema public DAN pada database — aplikasi ini membuat schema "
            "workspace_<id> secara dinamis per user. Untuk dev lokal, pakai "
            "connection string role 'postgres' bawaan Supabase. Atau jalankan:\n"
            "  GRANT USAGE, CREATE ON SCHEMA public TO <role>;\n"
            "  GRANT CREATE ON DATABASE postgres TO <role>;\n"
            f"Error asli: {e}"
        ) from e


app.include_router(health.router)
app.include_router(upload.router)
app.include_router(sample.router)
app.include_router(chat.router)
app.include_router(report.router)
app.include_router(analysis.router)
app.include_router(workspace.router)
app.include_router(admin.router)
