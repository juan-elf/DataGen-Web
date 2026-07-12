"""
File → DataFrame loader for the /upload endpoint.

Supports CSV and Excel (.xlsx/.xls). Robust to encoding issues and malformed
rows since this is untrusted, user-uploaded content — never let a single bad
row or bad byte 500 the whole request.
"""
import io
from dataclasses import dataclass

import pandas as pd

MAX_UPLOAD_BYTES = 15 * 1024 * 1024   # 15MB — direct-to-backend upload ceiling (free tier)
MAX_ROWS = 500_000
MAX_COLUMNS = 200

_CSV_ENCODINGS = ("utf-8", "utf-8-sig", "latin-1")


class LoadError(Exception):
    """Raised when the uploaded file can't be parsed or violates a size/shape limit."""


@dataclass
class LoadResult:
    df: pd.DataFrame
    warnings: list[str]


def _read_csv_bytes(raw: bytes) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in _CSV_ENCODINGS:
        try:
            return pd.read_csv(
                io.BytesIO(raw),
                encoding=encoding,
                on_bad_lines="skip",
                sep=None,
                engine="python",
            )
        except (UnicodeDecodeError, pd.errors.ParserError) as e:
            last_error = e
            continue
    raise LoadError(f"Could not parse CSV with any known encoding: {last_error}")


def _read_excel_bytes(raw: bytes) -> pd.DataFrame:
    try:
        return pd.read_excel(io.BytesIO(raw))
    except Exception as e:
        raise LoadError(f"Could not parse Excel file: {e}")


def load_file(filename: str, raw: bytes) -> LoadResult:
    """
    Parse an uploaded CSV/Excel file into a DataFrame with basic guardrails.
    Raises LoadError for anything that can't safely proceed to ingestion.
    """
    if len(raw) > MAX_UPLOAD_BYTES:
        raise LoadError(
            f"File too large ({len(raw) / 1_048_576:.1f}MB > "
            f"{MAX_UPLOAD_BYTES / 1_048_576:.0f}MB limit)."
        )

    lower = filename.lower()
    if lower.endswith(".csv"):
        df = _read_csv_bytes(raw)
    elif lower.endswith((".xlsx", ".xls")):
        df = _read_excel_bytes(raw)
    else:
        raise LoadError(f"Unsupported file type: {filename}. Use .csv, .xlsx, or .xls.")

    warnings: list[str] = []

    if df.empty:
        raise LoadError("File contains no rows.")

    if len(df.columns) > MAX_COLUMNS:
        raise LoadError(f"Too many columns ({len(df.columns)} > {MAX_COLUMNS} limit).")

    if len(df) > MAX_ROWS:
        warnings.append(f"File has {len(df):,} rows — truncated to first {MAX_ROWS:,}.")
        df = df.head(MAX_ROWS)

    # Drop fully-empty unnamed columns pandas sometimes creates from trailing delimiters
    unnamed_empty = [
        c for c in df.columns
        if str(c).startswith("Unnamed:") and df[c].isna().all()
    ]
    if unnamed_empty:
        df = df.drop(columns=unnamed_empty)

    return LoadResult(df=df, warnings=warnings)
