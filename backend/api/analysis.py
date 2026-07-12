"""
POST /analysis — direct sandboxed pandas analysis, reusing
`core/analysis.py:run_analysis()` unchanged from DataGen. Meant for
frontend-driven ad-hoc analysis (outside the agent tool loop) — e.g. a
"run this on the chart data" button.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.analysis import run_analysis
from core.context import WorkspaceContext, use_context
from core.ratelimit import RateLimitExceeded, check_rate_limit
from db.context import get_workspace

router = APIRouter()


class AnalysisRequest(BaseModel):
    sql: str
    code: str


@router.post("/analysis")
def analysis(body: AnalysisRequest, ctx: WorkspaceContext = Depends(get_workspace)):
    try:
        check_rate_limit(f"analysis:{ctx.workspace_id}", max_requests=30, window_seconds=60)
    except RateLimitExceeded as e:
        raise HTTPException(429, f"Rate limit exceeded, retry in {e.retry_after:.0f}s")

    with use_context(ctx):
        result = run_analysis(body.sql, body.code)
    return result
