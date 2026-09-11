"""HTTP routes for the fenrir API.

  POST /chat                     {message, thread_id?}  -> start / continue a run (SSE)
  POST /threads/{id}/resume      {decisions}            -> answer a gated tool call (SSE)
  GET  /threads                                         -> list past conversations
  GET  /threads/{id}                                    -> replay a conversation's messages
  GET  /threads/{id}/usage                               -> per-agent token cost for the thread
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from starlette.background import BackgroundTask

from fenrir.protocol import HumanTurn, InvokePayload

from . import db
from .db import ThreadRow, UsageRow, UsageSummary
from .schemas import ChatIn, HealthStatus, ResumeIn, ThreadMessages
from .sse import as_message, stream_run
from .state import RECURSION_LIMIT, state

router = APIRouter()


@router.get("/health")
async def health() -> HealthStatus:
    return {"ok": state.agent is not None, "error": state.error}


@router.get("/threads")
async def list_threads() -> list[ThreadRow]:
    return await db.list_threads(state.require_db())


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str) -> ThreadMessages:
    agent = state.agent
    if agent is None:
        raise HTTPException(503, state.error or "agent not ready")

    snap = await agent.aget_state({"configurable": {"thread_id": thread_id}})
    messages = (snap.values or {}).get("messages", []) if snap else []

    replayed = []
    for m in messages:
        out = as_message(m)
        out["node"] = None
        replayed.append(out)

    return {"messages": replayed}


@router.get("/threads/{thread_id}/usage")
async def get_usage(thread_id: str) -> list[UsageSummary]:
    return await db.usage_for_thread(state.require_db(), thread_id)


async def _persist_usage(rows: list[UsageRow]) -> None:
    await db.record_usage(state.require_db(), rows)


def _stream(payload: InvokePayload | Command, thread_id: str) -> StreamingResponse:
    usage: list[UsageRow] = []

    return StreamingResponse(
        stream_run(state.agent, state.error, payload, thread_id, RECURSION_LIMIT, usage),
        media_type="text/event-stream",
        background=BackgroundTask(_persist_usage, usage),
    )


@router.post("/chat")
async def chat(body: ChatIn) -> StreamingResponse:
    thread_id = body.thread_id or str(uuid.uuid4())

    if not body.thread_id:
        title = body.message.strip().splitlines()[0][:80] or "untitled"
        await db.record_thread(state.require_db(), thread_id, title, datetime.now(timezone.utc).isoformat())

    turn: HumanTurn = {"role": "user", "content": body.message}
    payload: InvokePayload = {"messages": [turn]}

    return _stream(payload, thread_id)


@router.post("/threads/{thread_id}/resume")
async def resume(thread_id: str, body: ResumeIn) -> StreamingResponse:
    payload: Command = Command(resume={"decisions": body.decisions})

    return _stream(payload, thread_id)
