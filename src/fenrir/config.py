"""Static paths and the agent -> model routing table."""

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Final

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
PACKAGE_DIR: Final[Path] = Path(__file__).resolve().parent
PROMPTS_DIR: Final[Path] = PACKAGE_DIR / "prompts"
SKILLS: Final[list[str]] = ["src/fenrir/skills"]


class Agent(StrEnum):
    ORCHESTRATOR = "orchestrator"
    RECON = "recon"
    WEB = "web"
    EXPLOIT = "exploit"
    TRIAGE = "triage"


class Model(StrEnum):
    GEMINI_FLASH = "google_genai:gemini-3.6-flash"
    GPT_OSS_120B = "groq:openai/gpt-oss-120b"
    NEMOTRON_SUPER = "openrouter:nvidia/nemotron-3-super-120b-a12b:free"


MODELS: Final[Mapping[Agent, Model]] = {
    Agent.ORCHESTRATOR: Model.GEMINI_FLASH,
    Agent.RECON: Model.GPT_OSS_120B,
    Agent.WEB: Model.GEMINI_FLASH,
    Agent.EXPLOIT: Model.NEMOTRON_SUPER,
    Agent.TRIAGE: Model.GPT_OSS_120B,
}
