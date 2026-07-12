"""
DataGen web backend — FastAPI app.

Reuses the DataGen engine (core/) unchanged in shape from the CLI project at
universal-sql-agent — only the data layer became schema-per-workspace
Postgres instead of a global SQLite path / DATABASE_URL. See
core/context.py and db/context.py for how that isolation works.
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from api import admin, analysis, chat, health, report, upload  # noqa: E402
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
)


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
app.include_router(chat.router)
app.include_router(report.router)
app.include_router(analysis.router)
app.include_router(admin.router)
