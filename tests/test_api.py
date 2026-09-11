"""Runnable self-checks for the API's SSE and DB helpers. `uv run python tests/test_api.py`."""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import aiosqlite  # noqa: E402

from fenrir.api import db  # noqa: E402
from fenrir.api.sse import as_message, encode  # noqa: E402


def _parse_frame(frame: bytes) -> tuple[str, dict]:
    text = frame.decode()
    event = text.splitlines()[0].removeprefix("event: ")
    data = json.loads(text.splitlines()[1].removeprefix("data: "))
    return event, data


def test_encode_produces_a_valid_sse_frame():
    event, data = _parse_frame(encode("message", {"content": "hi"}))
    assert event == "message"
    assert data == {"content": "hi"}


def test_as_message_extracts_type_content_and_tool_calls():
    m = SimpleNamespace(type="ai", content="hello", tool_calls=[{"name": "in_scope", "args": {}}])
    assert as_message(m) == {"type": "ai", "content": "hello", "tool_calls": [{"name": "in_scope", "args": {}}]}


def test_as_message_flattens_content_blocks():
    m = SimpleNamespace(type="ai", content=[{"text": "part one"}, {"text": "part two"}], tool_calls=[])
    assert as_message(m)["content"] == "part one\npart two"


def test_as_message_defaults_missing_fields():
    m = SimpleNamespace()
    assert as_message(m) == {"type": "ai", "content": "", "tool_calls": []}


def test_db_round_trip():
    async def run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.db"
            conn = await aiosqlite.connect(path)
            try:
                await conn.execute(
                    "CREATE TABLE IF NOT EXISTS threads (id TEXT PRIMARY KEY, title TEXT, created_at TEXT)"
                )
                await conn.commit()
                await db.record_thread(conn, "t1", "first chat", "2026-01-01T00:00:00Z")
                await db.record_thread(conn, "t1", "ignored (same id)", "2026-01-01T00:00:01Z")
                rows = await db.list_threads(conn)
                assert rows == [{"thread_id": "t1", "title": "first chat", "created_at": "2026-01-01T00:00:00Z"}]
            finally:
                await conn.close()

    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all passed")
