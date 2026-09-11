"""HTTP routes for the fenrir API.

  POST /chat                   {message, thread_id?}  -> start / continue a run (SSE)
  POST /threads/{id}/resume    {decisions}            -> answer a gated tool call (SSE)
  GET  /threads                                       -> list past conversations
  GET  /threads/{id}                                  -> replay a conversation's messages
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from . import db
from .schemas import ChatIn, ResumeIn
from .sse import as_message, stream_run
from .state import RECURSION_LIMIT, state

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"ok": state["agent"] is not None, "error": state["error"]}


@router.get("/threads")
async def list_threads() -> list[dict]:
    return await db.list_threads(state["db"])


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str) -> dict:
    agent = state["agent"]
    if agent is None:
        raise HTTPException(503, state["error"] or "agent not ready")
    snap = await agent.aget_state({"configurable": {"thread_id": thread_id}})
    messages = (snap.values or {}).get("messages", []) if snap else []
    return {"messages": [{"node": None, **as_message(m)} for m in messages]}


@router.post("/chat")
async def chat(body: ChatIn) -> StreamingResponse:
    thread_id = body.thread_id or str(uuid.uuid4())
    if not body.thread_id:
        title = body.message.strip().splitlines()[0][:80] or "untitled"
        await db.record_thread(state["db"], thread_id, title, datetime.now(timezone.utc).isoformat())
    payload = {"messages": [{"role": "user", "content": body.message}]}
    return StreamingResponse(
        stream_run(state["agent"], state["error"], payload, thread_id, RECURSION_LIMIT),
        media_type="text/event-stream",
    )


@router.post("/threads/{thread_id}/resume")
async def resume(thread_id: str, body: ResumeIn) -> StreamingResponse:
    payload = Command(resume={"decisions": body.decisions})
    return StreamingResponse(
        stream_run(state["agent"], state["error"], payload, thread_id, RECURSION_LIMIT),
        media_type="text/event-stream",
    )
