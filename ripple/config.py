"""Settings, read from the environment and `.env` (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ripple import ROOT

TENANTS = ("dataco", "nova")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    ripple_db_mode: str = "embedded"  # embedded | remote
    ripple_db_path: str = "var/ripple.db"
    falkordb_host: str = "localhost"
    falkordb_port: int = 6379
    falkordb_username: str | None = None
    falkordb_password: str | None = None
    falkordb_db: int = 0  # Redis logical database (remote mode); tests give each fixture its own

    # LLM provider: "auto" picks OpenRouter when OPENROUTER_API_KEY is set, else Anthropic when its key is set
    ripple_llm_provider: str = "auto"  # auto | openrouter | anthropic
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-opus-5.5"
    anthropic_api_key: str | None = None
    ripple_model: str = "claude-opus-5-5"  # Anthropic API model id
    ripple_agent_mode: str = "scripted"  # default mode for incidents

    ripple_embeddings: str = "hash"  # hash | openrouter | openai
    openrouter_embed_model: str = "openai/text-embedding-3-small"
    ripple_embed_dim: int | None = None  # remote embedders: None = probe the model once
    openai_api_key: str | None = None
    ripple_graphiti: bool = False

    ripple_autobuild: bool = True
    ripple_sample_orders: int | None = None  # None = full DataCo
    api_cors_origins: str = "http://localhost:5173"

    # Auto-approval policy for REROUTE_ORDERS
    auto_reroute_max_added_days: float = 3.0
    auto_reroute_max_orders: int = 50

    @field_validator("ripple_embed_dim", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        return None if v == "" else v

    @property
    def db_path(self) -> Path:
        p = Path(self.ripple_db_path)
        return p if p.is_absolute() else ROOT / p

    @property
    def llm_provider(self) -> str | None:
        """The provider LLM mode will use, or None when its key is missing."""
        p = self.ripple_llm_provider
        if p in ("auto", "openrouter") and self.openrouter_api_key:
            return "openrouter"
        if p in ("auto", "anthropic") and self.anthropic_api_key:
            return "anthropic"
        return None

    @property
    def has_llm(self) -> bool:
        return self.llm_provider is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
