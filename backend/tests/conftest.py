"""
pytest configuration for the backend test suite.

Unlike DataGen's CLI tests (which could fall back to a real local SQLite
file), this backend is Postgres-only, and no live database is available in
CI/most dev environments. So this suite intentionally covers only the
DB-free layers: guardrails, ingest/schema inference, ingest/file loading,
the workspace context primitive, and the rate limiter. Anything that needs
a real Postgres connection (core/database.py, core/profiler.py end-to-end)
is exercised manually against Supabase — see README.md "Testing" section.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
