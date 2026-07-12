"""
Auto data-profiling for the current request's workspace schema.

profile_database() runs once per workspace and caches results.
Results are injected into the agent's system prompt so the model has
row counts, value ranges, and cardinality without using tool calls.

Cache key: workspace schema name (not just the DSN — a shared Postgres
instance hosts many workspace schemas, so the DSN alone would leak one
workspace's profile into another's prompt). Invalidated via force=True
after an ingest/upload adds or changes tables.

Ported from DataGen (universal-sql-agent/profiler.py); Postgres-only branch
kept, SQLite branch dropped (web backend is Postgres/Supabase only).
"""
import time
from typing import Any

from core.context import get_context
from core.database import get_connection

CATEGORICAL_THRESHOLD = 20
MAX_STAT_ROWS = 100_000

_cache: dict[str, dict] = {}


# ── Public API ────────────────────────────────────────────────────────────────

def profile_database(force: bool = False) -> dict[str, Any]:
    """Profile all tables in the current workspace schema. Cached; force=True to regenerate."""
    key = get_context().schema
    if not force and key in _cache:
        return _cache[key]
    profile = _build_profile()
    _cache[key] = profile
    return profile


def invalidate_profile_cache(schema: str | None = None) -> None:
    """Drop the cached profile for a workspace (call after ingest changes tables)."""
    key = schema or get_context().schema
    _cache.pop(key, None)


# ── Build ─────────────────────────────────────────────────────────────────────

def _build_profile() -> dict[str, Any]:
    conn = get_connection()
    try:
        tables = _get_table_names(conn)
        profile: dict[str, Any] = {"tables": {}, "generated_at": time.time()}
        for table in tables:
            profile["tables"][table] = _profile_table(conn, table)
        return profile
    finally:
        conn.close()


def _get_table_names(conn) -> list[str]:
    schema = get_context().schema
    cursor = conn.cursor()
    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = %s AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """, (schema,))
    return [row[0] for row in cursor.fetchall()]


def _get_column_meta(conn, table: str) -> list[dict]:
    """Return [{"name": ..., "declared_type": ...}, ...]."""
    schema = get_context().schema
    cursor = conn.cursor()
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    """, (schema, table))
    return [
        {"name": row[0], "declared_type": _pg_type_to_declared(row[1])}
        for row in cursor.fetchall()
    ]


def _pg_type_to_declared(pg_type: str) -> str:
    """Normalize a Postgres data_type string to the declared-type used by is_numeric check."""
    pg = pg_type.upper()
    if any(t in pg for t in ("INT", "SERIAL")):
        return "INTEGER"
    if any(t in pg for t in ("REAL", "FLOAT", "DOUBLE", "NUMERIC", "DECIMAL", "PRECISION")):
        return "REAL"
    return "TEXT"


def _profile_table(conn, table: str) -> dict[str, Any]:
    cursor = conn.cursor()
    cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
    row_count: int = cursor.fetchone()[0]

    col_meta = _get_column_meta(conn, table)
    skip_stats = row_count > MAX_STAT_ROWS

    columns: dict[str, Any] = {}
    for col_info in col_meta:
        col_name = col_info["name"]
        declared_type = col_info["declared_type"]
        columns[col_name] = _profile_column(
            conn, table, col_name, declared_type, row_count, skip_stats
        )

    return {"row_count": row_count, "columns": columns}


def _profile_column(
    conn,
    table: str,
    column: str,
    declared_type: str,
    row_count: int,
    skip_stats: bool,
) -> dict[str, Any]:
    base: dict[str, Any] = {"declared_type": declared_type}

    if skip_stats or row_count == 0:
        base["skipped"] = True
        return base

    c = f'"{column}"'
    t = f'"{table}"'
    cursor = conn.cursor()

    cursor.execute(
        f'SELECT COUNT(*) - COUNT({c}) AS nulls, COUNT(DISTINCT {c}) AS dist FROM {t}'
    )
    row = cursor.fetchone()
    null_count: int = row[0]
    distinct_count: int = row[1]
    null_pct = round(100.0 * null_count / row_count, 1) if row_count > 0 else 0.0

    base["null_pct"] = null_pct
    base["distinct_count"] = distinct_count

    is_numeric = any(
        kw in declared_type
        for kw in ("INT", "REAL", "FLOAT", "DOUBLE", "NUM", "DECIMAL")
    )

    if is_numeric:
        base["semantic_type"] = "numeric"
        # Postgres has no ROUND(double precision, int) overload — needs an
        # explicit ::numeric cast.
        cursor.execute(f'SELECT MIN({c}), MAX({c}), ROUND(AVG({c})::numeric, 4) FROM {t}')
        r = cursor.fetchone()
        if r:
            base["min"] = r[0]
            base["max"] = r[1]
            base["mean"] = r[2]
    elif distinct_count <= CATEGORICAL_THRESHOLD:
        base["semantic_type"] = "categorical"
        cursor.execute(
            f'SELECT DISTINCT {c} FROM {t} WHERE {c} IS NOT NULL ORDER BY {c} LIMIT 20'
        )
        base["sample_values"] = [r[0] for r in cursor.fetchall()]
    else:
        base["semantic_type"] = "text"

    return base


# ── Formatting ────────────────────────────────────────────────────────────────

def _fmt(v: Any) -> str:
    if v is None:
        return "?"
    if isinstance(v, float) and v == int(v) and abs(v) < 1e10:
        return str(int(v))
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def format_profile_for_prompt(profile: dict[str, Any]) -> str:
    """Compact single-line-per-column text for system prompt injection."""
    if not profile or not profile.get("tables"):
        return "(No tables yet — upload a CSV/Excel file first.)"

    lines: list[str] = []
    for table, tinfo in profile["tables"].items():
        row_count = tinfo.get("row_count", "?")
        count_str = f"{row_count:,}" if isinstance(row_count, int) else str(row_count)
        lines.append(f"\n{table}  ({count_str} rows)")

        for col_name, cinfo in tinfo.get("columns", {}).items():
            dtype = cinfo.get("declared_type", "")
            prefix = f"  {col_name:<24} {dtype:<8}"

            if cinfo.get("skipped"):
                lines.append(prefix + " (large table -- stats skipped)")
                continue

            stype = cinfo.get("semantic_type", "")
            distinct = cinfo.get("distinct_count", "?")
            null_pct = cinfo.get("null_pct", 0.0)

            line = prefix
            if stype == "numeric":
                mn, mx, mean = cinfo.get("min"), cinfo.get("max"), cinfo.get("mean")
                line += f" |range: {_fmt(mn)}-{_fmt(mx)} |mean: {_fmt(mean)}"
            elif stype == "categorical":
                vals = cinfo.get("sample_values", [])
                line += f" |values: {', '.join(str(v) for v in vals)}"
            line += f" |distinct: {distinct}"
            if null_pct > 0:
                line += f" |nulls: {null_pct}%"

            lines.append(line)

    return "\n".join(lines)
