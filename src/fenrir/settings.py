"""Runtime settings, loaded from the environment / `.env` via pydantic-settings."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from fenrir.config import Agent

_ROOT = Path(__file__).resolve().parents[2]


class ApprovalSettings(BaseModel):
    """Per-agent human-approval gating. `require_approval_exploit` is a
    property, not a field: there is no env var or constructor argument that
    can set it, so exploit is always gated regardless of configuration."""

    require_approval_recon: bool = True
    require_approval_web: bool = True

    @property
    def require_approval_exploit(self) -> bool:
        return True

    def requires_approval(self, agent: Agent) -> bool:
        return {
            Agent.RECON: self.require_approval_recon,
            Agent.WEB: self.require_approval_web,
            Agent.EXPLOIT: self.require_approval_exploit,
        }.get(agent, True)  # unknown agent -> safe default: require approval


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_nested_delimiter="__")
    google_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    hexstrike_server: str = "http://localhost:8888"
    hexstrike_mcp_path: Path = _ROOT.parent / "hexstrike-ai" / "hexstrike_mcp.py"
    approval: ApprovalSettings = ApprovalSettings()

    def model_post_init(self, _context: Any, /) -> None:
        for var, secret in (
            ("GOOGLE_API_KEY", self.google_api_key),
            ("GROQ_API_KEY", self.groq_api_key),
            ("OPENROUTER_API_KEY", self.openrouter_api_key),
        ):
            if secret and not os.environ.get(var):
                os.environ[var] = secret.get_secret_value()


settings = Settings()
