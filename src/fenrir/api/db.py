"""SQLite-backed conversation history (thread id/title/created_at)."""

from typing import Final, TypedDict

import aiosqlite

from fenrir.config import ROOT

DB_PATH: Final = ROOT / "fenrir.db"


class ThreadRow(TypedDict):
    thread_id: str
    title: str
    created_at: str


async def connect() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    await db.execute(
        "CREATE TABLE IF NOT EXISTS threads (id TEXT PRIMARY KEY, title TEXT, created_at TEXT)"
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
