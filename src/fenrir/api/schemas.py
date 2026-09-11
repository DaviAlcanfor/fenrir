"""Request/response shapes for the HTTP API."""

from typing import TypedDict

from pydantic import BaseModel

from fenrir.protocol import Decision

from .sse import MessageOut


class ChatIn(BaseModel):
    message: str
    thread_id: str | None = None


class ResumeIn(BaseModel):
    decisions: list[Decision]


class HealthStatus(TypedDict):
    ok: bool
    error: str | None


class ThreadMessages(TypedDict):
    messages: list[MessageOut]
