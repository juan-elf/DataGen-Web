"""
POST /upload — CSV/Excel → a new table in the caller's workspace schema.

Pipeline (DataGenWeb.md §4.2): receive file -> parse -> validate -> sanitize
schema -> load into Postgres -> profile -> respond with a preview.
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.chat import evict_agent
from core.context import WorkspaceContext, use_context
from core.profiler import profile_database, format_profile_for_prompt, invalidate_profile_cache
from core.ratelimit import RateLimitExceeded, check_rate_limit
from db.context import get_workspace
from ingest.ingest import ingest_dataframe, table_exists
from ingest.loader import LoadError, load_file
from ingest.schema_infer import sanitize_table_name

router = APIRouter()


@router.post("/upload")
def upload(
    file: UploadFile = File(...),
    table_name: Optional[str] = Form(None),
    if_exists: str = Form("fail"),
    ctx: WorkspaceContext = Depends(get_workspace),
):
    if if_exists not in ("fail", "replace", "append"):
        raise HTTPException(400, "if_exists must be one of: fail, replace, append")

    try:
        check_rate_limit(f"upload:{ctx.workspace_id}", max_requests=10, window_seconds=3600)
    except RateLimitExceeded as e:
        raise HTTPException(429, f"Rate limit exceeded, retry in {e.retry_after:.0f}s")

    raw = file.file.read()
    try:
        loaded = load_file(file.filename, raw)
    except LoadError as e:
        raise HTTPException(400, str(e))

    desired_table = sanitize_table_name(table_name or file.filename.rsplit(".", 1)[0])

    with use_context(ctx):
        if if_exists == "fail" and table_exists(desired_table, ctx):
            raise HTTPException(
                409,
                f"Table '{desired_table}' already exists in this workspace. "
                f"Pass if_exists=replace or if_exists=append, or choose a different table_name.",
            )

        try:
            summary = ingest_dataframe(loaded, desired_table, ctx, if_exists=if_exists)
        except Exception as e:
            raise HTTPException(500, f"Ingest failed: {type(e).__name__}: {e}")

        invalidate_profile_cache(ctx.schema)
        profile_text = format_profile_for_prompt(profile_database(force=True))

    # The workspace's cached chat agent baked the old (possibly empty) schema
    # into its system prompt — drop it so the next question sees this upload.
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
