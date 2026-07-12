# DataGen Web

Production web version of **DataGen** — upload a CSV/Excel file, get an autonomous
data analyst: auto-profiling, natural-language chat over your data, and a
one-click AI-written insight report.

Architecture, phased implementation plan, and free-tier hosting strategy are
specified in [`DataGenWeb.md`](DataGenWeb.md). This is a from-scratch web
implementation in its own repo — it reuses the **engine** (agent loop, SQL
tools, guardrails, profiler, insight-report pipeline) from the CLI project
([`universal-sql-agent`](https://github.com/juan-elf/Database-AI-agent)), not
its UI (Streamlit isn't Vercel-compatible).

```
┌─────────────────────┐     HTTPS / SSE      ┌──────────────────────┐
│  Next.js (Vercel)   │ ──────────────────▶ │  FastAPI backend     │
│  - Upload UI        │                      │  (Railway/Render/Fly)│
│  - Chat (streaming) │ ◀────────────────── │  - reuses DataGen engine
│  - Insight Report    │     JSON / SSE       │  - CSV/Excel ingest  │
└─────────────────────┘                      │  - per-workspace isolation
                                              └──────────┬───────────┘
                                                          │ SQL (schema-per-workspace)
                                                          ▼
                                              ┌────────────────────┐
                                              │ Supabase Postgres  │
                                              └────────────────────┘
```

## Repo layout

```
DataGen/
├── DataGenWeb.md         # full spec: architecture, phases, free-tier hosting
├── backend/               # FastAPI — see backend/README below
│   ├── core/              # DataGen engine, ported to be workspace-scoped
│   │   ├── context.py      # WorkspaceContext + contextvar plumbing (the P1 isolation layer)
│   │   ├── database.py     # Postgres, schema-per-workspace (was SQLite/global DATABASE_URL)
│   │   ├── agent.py        # agent loop — chat_stream() yields SSE-able events
│   │   ├── tools.py        # execute_sql, get_distinct_values, run_analysis, web_search
│   │   ├── profiler.py     # auto data-profiling, cached per workspace schema
│   │   ├── analysis.py     # sandboxed pandas analysis tool
│   │   ├── insight_report.py  # autonomous multi-step analyst pipeline
│   │   ├── guardrails.py   # prompt-injection defense, trust boundary (unchanged from CLI)
│   │   ├── web_search.py   # Tavily web search (unchanged from CLI)
│   │   ├── logger.py       # per-session JSONL logs
│   │   └── ratelimit.py    # in-memory per-workspace rate limiting
│   ├── ingest/             # CSV/Excel → Postgres table (new — web-only concern)
│   │   ├── loader.py        # file → DataFrame (encoding/row/col/size guardrails)
│   │   ├── schema_infer.py  # column/table name sanitization, type inference
│   │   └── ingest.py        # DataFrame → `<workspace_schema>.<table>` via SQLAlchemy
│   ├── db/                 # workspace identity + lifecycle (new — web-only concern)
│   │   ├── context.py       # get_workspace() — cookie-based anonymous identity
│   │   ├── registry.py      # public.datagen_workspaces — tracks every workspace schema
│   │   └── cleanup.py       # TTL sweep — drops idle workspace schemas
│   ├── api/                 # FastAPI routes
│   │   ├── health.py, upload.py, chat.py, report.py, analysis.py, admin.py
│   ├── domains/             # domain packs (battery.md, ecommerce.md — from DataGen)
│   ├── tests/               # DB-free unit tests (guardrails, ingest, context, ratelimit)
│   ├── main.py, requirements.txt, Dockerfile, .env.example
├── frontend/               # Next.js App Router (Vercel)
└── .github/workflows/      # backend tests CI + keep-alive/TTL-sweep cron
```

## Why schema-per-workspace, not a global `DATABASE_URL`

DataGen's CLI engine assumed one process = one database (a global `_db_path` /
`DATABASE_URL`). A web backend serves many users concurrently, so
[`backend/core/context.py`](backend/core/context.py) replaces that global with a
`contextvars.ContextVar` holding a `WorkspaceContext(workspace_id, schema, dsn)`.
`core/database.py`, `core/profiler.py`, etc. call `get_context()` internally —
their function signatures are otherwise unchanged from the CLI version, so the
agent/tools/insight-report code you already know still applies.

Each endpoint (or SSE background thread) explicitly wraps its work in
`with use_context(ctx):` — see the docstring in `core/context.py` for exactly
why this can't be "set once in a FastAPI dependency and left ambient": FastAPI
resolves each sync dependency and the endpoint body via separate threadpool
dispatches, so a contextvar set in one doesn't reliably reach the other, and a
plain generator handed to `StreamingResponse` can resume on a different worker
thread between `yield`s. Both `api/chat.py` and `api/report.py` sidestep this
by running the whole streaming pipeline on one dedicated thread they spawn
themselves, communicating to the HTTP response via a `queue.Queue`.

Workspace identity for the MVP is an anonymous, signed cookie (no login) —
see `db/context.py`'s docstring for how to swap in Supabase Auth later without
touching anything downstream.

## Getting started

### Backend

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env    # fill in OPENROUTER_API_KEY, DATABASE_URL, SECRET_KEY
uvicorn main:app --reload --port 8000
```

`DATABASE_URL` must point at a Postgres instance (Supabase free tier works).
The read role only needs `CONNECT` + the ability to create/use its own
schemas per workspace — see the "Supabase setup" section below for the exact
grants.

Health check: `GET http://localhost:8000/health` and `/health/db`.

### Frontend

```powershell
cd frontend
npm install
copy .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Opens at http://localhost:3000.

## Supabase setup (production database)

1. Create a free Supabase project.
2. Create two Postgres roles (SQL Editor):
   ```sql
   CREATE ROLE agent_reader LOGIN PASSWORD '...';
   CREATE ROLE agent_writer LOGIN PASSWORD '...' CREATEDB;
   GRANT CREATE, USAGE ON SCHEMA public TO agent_writer;
   ```
   Per-workspace schemas are created dynamically by `ingest/ingest.py` — grant
   `agent_reader` `USAGE` + `SELECT` on new schemas via a default privilege:
   ```sql
   ALTER DEFAULT PRIVILEGES FOR ROLE agent_writer IN SCHEMA public
     GRANT SELECT ON TABLES TO agent_reader;
   ```
   (Adjust per your actual schema-creation role — the goal is: `agent_reader`
   can never `INSERT`/`UPDATE`/`DELETE`/`DROP`, only `SELECT`, mirroring
   DataGen's original read-only enforcement.)
3. Set `DATABASE_URL` (agent_reader) and `WRITE_DATABASE_URL` (agent_writer)
   in `backend/.env`.

## Deploying

- **Frontend → Vercel**: `vercel link`, set `NEXT_PUBLIC_API_URL` to the
  deployed backend URL, `vercel deploy --prod`. (Vercel CLI isn't installed
  in this dev environment — install with `npm i -g vercel` to use
  `vercel env pull` / `vercel deploy` / `vercel logs` directly.)
- **Backend → Fly.io / Render / HF Spaces**: build `backend/Dockerfile`.
  Render's free tier sleeps after 15 min idle — `.github/workflows/keepalive.yml`
  pings `/health/db` and triggers `/admin/cleanup` every 10 minutes to prevent
  that and to stop the Supabase free-tier project from pausing after a week
  idle. Set the `BACKEND_URL` and `CLEANUP_TOKEN` repo secrets for it to work.
- **Database → Supabase**: nothing to deploy, just keep it warm (see above).

## Testing

```powershell
cd backend
pytest -v
```

Covers guardrails, ingest (file loading, schema sanitization/type inference),
the workspace context primitive, and the rate limiter — all DB-free. Anything
touching `core/database.py`/`core/profiler.py` end-to-end needs a real
Postgres connection; exercise those manually against a Supabase dev project
(`DATABASE_URL` in `.env`) since no Postgres is available in CI/this sandbox.

## What's implemented vs. deferred

Matches phases P0–P3 of [`DataGenWeb.md`](DataGenWeb.md) fully, P4 (frontend)
with a functional-but-undesigned UI (you have your own design to apply), and
P5 partially:

| Done | Deferred |
|---|---|
| Schema-per-workspace isolation (P1) | Full Supabase Auth (workspace is anonymous-cookie only) |
| CSV/Excel ingest → Postgres (P2) | CSV formula-injection sanitization on **export** (no export feature yet) |
| `/chat`, `/report`, `/analysis` SSE endpoints reusing the DataGen engine (P3) | PDF report export (markdown only) |
| Rate limiting (in-memory, per-workspace) | Redis-backed rate limiting (only needed if scaled to >1 backend instance) |
| Workspace TTL sweep + keep-alive cron | Dashboard for viewing/managing your own workspace's tables directly |
