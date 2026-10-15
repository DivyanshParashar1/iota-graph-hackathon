"""Settings, read from the environment and `.env` (see .env.example).

v2 has no fixed tenant list: a tenant is created when a company starts onboarding, and its id is validated by
shape (`ripple.db.valid_tenant_id`) rather than looked up in a constant.
"""

from __future__ import annotations

import shutil
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from ripple import ROOT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    ripple_db_mode: str = "embedded"  # embedded | remote
    ripple_db_path: str = "var/ripple.db"
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_username: str | None = None
    falkordb_password: str | None = None
    falkordb_db: int = 0  # Redis logical database (remote mode); tests give each fixture its own

    # LLM provider. "claude_code" (the default) runs on the local Claude Code login - no API key.
    # "openrouter" and "anthropic" need their key. "auto" prefers claude_code, then openrouter, then anthropic.
    ripple_llm_provider: str = "claude_code"  # claude_code | openrouter | anthropic | auto
    ripple_llm_effort: str = "medium"  # low | medium | high
    ripple_llm_max_tokens: int = 16000
    claude_code_bin: str = "claude"
    claude_code_model: str = "opus"  # a `claude --model` alias or full model id
    claude_code_bridge_url: str | None = None  # e.g. http://host.docker.internal:8765; empty = run the CLI
    claude_code_bridge_token: str | None = None
    claude_code_timeout: float = 600
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-opus-5.5"
    anthropic_api_key: str | None = None
    ripple_model: str = "claude-opus-5-5"  # Anthropic API model id

    # Onboarding
    ripple_tenants_dir: str = "tenants"  # file-side mirror: experts/*.md, uploads/, exports/
    ripple_max_upload_mb: int = 25
    ripple_llm_log_dir: str | None = None  # set to capture every LLM request/response as JSON

    api_cors_origins: str = "http://localhost:5173"

    @property
    def db_path(self) -> Path:
        p = Path(self.ripple_db_path)
        return p if p.is_absolute() else ROOT / p

    @property
    def tenants_dir(self) -> Path:
        p = Path(self.ripple_tenants_dir)
        return p if p.is_absolute() else ROOT / p

    @property
    def llm_provider(self) -> str | None:
        """The provider that will actually be used, or None when nothing is configured."""
        p = self.ripple_llm_provider
        cc = bool(self.claude_code_bridge_url) or bool(shutil.which(self.claude_code_bin))
        if p == "claude_code":
            return "claude_code" if cc else None
        if p == "openrouter":
            return "openrouter" if self.openrouter_api_key else None
        if p == "anthropic":
            return "anthropic" if self.anthropic_api_key else None
        if p == "auto":
            if cc:
                return "claude_code"
            if self.openrouter_api_key:
                return "openrouter"
            if self.anthropic_api_key:
                return "anthropic"
        return None

    @property
    def has_llm(self) -> bool:
        return self.llm_provider is not None

    @property
    def model_name(self) -> str:
        """The model id/alias of the active provider, for display and for `_Session.model`."""
        return {"claude_code": self.claude_code_model, "openrouter": self.openrouter_model,
                "anthropic": self.ripple_model}.get(self.llm_provider or "", "none")


@lru_cache
def get_settings() -> Settings:
    return Settings()
