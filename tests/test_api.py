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
from pydantic import ValidationError  # noqa: E402

from langchain_core.messages import AIMessageChunk  # noqa: E402

from fenrir.api import db  # noqa: E402
from fenrir.api.schemas import ResumeIn  # noqa: E402
from fenrir.api.sse import _usage_row, as_message, encode  # noqa: E402


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


def test_resume_in_accepts_approve_and_reject_decisions():
    approve = ResumeIn.model_validate({"decisions": [{"type": "approve"}]})
    assert approve.decisions == [{"type": "approve"}]

    reject = ResumeIn.model_validate({"decisions": [{"type": "reject", "message": "no"}]})
    assert reject.decisions == [{"type": "reject", "message": "no"}]


def test_resume_in_rejects_an_unknown_decision_type():
    try:
        ResumeIn.model_validate({"decisions": [{"type": "maybe"}]})
        raise AssertionError("expected ValidationError")
    except ValidationError:
        pass


_USAGE_TABLE = """
    CREATE TABLE IF NOT EXISTS usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id TEXT NOT NULL,
        node TEXT NOT NULL,
        model TEXT,
        input_tokens INTEGER NOT NULL,
        output_tokens INTEGER NOT NULL,
        total_tokens INTEGER NOT NULL,
        created_at TEXT NOT NULL
    )
"""


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


def test_usage_row_extracts_tokens_and_model():
    chunk = AIMessageChunk(
        content="hi",
        usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        response_metadata={"model_name": "gemini-3.6-flash"},
    )
    row = _usage_row("t1", "recon", chunk)
    assert row["node"] == "recon"
    assert row["model"] == "gemini-3.6-flash"
    assert row["input_tokens"] == 100
    assert row["output_tokens"] == 20
    assert row["total_tokens"] == 120


def test_usage_row_defaults_to_zero_without_usage_metadata():
    chunk = AIMessageChunk(content="hi")
    row = _usage_row("t1", "web", chunk)
    assert row["input_tokens"] == 0
    assert row["output_tokens"] == 0
    assert row["total_tokens"] == 0


def test_usage_round_trip_aggregates_per_node_and_model():
    async def run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.db"
            conn = await aiosqlite.connect(path)
            try:
                await conn.execute(_USAGE_TABLE)
                await conn.commit()

                rows = [
                    db.UsageRow(
                        thread_id="t1", node="orchestrator", model="gemini-3.6-flash",
                        input_tokens=50, output_tokens=10, total_tokens=60, created_at="2026-01-01T00:00:00Z",
                    ),
                    db.UsageRow(
                        thread_id="t1", node="recon", model="gpt-oss-120b",
                        input_tokens=200, output_tokens=40, total_tokens=240, created_at="2026-01-01T00:00:01Z",
                    ),
                    db.UsageRow(
                        thread_id="t1", node="recon", model="gpt-oss-120b",
                        input_tokens=80, output_tokens=15, total_tokens=95, created_at="2026-01-01T00:00:02Z",
                    ),
                    db.UsageRow(
                        thread_id="t2", node="recon", model="gpt-oss-120b",
                        input_tokens=999, output_tokens=999, total_tokens=1998, created_at="2026-01-01T00:00:03Z",
                    ),
                ]
                await db.record_usage(conn, rows)

                summary = await db.usage_for_thread(conn, "t1")
                by_node = {row["node"]: row for row in summary}

                assert set(by_node) == {"orchestrator", "recon"}
                assert by_node["recon"]["calls"] == 2
                assert by_node["recon"]["input_tokens"] == 280
                assert by_node["recon"]["total_tokens"] == 335
                assert by_node["orchestrator"]["total_tokens"] == 60
            finally:
                await conn.close()

    asyncio.run(run())


def test_record_usage_is_a_noop_for_an_empty_list():
    async def run() -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.db"
            conn = await aiosqlite.connect(path)
            try:
                await conn.execute(_USAGE_TABLE)
                await conn.commit()
                await db.record_usage(conn, [])  # must not raise
                assert await db.usage_for_thread(conn, "t1") == []
            finally:
                await conn.close()

    asyncio.run(run())


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all passed")
