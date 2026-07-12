"""
Schema sanitization + type inference for ingested DataFrames.

Turns arbitrary user column/file names into safe Postgres identifiers before
`to_sql` ever runs, and keeps the original → sanitized mapping so the upload
response can show the user what actually landed in their workspace.
"""
import re
from dataclasses import dataclass, field

import pandas as pd

_IDENTIFIER_RE = re.compile(r'^[a-z_][a-z0-9_]*$')
_RESERVED = {
    "select", "from", "where", "table", "insert", "update", "delete", "drop",
    "order", "group", "user", "column", "index", "primary", "key", "join",
}
MAX_IDENTIFIER_LEN = 63  # Postgres identifier limit


def _sanitize_identifier(raw: str, fallback_prefix: str = "col") -> str:
    name = str(raw).strip().lower()
    name = re.sub(r"[^a-z0-9_]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    if not name or not re.match(r"^[a-z_]", name):
        name = f"{fallback_prefix}_{name}" if name else fallback_prefix
    if name in _RESERVED:
        name = f"{name}_col"
    return name[:MAX_IDENTIFIER_LEN]


def sanitize_table_name(raw: str) -> str:
    name = _sanitize_identifier(raw, fallback_prefix="table")
    return name or "uploaded_table"


@dataclass
class ColumnMapping:
    original_to_safe: dict[str, str] = field(default_factory=dict)
    safe_to_original: dict[str, str] = field(default_factory=dict)


def sanitize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, ColumnMapping]:
    """Rename df's columns to safe, deduplicated Postgres identifiers."""
    mapping = ColumnMapping()
    seen: dict[str, int] = {}
    new_columns: list[str] = []

    for i, col in enumerate(df.columns):
        safe = _sanitize_identifier(col, fallback_prefix=f"col_{i}")
        if safe in seen:
            seen[safe] += 1
            safe = f"{safe}_{seen[safe]}"
        else:
            seen[safe] = 0
        new_columns.append(safe)
        mapping.original_to_safe[str(col)] = safe
        mapping.safe_to_original[safe] = str(col)

    out = df.copy()
    out.columns = new_columns
    return out, mapping


def infer_postgres_types(df: pd.DataFrame) -> dict[str, str]:
    """Map pandas dtypes to Postgres column types (best-effort, used for docs/preview
    only — actual DDL is left to pandas.to_sql/SQLAlchemy's own type mapping)."""
    types: dict[str, str] = {}
    for col in df.columns:
        dtype = df[col].dtype
        if pd.api.types.is_bool_dtype(dtype):
            types[col] = "BOOLEAN"
        elif pd.api.types.is_integer_dtype(dtype):
            types[col] = "BIGINT"
        elif pd.api.types.is_float_dtype(dtype):
            types[col] = "DOUBLE PRECISION"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            types[col] = "TIMESTAMP"
        else:
            types[col] = "TEXT"
    return types


def try_parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Best-effort: convert text columns that look like dates into datetime64.
    Skipped for columns where parsing succeeds on less than 90% of non-null values.

    Checks "not already numeric/bool/datetime" rather than "is object dtype" —
    pandas >= 3.0 defaults CSV string columns to its new `str` extension dtype,
    not the legacy `object` dtype, so an `is_object_dtype` check would silently
    skip every text column and never parse any dates.
    """
    out = df.copy()
    for col in out.columns:
        dtype = out[col].dtype
        if (
            pd.api.types.is_numeric_dtype(dtype)
            or pd.api.types.is_bool_dtype(dtype)
            or pd.api.types.is_datetime64_any_dtype(dtype)
        ):
            continue
        non_null = out[col].dropna()
        if non_null.empty:
            continue
        parsed = pd.to_datetime(non_null, errors="coerce", format="mixed")
        if parsed.notna().mean() >= 0.9:
            out[col] = pd.to_datetime(out[col], errors="coerce", format="mixed")
    return out
