"""Server-sent event encoding and the agent-stream -> SSE generator.

Events: thread, message, interrupt, error, done.
"""

import json
from typing import Any


def encode(event: str, data: Any) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode()


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


def as_message(m: Any) -> dict:
    return {
        "type": getattr(m, "type", "ai"),
        "content": _text(getattr(m, "content", "")),
        "tool_calls": getattr(m, "tool_calls", []) or [],
    }


async def stream_run(agent: Any, error: str | None, payload: Any, thread_id: str, recursion_limit: int):
    if agent is None:
        yield encode("error", {"detail": error or "agent not ready — check API keys in .env"})
        yield encode("done", {})
        return

    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": recursion_limit}
    yield encode("thread", {"thread_id": thread_id})
    try:
        async for chunk in agent.astream(payload, config, stream_mode="updates"):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    yield encode("interrupt", update[0].value)
                elif isinstance(update, dict) and update.get("messages"):
                    yield encode("message", {"node": node, **as_message(update["messages"][-1])})
    except Exception as e:  # noqa: BLE001 - report mid-stream, don't 500
        yield encode("error", {"detail": str(e)})
    yield encode("done", {})
