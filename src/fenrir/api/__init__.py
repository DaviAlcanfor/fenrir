"""HTTP API for fenrir — streaming chat + human-in-the-loop resume, SQLite-backed history.

SSE events: thread, message, interrupt, error, done.
"""

from .app import app

__all__ = ["app", "run"]


def run() -> None:
    import uvicorn

    uvicorn.run("fenrir.api.app:app", host="127.0.0.1", port=8000)
