"""
DataFrame → Postgres table, scoped to the current workspace schema.

Uses SQLAlchemy (`df.to_sql`) purely for the write path — the read/analysis
path (`core/database.py`) stays on raw psycopg2 with an explicit read-only
session, unchanged from DataGen. Keeping ingestion on a separate write
connection/engine mirrors the read/write split DataGen already uses for its
CSV-append feature (`writer.py`), just generalized to "create a new table"
instead of "append to an existing one".
"""
from typing import Any

from sqlalchemy import create_engine, text

from core.context import WorkspaceContext
from ingest.schema_infer import (
    sanitize_columns,
    sanitize_table_name,
    infer_postgres_types,
    try_parse_dates,
)
from ingest.loader import LoadResult

import pandas as pd


def _to_sqlalchemy_dsn(dsn: str) -> str:
    """psycopg2-style postgres:// DSN -> SQLAlchemy's postgresql+psycopg2:// form."""
    if dsn.startswith("postgresql+"):
        return dsn
    if dsn.startswith("postgres://"):
        return "postgresql+psycopg2://" + dsn[len("postgres://"):]
    if dsn.startswith("postgresql://"):
        return "postgresql+psycopg2://" + dsn[len("postgresql://"):]
    return dsn


def _engine_for(ctx: WorkspaceContext):
    dsn = ctx.write_dsn or ctx.dsn
    return create_engine(_to_sqlalchemy_dsn(dsn), pool_pre_ping=True)


def ensure_workspace_schema(ctx: WorkspaceContext) -> None:
    """Create the workspace's Postgres schema if it doesn't exist yet."""
    engine = _engine_for(ctx)
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{ctx.schema}"'))
    engine.dispose()


def ingest_dataframe(
    load_result: LoadResult,
    table_name: str,
    ctx: WorkspaceContext,
    if_exists: str = "fail",
) -> dict[str, Any]:
    """
    Write a loaded DataFrame into `<workspace_schema>.<table_name>`.

    if_exists: "fail" (default, safest for a brand-new upload) | "replace" | "append"
    Returns a summary dict: table, rows, columns, column_mapping, warnings.
    """
    df = try_parse_dates(load_result.df)
    df, mapping = sanitize_columns(df)
    safe_table = sanitize_table_name(table_name)

    ensure_workspace_schema(ctx)
    engine = _engine_for(ctx)
    try:
        df.to_sql(
            safe_table,
            engine,
            schema=ctx.schema,
            if_exists=if_exists,
            index=False,
            chunksize=1000,
            method="multi",
        )
    finally:
        engine.dispose()

    return {
        "table": safe_table,
        "rows": len(df),
        "columns": list(df.columns),
        "column_types": infer_postgres_types(df),
        "column_mapping": mapping.safe_to_original,
        "warnings": load_result.warnings,
    }


def table_exists(table_name: str, ctx: WorkspaceContext) -> bool:
    engine = _engine_for(ctx)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = :schema AND table_name = :table"
                ),
                {"schema": ctx.schema, "table": sanitize_table_name(table_name)},
            ).fetchone()
            return row is not None
    finally:
        engine.dispose()
