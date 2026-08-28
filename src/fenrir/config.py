"""Static paths and the agent -> model routing table."""

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = ROOT / "src" / "prompts"
SKILLS = ["src/skills"]  


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


MODELS: Mapping[Agent, Model] = {
    Agent.ORCHESTRATOR: Model.GEMINI_FLASH,
    Agent.RECON: Model.GPT_OSS_120B,
    Agent.WEB: Model.GEMINI_FLASH,
    Agent.EXPLOIT: Model.NEMOTRON_SUPER,
    Agent.TRIAGE: Model.GPT_OSS_120B,
}
