"""Server-sent event encoding and the agent-stream -> SSE generator.

Events: thread, message, interrupt, error, done.
"""

import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Final, Literal, NotRequired, TypedDict

from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from fenrir.agents import FenrirAgent
from fenrir.protocol import InvokePayload

from .db import UsageRow

SseEvent = Literal["thread", "message", "interrupt", "error", "done"]

INTERRUPT_NODE: Final = "__interrupt__"


class MessageOut(TypedDict):
    type: str
    content: str
    tool_calls: list[dict]
    node: NotRequired[str | None]


def encode(event: SseEvent, data: object) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode()


def _text(content: object) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        return "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)

    return str(content)


def as_message(m: BaseMessage) -> MessageOut:
    return {
        "type": getattr(m, "type", "ai"),
        "content": _text(getattr(m, "content", "")),
        "tool_calls": getattr(m, "tool_calls", []) or [],
    }


def _usage_row(thread_id: str, node: str, chunk: AIMessageChunk) -> UsageRow:
    usage = chunk.usage_metadata

    return {
        "thread_id": thread_id,
        "node": node,
        "model": chunk.response_metadata.get("model_name"),
        "input_tokens": usage["input_tokens"] if usage else 0,
        "output_tokens": usage["output_tokens"] if usage else 0,
        "total_tokens": usage["total_tokens"] if usage else 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


async def stream_run(
    agent: FenrirAgent | None,
    error: str | None,
    payload: InvokePayload | Command,
    thread_id: str,
    recursion_limit: int,
    usage: list[UsageRow],
) -> AsyncIterator[bytes]:
    """Stream the run as SSE frames. `usage` is an output parameter — every
    LLM call's token cost, attributed to the agent (graph node) that made it,
    gets appended to it as the run progresses. The caller reads it back once
    the generator is exhausted (e.g. via StreamingResponse's `background`)."""
    if agent is None:
        yield encode("error", {"detail": error or "agent not ready — check API keys in .env"})
        yield encode("done", {})
        return

    config: RunnableConfig = {"configurable": {"thread_id": thread_id}, "recursion_limit": recursion_limit}
    yield encode("thread", {"thread_id": thread_id})

    try:
        async for part in agent.astream(
            payload, config, stream_mode=["updates", "messages"], subgraphs=True, version="v2"
        ):
            if part["type"] == "updates":
                for node, update in part["data"].items():
                    if node == INTERRUPT_NODE:
                        yield encode("interrupt", update[0].value)
                    elif isinstance(update, dict) and update.get("messages"):
                        out = as_message(update["messages"][-1])
                        out["node"] = node
                        yield encode("message", out)

            elif part["type"] == "messages":
                chunk, meta = part["data"]
                if isinstance(chunk, AIMessageChunk) and chunk.usage_metadata:
                    usage.append(_usage_row(thread_id, meta["langgraph_node"], chunk))
    except Exception as e:  # noqa: BLE001 - report mid-stream, don't 500
        yield encode("error", {"detail": str(e)})

    yield encode("done", {})
