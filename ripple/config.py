"""Settings, read from the environment and `.env` (see .env.example)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

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

    anthropic_api_key: str | None = None
    ripple_model: str = "claude-opus-5-5"
    ripple_agent_mode: str = "scripted"  # default mode for incidents

    ripple_embeddings: str = "hash"  # hash | openai
    openai_api_key: str | None = None
    ripple_graphiti: bool = False

    ripple_autobuild: bool = True
    ripple_sample_orders: int | None = None  # None = full DataCo
    api_cors_origins: str = "http://localhost:5173"

    # Auto-approval policy for REROUTE_ORDERS
    auto_reroute_max_added_days: float = 3.0
    auto_reroute_max_orders: int = 50

    @property
    def db_path(self) -> Path:
        p = Path(self.ripple_db_path)
        return p if p.is_absolute() else ROOT / p

    @property
    def has_llm(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
