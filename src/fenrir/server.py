"""Thin HTTP API over the fenrir agent — streaming chat + human-in-the-loop resume.

Two endpoints do the work, both server-sent-event streams of the same shape:
  POST /chat                      {message, thread_id?}   -> start / continue a run
  POST /threads/{id}/resume       {decisions}             -> answer a gated tool call

SSE events: thread, message, interrupt, error, done.
"""

import json
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import BaseModel

from fenrir.agents import build_agent

RECURSION_LIMIT = 100

_state: dict[str, Any] = {"agent": None, "error": None}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        _state["agent"] = await build_agent(checkpointer=InMemorySaver())
    except Exception as e:  # noqa: BLE001 - surfaced per-request as 503
        _state["error"] = str(e)
    yield


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
                    m = update["messages"][-1]
                    yield _sse(
                        "message",
                        {
                            "type": m.type,
                            "node": node,
                            "content": _text(m.content),
                            "tool_calls": getattr(m, "tool_calls", []) or [],
                        },
                    )
    except Exception as e:  # noqa: BLE001 - report mid-stream, don't 500
        yield _sse("error", {"detail": str(e)})
    yield _sse("done", {})


@app.get("/health")
async def health() -> dict:
    return {"ok": _state["agent"] is not None, "error": _state["error"]}


@app.post("/chat")
async def chat(body: ChatIn) -> StreamingResponse:
    thread_id = body.thread_id or str(uuid.uuid4())
    payload = {"messages": [{"role": "user", "content": body.message}]}
    return StreamingResponse(_run(payload, thread_id), media_type="text/event-stream")


@app.post("/threads/{thread_id}/resume")
async def resume(thread_id: str, body: ResumeIn) -> StreamingResponse:
    payload = Command(resume={"decisions": body.decisions})
    return StreamingResponse(_run(payload, thread_id), media_type="text/event-stream")


def run() -> None:
    import uvicorn

    uvicorn.run("fenrir.server:app", host="127.0.0.1", port=8000)
