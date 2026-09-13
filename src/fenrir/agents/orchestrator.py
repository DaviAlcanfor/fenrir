"""Assemble the fenrir orchestrator with its four specialists."""

from typing import Final

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from fenrir.config import ENGAGEMENT_DIR, MODELS, SKILLS, Agent
from fenrir.mcp import hexstrike_tools
from fenrir.tools import TOOLS

from . import prompts
from .subagents import EXECUTE_TOOL_NAME, make_subagents

# Left unparameterized on purpose: deepagents/langgraph's own generic params
# here are internal implementation detail, not something fenrir's call sites
# should have to spell out. Still far better than `Any` — every method on the
# compiled graph (.ainvoke, .astream, .aget_state, ...) is known to the type
# checker.
FenrirAgent = CompiledStateGraph

ROOT_INTERRUPT_ON: Final[dict[str, bool]] = {
    EXECUTE_TOOL_NAME: True,  # the root orchestrator's local shell always pauses for approval
}


async def build_agent(checkpointer: BaseCheckpointSaver | None = None) -> FenrirAgent:
    """Build the compiled graph. Pass a checkpointer to keep per-thread state
    (the CLI and the API both use an in-memory one)."""
    tools = await hexstrike_tools()

    return create_deep_agent(
        model=MODELS[Agent.ORCHESTRATOR],
        system_prompt=prompts.load(Agent.ORCHESTRATOR),
        tools=TOOLS,
        # SubAgentSpec is a narrower, independently-declared TypedDict (not a
        # subclass of deepagents' own SubAgent) — structurally compatible at
        # runtime (proven by build_agent() smoke tests), but mypy can't prove
        # that across two unrelated TypedDicts.
        subagents=make_subagents(tools),  # type: ignore[arg-type]
        skills=SKILLS,
        backend=LocalShellBackend(root_dir=str(ENGAGEMENT_DIR)),
        # Same story: dict[str, bool] is deliberately narrower than deepagents'
        # dict[str, bool | InterruptOnConfig] — every gate fenrir sets is a
        # plain bool, and dict's value-type invariance is what mypy is (too
        # conservatively) flagging here, not an actual type mismatch.
        interrupt_on=ROOT_INTERRUPT_ON,  # type: ignore[arg-type]
        checkpointer=checkpointer,
        name="fenrir",
    )
