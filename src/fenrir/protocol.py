"""Typed shapes for the human-in-the-loop protocol shared by fenrir's two
front ends (the CLI and the HTTP API). Both talk to the same compiled agent
graph, so both send it the same invoke payload and answer the same kind of
interrupt — this module is the one place that shape is defined.
"""

from typing import Literal, NotRequired, TypedDict

__all__ = [
    "HumanTurn",
    "InvokePayload",
    "ActionRequest",
    "InterruptRequest",
    "ApproveDecision",
    "RejectDecision",
    "Decision",
]


class HumanTurn(TypedDict):
    role: Literal["user"]
    content: str


class InvokePayload(TypedDict):
    """What `agent.ainvoke`/`agent.astream` are first called with."""

    messages: list[HumanTurn]


class ActionRequest(TypedDict):
    """One gated tool call the graph is pausing on."""

    name: str
    args: dict[str, object]
    description: NotRequired[str]


class InterruptRequest(TypedDict):
    """The `__interrupt__` payload — one or more gated tool calls awaiting a decision."""

    action_requests: list[ActionRequest]


class ApproveDecision(TypedDict):
    type: Literal["approve"]


class RejectDecision(TypedDict):
    type: Literal["reject"]
    message: NotRequired[str]


Decision = ApproveDecision | RejectDecision
