"""Request bodies for the HTTP API."""

from pydantic import BaseModel


class ChatIn(BaseModel):
    message: str
    thread_id: str | None = None


class ResumeIn(BaseModel):
    decisions: list[dict]
