"""FastAPI app: agent + database lifecycle, CORS, mounted routes."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from fenrir.agents import build_agent

from . import db
from .routes import router
from .state import state


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    conn = await db.connect()
    state.db = conn

    try:
        async with AsyncSqliteSaver.from_conn_string(str(db.DB_PATH)) as saver:
            state.agent = await build_agent(checkpointer=saver)
            yield
    except Exception as e:  # noqa: BLE001 - surfaced per-request
        state.error = str(e)
        yield
    finally:
        await conn.close()


app = FastAPI(title="fenrir", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
