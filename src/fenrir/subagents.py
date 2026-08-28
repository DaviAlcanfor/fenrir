"""Declarative specs for fenrir's four specialists, injected into the orchestrator."""

from collections.abc import Sequence
from typing import NotRequired, TypedDict

from langchain_core.tools import BaseTool

from fenrir import prompts
from fenrir.config import MODELS, SKILLS, Agent
from fenrir.settings import settings
from fenrir.tools import TOOLS

__all__ = ["SubAgentSpec", "make_subagents"]


class SubAgentSpec(TypedDict):
    name: str
    description: str
    system_prompt: str
    model: str
    skills: list[str]
    tools: NotRequired[Sequence[BaseTool]]
    interrupt_on: NotRequired[dict[str, bool]]


_BELT: dict[Agent, tuple[str, ...] | None] = {
    Agent.RECON: (
        "subfinder", "amass", "dns", "httpx", "katana", "gau", "wayback",
        "gobuster", "feroxbuster", "dirsearch", "nmap", "masscan", "naabu",
        "whatweb", "wafw00f", "nuclei", "paramspider", "arjun",
    ),
    Agent.WEB: (
        "nuclei", "ffuf", "sqlmap", "dalfox", "wpscan", "nikto", "arjun",
        "paramspider", "katana", "httpx", "gobuster", "feroxbuster",
        "dirsearch", "wafw00f", "gau", "wayback",
    ),
    Agent.EXPLOIT: None,
}


def _belt(tools: Sequence[BaseTool], agent: Agent) -> list[BaseTool]:
    keys = _BELT[agent]
    
    if keys is None:
        return list(tools)
    
    return [t for t in tools if any(k in t.name.lower() for k in keys)]


def _gate(tools: Sequence[BaseTool]) -> dict[str, bool]:
    """
    Every offensive tool + `execute` pauses for operator approval.
    """
    
    if not settings.require_approval:
        return {}
    
    return {t.name: True for t in tools} | {"execute": True}


def make_subagents(tools: Sequence[BaseTool]) -> list[SubAgentSpec]:
    recon = _belt(tools, Agent.RECON)
    web = _belt(tools, Agent.WEB)
    exploit = list(tools)

    return [
        SubAgentSpec(
            name=Agent.RECON,
            description="Subdomain/DNS/port/tech/content discovery and link-takeover checks. Scope targets go here first.",
            system_prompt=prompts.load(Agent.RECON),
            model=MODELS[Agent.RECON],
            skills=SKILLS,
            tools=[*TOOLS, *recon],
            interrupt_on=_gate(recon),
        ),
        SubAgentSpec(
            name=Agent.WEB,
            description="Hands-on web app testing of one surface using OWASP WSTG methodology.",
            system_prompt=prompts.load(Agent.WEB),
            model=MODELS[Agent.WEB],
            skills=SKILLS,
            tools=[*TOOLS, *web],
            interrupt_on=_gate(web),
        ),
        SubAgentSpec(
            name=Agent.EXPLOIT,
            description="Build a minimal proof-of-concept for ONE already-confirmed finding. Always gated.",
            system_prompt=prompts.load(Agent.EXPLOIT),
            model=MODELS[Agent.EXPLOIT],
            skills=SKILLS,
            tools=[*TOOLS, *exploit],
            interrupt_on=_gate(exploit),
        ),
        SubAgentSpec(
            name=Agent.TRIAGE,
            description="Dedupe findings, assign CVSS, write the report in the skill's output format.",
            system_prompt=prompts.load(Agent.TRIAGE),
            model=MODELS[Agent.TRIAGE],
            skills=SKILLS,
        ),
    ]
