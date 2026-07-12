"""
Request-scoped workspace context.

Replaces DataGen's module-level `_db_path` / `DATABASE_URL` singleton with a
`contextvars.ContextVar`, so `core/*` (database, profiler, agent, ...) keeps
calling a plain module-level `get_context()` instead of every function taking
a connection/schema argument.

Important: this is NOT wired up as "ambient state set once per request by a
FastAPI dependency and implicitly visible everywhere downstream". FastAPI/
anyio dispatches each sync dependency and the endpoint body via separate
threadpool calls, each of which gets its own *copy* of the calling context —
a `.set()` done inside a `yield`-dependency does not propagate to the
endpoint function, and does not survive across a streaming generator's
per-`next()` dispatch either. So every entry point that calls into `core/*`
(an endpoint body, or a background thread backing an SSE stream) must wrap
its own work in `with use_context(ctx):` itself — see api/*.py for the
pattern. Within a single synchronous call stack this behaves exactly like
ordinary thread-local state.
"""
import contextvars
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceContext:
    workspace_id: str
    schema: str          # Postgres schema name, e.g. "workspace_ab12cd34"
    dsn: str              # Postgres connection string (read role)
    write_dsn: str | None = None  # only set when the write path is enabled


_current: contextvars.ContextVar[WorkspaceContext | None] = contextvars.ContextVar(
    "workspace_context", default=None
)


def set_context(ctx: WorkspaceContext) -> contextvars.Token:
    return _current.set(ctx)


def reset_context(token: contextvars.Token) -> None:
    _current.reset(token)


def get_context() -> WorkspaceContext:
    ctx = _current.get()
    if ctx is None:
        raise RuntimeError(
            "No workspace context set on this thread. "
            "Wrap this call in `with use_context(ctx):` at the top of the "
            "endpoint or worker thread — see api/*.py."
        )
    return ctx


@contextmanager
def use_context(ctx: WorkspaceContext):
    """Set the workspace context for the duration of a `with` block, on the
    calling thread only. Use this at the top of every endpoint body and every
    background worker thread that touches `core/*` — see module docstring."""
    token = set_context(ctx)
    try:
        yield ctx
    finally:
        reset_context(token)
