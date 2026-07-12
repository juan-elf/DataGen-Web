"""
PostgreSQL data-layer for the web backend — schema-per-workspace.

Ported from DataGen's dual-engine `database.py`. The web backend only ever
talks to Supabase/Postgres, and the target schema comes from the request's
`WorkspaceContext` (see `core/context.py`) instead of a global `DATABASE_URL`.
Every connection issues `SET search_path TO "<workspace_schema>", public`
right after connecting, so unqualified table names in agent-generated SQL
resolve to that workspace's tables only.
"""
import re
from typing import Any

import psycopg2
import psycopg2.extras

from core.context import get_context
from core.guardrails import wrap_untrusted

FORBIDDEN_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "truncate",
    "create", "replace", "attach", "detach", "grant", "revoke", "vacuum"
]

_DB_ERRORS: tuple = (psycopg2.Error,)
_IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


# ── Connection URL parsing ─────────────────────────────────────────────────────

def _parse_connection_url(url: str) -> dict:
    """
    Parse postgresql://user:pass@host:port/db into psycopg2 kwargs.

    Uses rfind('@') instead of urlparse so passwords containing '@', '[', ']'
    or other special characters work without URL-encoding. Also strips
    accidental bracket-wrapping of the password (common copy-paste from the
    Supabase dashboard, which shows [YOUR-PASSWORD]).
    """
    url = url.strip()
    url = re.sub(r'^postgres(?:ql)?://', '', url)

    at_idx = url.rfind('@')
    if at_idx == -1:
        raise ValueError("Invalid connection URL: missing '@' separator")

    credentials = url[:at_idx]
    host_part = url[at_idx + 1:]

    colon_idx = credentials.find(':')
    if colon_idx == -1:
        raise ValueError("Invalid connection URL: missing ':' in credentials")

    user = credentials[:colon_idx]
    password = credentials[colon_idx + 1:]
    if password.startswith('[') and password.endswith(']'):
        password = password[1:-1]

    m = re.match(r'([^:/?]+):(\d+)/([^?]+)', host_part)
    if not m:
        raise ValueError(f"Invalid connection URL host section: {host_part!r}")

    return {
        "host": m.group(1),
        "port": int(m.group(2)),
        "dbname": m.group(3),
        "user": user,
        "password": password,
    }


def _validate_identifier(name: str, kind: str = "identifier") -> None:
    if not _IDENTIFIER_RE.match(name):
        raise RuntimeError(f"Invalid {kind}: {name!r}")


# ── Connection ────────────────────────────────────────────────────────────────

def get_connection(readonly: bool = True):
    """
    Open a Postgres connection scoped to the current request's workspace
    schema. `readonly=True` (default) uses the read DSN and a read-only
    session — used by every analysis tool. `readonly=False` uses the write
    DSN (ingestion / writer.py) and is never reachable from LLM tool calls.
    """
    ctx = get_context()
    _validate_identifier(ctx.schema, "schema name")

    dsn = ctx.dsn if readonly else (ctx.write_dsn or ctx.dsn)
    conn = psycopg2.connect(**_parse_connection_url(dsn))

    if readonly:
        conn.set_session(readonly=True, autocommit=True)
    else:
        conn.autocommit = False

    cur = conn.cursor()
    cur.execute(f'SET search_path TO "{ctx.schema}", public')
    cur.close()
    return conn


def get_db_label() -> str:
    """Human-readable workspace identifier for the system prompt (no secrets)."""
    return get_context().workspace_id


# ── Schema introspection ──────────────────────────────────────────────────────

def get_table_names() -> list[str]:
    """User table names visible in the current workspace schema."""
    ctx = get_context()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """, (ctx.schema,))
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_schema() -> str:
    """Full schema: tables, columns, types, PKs, FKs, sample rows."""
    ctx = get_context()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """, (ctx.schema,))
        tables = [row[0] for row in cursor.fetchall()]

        if not tables:
            return "(Workspace has no tables yet — upload a CSV/Excel file first.)"

        lines = [f"Workspace has {len(tables)} table(s): {', '.join(tables)}\n"]

        for table in tables:
            lines.append(f"\nTABLE: {table}")

            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (ctx.schema, table))
            for col in cursor.fetchall():
                notnull = " NOT NULL" if col[2] == "NO" else ""
                lines.append(f"  - {col[0]}: {col[1].upper()}{notnull}")

            cursor.execute("""
                SELECT kcu.column_name, ccu.table_name, ccu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s
                    AND tc.table_name = %s
            """, (ctx.schema, table))
            fks = cursor.fetchall()
            if fks:
                lines.append("  Foreign keys:")
                for fk in fks:
                    lines.append(f"    {table}.{fk[0]} -> {fk[1]}.{fk[2]}")

            cursor.execute(f'SELECT * FROM "{table}" LIMIT 2')
            sample_rows = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
            if sample_rows:
                lines.append("  Sample rows:")
                row_strs = []
                for row in sample_rows:
                    row_dict = dict(zip(col_names, row))
                    row_dict = {
                        k: (str(v)[:60] + "..." if len(str(v)) > 60 else v)
                        for k, v in row_dict.items()
                    }
                    row_strs.append(f"    {row_dict}")
                lines.append(wrap_untrusted("\n".join(row_strs), "database_sample_rows"))

        return "\n".join(lines)
    finally:
        conn.close()


# ── Query validation ──────────────────────────────────────────────────────────

def validate_query(sql: str) -> tuple[bool, str | None]:
    """Defense-in-depth validation: whitelist + blacklist + no multi-statement."""
    sql_clean = sql.strip()
    if not sql_clean:
        return False, "Empty query."

    sql_lower = sql_clean.lower()
    if not (sql_lower.startswith("select") or sql_lower.startswith("with")):
        return False, "Query must start with SELECT or WITH. This tool is read-only."

    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(r'\b' + keyword + r'\b', sql_lower):
            return False, f"Keyword '{keyword.upper()}' is not allowed."

    sql_no_strings = re.sub(r"'[^']*'", "''", sql_clean)
    sql_no_strings = re.sub(r'"[^"]*"', '""', sql_no_strings)
    if ";" in sql_no_strings.rstrip(";").rstrip():
        return False, "Multiple statements are not allowed."

    return True, None


# ── Query execution ───────────────────────────────────────────────────────────

def execute_query(sql: str) -> dict[str, Any]:
    """Execute a validated SELECT query and return rows as list of dicts."""
    base = {
        "success": False,
        "rows": None,
        "row_count": 0,
        "columns": None,
        "error": None,
        "hint": None,
        "sql_executed": sql,
    }

    is_valid, validation_error = validate_query(sql)
    if not is_valid:
        return {**base, "error": validation_error}

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        rows_raw = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = [dict(zip(columns, row)) for row in rows_raw]
        return {
            **base,
            "success": True,
            "rows": rows,
            "row_count": len(rows),
            "columns": columns,
        }
    except _DB_ERRORS as e:
        return {
            **base,
            "error": f"SQL Error: {e}",
            "hint": _generate_error_hint(str(e)),
        }
    finally:
        conn.close()


def _generate_error_hint(error_msg: str) -> str:
    """Generate a helpful hint from a Postgres error message."""
    error_lower = error_msg.lower()

    if "column" in error_lower and "does not exist" in error_lower:
        return ("Wrong column name. Check the schema in the system prompt. "
                "Use get_distinct_values to inspect column values.")

    if "relation" in error_lower and "does not exist" in error_lower:
        try:
            tables = get_table_names()
            return f"Wrong table name. Available tables: {', '.join(tables)}."
        except Exception:
            return "Wrong table name. Check the schema in the system prompt."

    if "syntax error" in error_lower:
        return ("Invalid SQL syntax. Remember: this is PostgreSQL. "
                "For monthly grouping use to_char(date_col, 'YYYY-MM').")

    if "ambiguous" in error_lower:
        return ("Ambiguous column name (exists in multiple tables). "
                "Qualify with a table alias, e.g. t1.id instead of id.")

    return "Check the SQL query and try again with a correction."


# ── Distinct values ───────────────────────────────────────────────────────────

def get_distinct_values(table: str, column: str, limit: int = 20) -> dict[str, Any]:
    """Return unique values from a column (safe, identifier-validated)."""
    if not _IDENTIFIER_RE.match(table):
        return {"success": False, "error": f"Invalid table name: '{table}'"}
    if not _IDENTIFIER_RE.match(column):
        return {"success": False, "error": f"Invalid column name: '{column}'"}

    ctx = get_context()
    limit = max(1, min(limit, 100))
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (ctx.schema, table))
        cols_info = cursor.fetchall()
        if not cols_info:
            return {"success": False, "error": f"Table '{table}' not found."}
        col_names = [c[0] for c in cols_info]

        if column not in col_names:
            return {
                "success": False,
                "error": f"Column '{column}' not found in '{table}'. Columns: {col_names}"
            }

        cursor.execute(
            f'SELECT DISTINCT "{column}" FROM "{table}" '
            f'WHERE "{column}" IS NOT NULL ORDER BY "{column}" LIMIT {limit}'
        )
        values = [row[0] for row in cursor.fetchall()]

        cursor.execute(f'SELECT COUNT(DISTINCT "{column}") FROM "{table}"')
        total_distinct = cursor.fetchone()[0]

        return {
            "success": True,
            "table": table,
            "column": column,
            "distinct_values": values,
            "total_distinct": total_distinct,
            "showing": len(values),
        }
    except _DB_ERRORS as e:
        return {"success": False, "error": f"SQL Error: {e}"}
    finally:
        conn.close()
