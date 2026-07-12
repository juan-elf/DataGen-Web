"""
POST /chat — SSE-streamed conversation with the agent, reusing
`core/agent.py:Agent.chat_stream()` unchanged from DataGen.

One Agent instance is kept in memory per workspace (mirrors DataGen's
telegram_bot.py: one Agent per chat_id) so conversation history survives
across requests without a database round-trip. This is fine for a single
always-on backend process; if this is ever scaled to multiple instances,
move this dict to a shared store (Redis) keyed by workspace_id.
"""
import json
import queue
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.agent import Agent
from core.context import WorkspaceContext, use_context
from core.ratelimit import RateLimitExceeded, check_rate_limit
from db.context import get_workspace

router = APIRouter()

_agents: dict[str, Agent] = {}
_agents_lock = threading.Lock()


class ChatRequest(BaseModel):
    message: str
    domain: Optional[str] = None


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


def _get_or_create_agent(ctx: WorkspaceContext, domain: Optional[str]) -> Agent:
    with _agents_lock:
        agent = _agents.get(ctx.workspace_id)
        if agent is None or agent.domain != domain:
            with use_context(ctx):
                agent = Agent(domain=domain, workspace_id=ctx.workspace_id)
            _agents[ctx.workspace_id] = agent
        return agent


@router.post("/chat")
def chat(body: ChatRequest, ctx: WorkspaceContext = Depends(get_workspace)):
    if not body.message.strip():
        raise HTTPException(400, "message must not be empty")

    try:
        check_rate_limit(f"chat:{ctx.workspace_id}", max_requests=20, window_seconds=60)
    except RateLimitExceeded as e:
        detail = {"type": "error", "content": f"Rate limit exceeded, retry in {e.retry_after:.0f}s"}
        return StreamingResponse(iter([_sse(detail)]), media_type="text/event-stream")

    agent = _get_or_create_agent(ctx, body.domain)
    q: queue.Queue = queue.Queue()

    def worker():
        try:
            with use_context(ctx):
                for event in agent.chat_stream(body.message):
                    q.put(event)
        except Exception as e:
            q.put({"type": "error", "content": f"{type(e).__name__}: {e}"})
        finally:
            q.put(None)  # sentinel — always sent, even if the above raised

    threading.Thread(target=worker, daemon=True).start()

    def event_stream():
        while True:
            item = q.get()
            if item is None:
                break
            yield _sse(item)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/chat/reset")
def chat_reset(ctx: WorkspaceContext = Depends(get_workspace)):
    with _agents_lock:
        agent = _agents.get(ctx.workspace_id)
        if agent:
            agent.reset()
    return {"success": True}
