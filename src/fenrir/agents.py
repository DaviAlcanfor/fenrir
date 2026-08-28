"""Assemble the fenrir orchestrator with its four specialists."""

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.base import BaseCheckpointSaver

from fenrir import prompts
from fenrir.config import MODELS, ROOT, SKILLS, Agent
from fenrir.mcp import hexstrike_tools
from fenrir.subagents import make_subagents
from fenrir.tools import TOOLS


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
        checkpointer=checkpointer,
        name="fenrir",
    )
