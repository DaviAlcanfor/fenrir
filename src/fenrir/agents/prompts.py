"""Prompt loader. Prompts are plain Markdown in src/fenrir/prompts/, one per agent."""

from fenrir.config import PROMPTS_DIR, Agent


def load(name: Agent) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
