"""
POST /sample — load a bundled demo dataset into the caller's workspace.

Exists to remove the biggest friction on a public demo: having to hand your own
data to a server you don't know yet. A visitor can click once, get real data in
their workspace, and exercise the whole flow (profile → chat → report) without
uploading anything.

Deliberately reuses the exact same ingest pipeline as /upload rather than a
special-cased loader, so the sample path can't silently drift from the real one.
"""
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from api.chat import evict_agent
from core.context import WorkspaceContext, use_context
from core.profiler import profile_database, format_profile_for_prompt, invalidate_profile_cache
from core.ratelimit import RateLimitExceeded, check_rate_limit
from db.context import get_workspace
from ingest.ingest import ingest_dataframe
from ingest.loader import LoadError, load_file

router = APIRouter()

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
DEFAULT_SAMPLE = "ecommerce_orders"
_SAMPLE_NAME_RE = re.compile(r"^[a-z0-9_]+$")


@router.post("/sample")
def load_sample(
    dataset: str = DEFAULT_SAMPLE,
    ctx: WorkspaceContext = Depends(get_workspace),
):
    # `dataset` is attacker-controlled and becomes a filename — allow only a
    # strict slug so it can never escape SAMPLES_DIR (no "..", no separators).
    if not _SAMPLE_NAME_RE.match(dataset):
        raise HTTPException(400, "Invalid dataset name.")

    path = SAMPLES_DIR / f"{dataset}.csv"
    if not path.is_file():
        raise HTTPException(404, f"Sample dataset '{dataset}' not found.")

    try:
        check_rate_limit(f"sample:{ctx.workspace_id}", max_requests=10, window_seconds=3600)
    except RateLimitExceeded as e:
        raise HTTPException(429, f"Rate limit exceeded, retry in {e.retry_after:.0f}s")

    try:
        loaded = load_file(path.name, path.read_bytes())
    except LoadError as e:
        # Bundled file is ours — a failure here is a deploy/packaging bug, not user error.
        raise HTTPException(500, f"Bundled sample failed to parse: {e}")

    with use_context(ctx):
        try:
            # "replace" keeps repeat clicks idempotent instead of erroring on a
            # table that already exists.
            summary = ingest_dataframe(loaded, dataset, ctx, if_exists="replace")
        except Exception as e:
            raise HTTPException(500, f"Ingest failed: {type(e).__name__}: {e}")

        invalidate_profile_cache(ctx.schema)
        profile_text = format_profile_for_prompt(profile_database(force=True))

    # Same reason as /upload: the cached agent baked the old schema into its
    # system prompt and would answer as if this data didn't exist.
    evict_agent(ctx.workspace_id)

    return {
        "success": True,
        "table": summary["table"],
        "rows": summary["rows"],
        "columns": summary["columns"],
        "column_mapping": summary["column_mapping"],
        "warnings": summary["warnings"],
        "profile_preview": profile_text,
    }
