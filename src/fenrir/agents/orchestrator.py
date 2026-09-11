"""Assemble the fenrir orchestrator with its four specialists."""

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.base import BaseCheckpointSaver

from fenrir.config import MODELS, ROOT, SKILLS, Agent
from fenrir.mcp import hexstrike_tools
from fenrir.tools import TOOLS

from . import prompts
from .subagents import make_subagents

ROOT_INTERRUPT_ON: dict[str, bool] = {
    "execute": True,  # the root orchestrator's local shell always pauses for approval
}


async def build_agent(checkpointer: BaseCheckpointSaver | None = None):
    """Build the compiled graph. Pass a checkpointer to keep per-thread state
    (the CLI and the API both use an in-memory one)."""
    tools = await hexstrike_tools()
    return create_deep_agent(
        model=MODELS[Agent.ORCHESTRATOR],
        system_prompt=prompts.load(Agent.ORCHESTRATOR),
        tools=TOOLS,
        subagents=make_subagents(tools),
        skills=SKILLS,
        backend=LocalShellBackend(root_dir=str(ROOT)),
        interrupt_on=ROOT_INTERRUPT_ON,
        checkpointer=checkpointer,
        name="fenrir",
    )
