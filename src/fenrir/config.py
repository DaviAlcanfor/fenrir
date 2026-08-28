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
    GEMINI_FLASH = "google_genai:gemini-2.0-flash"
    LLAMA_70B = "groq:llama-3.3-70b-versatile"
    DEEPSEEK_R1 = "openrouter:deepseek/deepseek-r1:free"


MODELS: Mapping[Agent, Model] = {
    Agent.ORCHESTRATOR: Model.GEMINI_FLASH,
    Agent.RECON: Model.LLAMA_70B,
    Agent.WEB: Model.GEMINI_FLASH,
    Agent.EXPLOIT: Model.DEEPSEEK_R1,
    Agent.TRIAGE: Model.LLAMA_70B,
}
