"""Runtime settings, loaded from the environment / `.env` via pydantic-settings."""

import os
from pathlib import Path
from typing import Any

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    google_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    hexstrike_server: str = "http://localhost:8888"
    hexstrike_mcp_path: Path = _ROOT.parent / "hexstrike-ai" / "hexstrike_mcp.py"
    require_approval: bool = True

    def model_post_init(self, _context: Any, /) -> None:
        for var, secret in (
            ("GOOGLE_API_KEY", self.google_api_key),
            ("GROQ_API_KEY", self.groq_api_key),
            ("OPENROUTER_API_KEY", self.openrouter_api_key),
        ):
            if secret and not os.environ.get(var):
                os.environ[var] = secret.get_secret_value()


settings = Settings()
