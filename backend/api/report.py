"""
POST /report — SSE-streamed autonomous Insight Report, reusing
`core/insight_report.py:generate_report()` unchanged from DataGen.

Runs on a background thread so `on_progress` callbacks can be forwarded to
the client as they happen, instead of the client waiting silently for the
whole multi-LLM-call pipeline (which is exactly the >60s serverless-timeout
problem DataGenWeb.md §0 chose the always-on backend to avoid).
"""
import json
import queue
import threading

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from core.context import WorkspaceContext, use_context
from core.insight_report import generate_report
from core.ratelimit import RateLimitExceeded, check_rate_limit
from db.context import get_workspace

router = APIRouter()


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


@router.post("/report")
def report(ctx: WorkspaceContext = Depends(get_workspace)):
    try:
        check_rate_limit(f"report:{ctx.workspace_id}", max_requests=5, window_seconds=3600)
    except RateLimitExceeded as e:
        detail = {"type": "error", "content": f"Rate limit exceeded, retry in {e.retry_after:.0f}s"}
        return StreamingResponse(iter([_sse(detail)]), media_type="text/event-stream")

    q: queue.Queue = queue.Queue()

    def on_progress(step: str, detail: str = "") -> None:
        q.put({"type": "progress", "step": step, "detail": detail})

    def worker():
        try:
            with use_context(ctx):
                result = generate_report(on_progress=on_progress)
            q.put({"type": "result", "data": result})
        except Exception as e:
            q.put({"type": "error", "content": f"{type(e).__name__}: {e}"})
        finally:
            q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def event_stream():
        while True:
            item = q.get()
            if item is None:
                break
            yield _sse(item)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
