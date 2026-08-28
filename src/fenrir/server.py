"""Thin HTTP API over the fenrir agent — streaming chat + human-in-the-loop resume,
with SQLite-backed conversation history.

  POST /chat                   {message, thread_id?}  -> start / continue a run (SSE)
  POST /threads/{id}/resume    {decisions}            -> answer a gated tool call (SSE)
  GET  /threads                                       -> list past conversations
  GET  /threads/{id}                                  -> replay a conversation's messages

SSE events: thread, message, interrupt, error, done.
"""

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import aiosqlite
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from pydantic import BaseModel

from fenrir.agents import build_agent
from fenrir.config import ROOT

RECURSION_LIMIT = 100
DB_PATH = ROOT / "fenrir.db"

_state: dict[str, Any] = {"agent": None, "error": None, "threads": None}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    threads = await aiosqlite.connect(DB_PATH)
    await threads.execute(
        "CREATE TABLE IF NOT EXISTS threads (id TEXT PRIMARY KEY, title TEXT, created_at TEXT)"
    )
    await threads.commit()
    _state["threads"] = threads

    try:
        async with AsyncSqliteSaver.from_conn_string(str(DB_PATH)) as saver:
            _state["agent"] = await build_agent(checkpointer=saver)
            yield
    except Exception as e:  # noqa: BLE001 - surfaced per-request
        _state["error"] = str(e)
        yield
    finally:
        await threads.close()


app = FastAPI(title="fenrir", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatIn(BaseModel):
    message: str
    thread_id: str | None = None


class ResumeIn(BaseModel):
    decisions: list[dict]


def _sse(event: str, data: Any) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode()


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


def _msg(m: Any) -> dict:
    return {
        "type": getattr(m, "type", "ai"),
        "content": _text(getattr(m, "content", "")),
        "tool_calls": getattr(m, "tool_calls", []) or [],
    }


async def _run(payload: Any, thread_id: str):
    agent = _state["agent"]
    if agent is None:
        yield _sse("error", {"detail": _state["error"] or "agent not ready — check API keys in .env"})
        yield _sse("done", {})
        return

    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    yield _sse("thread", {"thread_id": thread_id})
    try:
        async for chunk in agent.astream(payload, config, stream_mode="updates"):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    yield _sse("interrupt", update[0].value)
                elif isinstance(update, dict) and update.get("messages"):
                    yield _sse("message", {"node": node, **_msg(update["messages"][-1])})
    except Exception as e:  # noqa: BLE001 - report mid-stream, don't 500
        yield _sse("error", {"detail": str(e)})
    yield _sse("done", {})


@app.get("/health")
async def health() -> dict:
    return {"ok": _state["agent"] is not None, "error": _state["error"]}


@app.get("/threads")
async def list_threads() -> list[dict]:
    db = _state["threads"]
    async with db.execute("SELECT id, title, created_at FROM threads ORDER BY created_at DESC") as cur:
        rows = await cur.fetchall()
    return [{"thread_id": r[0], "title": r[1], "created_at": r[2]} for r in rows]


@app.get("/threads/{thread_id}")
async def get_thread(thread_id: str) -> dict:
    agent = _state["agent"]
    if agent is None:
        raise HTTPException(503, _state["error"] or "agent not ready")
    snap = await agent.aget_state({"configurable": {"thread_id": thread_id}})
    messages = (snap.values or {}).get("messages", []) if snap else []
    return {"messages": [{"node": None, **_msg(m)} for m in messages]}


@app.post("/chat")
async def chat(body: ChatIn) -> StreamingResponse:
    thread_id = body.thread_id or str(uuid.uuid4())
    if not body.thread_id:
        db = _state["threads"]
        title = body.message.strip().splitlines()[0][:80] or "untitled"
        await db.execute(
            "INSERT OR IGNORE INTO threads (id, title, created_at) VALUES (?, ?, ?)",
            (thread_id, title, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
    payload = {"messages": [{"role": "user", "content": body.message}]}
    return StreamingResponse(_run(payload, thread_id), media_type="text/event-stream")


@app.post("/threads/{thread_id}/resume")
async def resume(thread_id: str, body: ResumeIn) -> StreamingResponse:
    payload = Command(resume={"decisions": body.decisions})
    return StreamingResponse(_run(payload, thread_id), media_type="text/event-stream")


def run() -> None:
    import uvicorn

    uvicorn.run("fenrir.server:app", host="127.0.0.1", port=8000)
