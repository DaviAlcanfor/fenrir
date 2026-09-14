"""SQLite-backed conversation history and per-agent token usage."""

from typing import Final, TypedDict

import aiosqlite

from fenrir.config import ROOT

DB_PATH: Final = ROOT / "data" / "fenrir.db"
DB_PATH.parent.mkdir(exist_ok=True)


class ThreadRow(TypedDict):
    thread_id: str
    title: str
    created_at: str


class UsageRow(TypedDict):
    """One LLM call's token cost, attributed to the graph node (agent) that made it."""

    thread_id: str
    node: str
    model: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    created_at: str


class UsageSummary(TypedDict):
    """Token cost aggregated per node for a thread."""

    node: str
    model: str | None
    calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int


async def connect() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)

    await db.execute(
        "CREATE TABLE IF NOT EXISTS threads (id TEXT PRIMARY KEY, title TEXT, created_at TEXT)"
    )
    await db.execute(
        """
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
    )
    await db.commit()

    return db


async def record_thread(db: aiosqlite.Connection, thread_id: str, title: str, created_at: str) -> None:
    await db.execute(
        "INSERT OR IGNORE INTO threads (id, title, created_at) VALUES (?, ?, ?)",
        (thread_id, title, created_at),
    )
    await db.commit()


async def list_threads(db: aiosqlite.Connection) -> list[ThreadRow]:
    async with db.execute("SELECT id, title, created_at FROM threads ORDER BY created_at DESC") as cur:
        rows = await cur.fetchall()

    return [ThreadRow(thread_id=r[0], title=r[1], created_at=r[2]) for r in rows]


async def record_usage(db: aiosqlite.Connection, rows: list[UsageRow]) -> None:
    """Batch-insert usage rows. No-op for an empty list — callers don't need to check first."""
    if not rows:
        return

    await db.executemany(
        """
        INSERT INTO usage (thread_id, node, model, input_tokens, output_tokens, total_tokens, created_at)
        VALUES (:thread_id, :node, :model, :input_tokens, :output_tokens, :total_tokens, :created_at)
        """,
        rows,
    )
    await db.commit()


async def usage_for_thread(db: aiosqlite.Connection, thread_id: str) -> list[UsageSummary]:
    async with db.execute(
        """
        SELECT node, model, COUNT(*), SUM(input_tokens), SUM(output_tokens), SUM(total_tokens)
        FROM usage
        WHERE thread_id = ?
        GROUP BY node, model
        ORDER BY SUM(total_tokens) DESC
        """,
        (thread_id,),
    ) as cur:
        rows = await cur.fetchall()

    return [
        UsageSummary(node=r[0], model=r[1], calls=r[2], input_tokens=r[3], output_tokens=r[4], total_tokens=r[5])
        for r in rows
    ]
