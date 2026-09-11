"""Prompt loader. Prompts are plain Markdown in src/prompts/, one per agent."""

from fenrir.config import PROMPTS_DIR


def load(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
