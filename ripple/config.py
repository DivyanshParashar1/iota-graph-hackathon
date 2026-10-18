"""Settings, read from the environment and `.env` (see .env.example).

v2 has no fixed tenant list: a tenant is created when a company starts onboarding, and its id is validated by
shape (`ripple.db.valid_tenant_id`) rather than looked up in a constant.
"""

from __future__ import annotations

import os
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
    falkordb_ssl: bool = False  # TLS to the server (FalkorDB Cloud)
    falkordb_db: int = 0  # Redis logical database (remote mode); tests give each fixture its own

    # LLM provider. "claude_code" (the default) runs on the local Claude Code login - no API key.
    # "openrouter" and "anthropic" need their key. "vertex" is Gemini or Claude on Google Vertex AI (gcloud
    # login or VERTEX_ACCESS_TOKEN). "auto" prefers claude_code, then openrouter, then anthropic.
    ripple_llm_provider: str = "claude_code"  # claude_code | vertex | openrouter | anthropic | auto
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
    vertex_project_id: str | None = None  # empty = `gcloud config get-value project`
    vertex_region: str = "global"  # global | us | eu | a region such as us-east5
    vertex_model: str = "gemini-3.1-pro-preview"  # gemini-* or claude-* (Claude needs Vertex quota for it)
    vertex_access_token: str | None = None  # empty = `gcloud auth print-access-token`, refreshed as it expires

    # Onboarding
    ripple_tenants_dir: str = "tenants"  # file-side mirror: experts/*.md, uploads/, exports/
    ripple_max_upload_mb: int = 25
    ripple_llm_log_dir: str | None = None  # set to capture every LLM request/response as JSON

    # Jev (TypeSafe's decision model, docs/m8_decision_pipeline.md). Not an LLM: it never goes through
    # ripple/llm. The key defaults to OPENROUTER_API_KEY; point the base URL at https://api.typesafe.ai/v1 with
    # a TypeSafe key to call it directly.
    jev_api_key: str | None = None
    jev_base_url: str = "https://openrouter.ai/api/v1"
    jev_model: str = "typesafe/jev-1.13"
    jev_timeout: float = 30

    # Incident pipeline. Every threshold below is policy applied to Jev's probabilities, not a model choice.
    ripple_webhook_secret: str | None = None  # when set, POST /api/events/* needs X-Ripple-Webhook-Secret
    ripple_incident_max_rounds: int = 4  # hard cap on orchestrator <-> expert rounds
    ripple_incident_max_asks: int = 6  # expert questions per round
    ripple_expert_relevance_min: float = 0.5  # P(relevant) for an expert to be consulted
    ripple_evidence_sufficient_min: float = 0.6  # P(sufficient) for the Q&A loop to stop early
    ripple_auto_priority_min: float = 0.5  # P(critical) needed, with critical the top level, to skip a human
    ripple_auto_noul_min: float = 0.6  # P(yes) for an independent action to be approved in a critical event
    ripple_auto_approve_wait: bool = True  # in a critical event, a winning "wait" option is approved as a hold

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
        if p == "vertex":
            ok = bool(self.vertex_access_token) or bool(shutil.which("gcloud")) or bool(os.environ.get("K_SERVICE"))
            return "vertex" if ok else None
        if p == "auto":
            if cc:
                return "claude_code"
            if self.openrouter_api_key:
                return "openrouter"
            if self.anthropic_api_key:
                return "anthropic"
        return None

    @property
    def jev_key(self) -> str | None:
        """The key Jev is called with: its own, else the OpenRouter key."""
        return self.jev_api_key or self.openrouter_api_key or None

    @property
    def has_jev(self) -> bool:
        return bool(self.jev_key)

    @property
    def has_llm(self) -> bool:
        return self.llm_provider is not None

    @property
    def model_name(self) -> str:
        """The model id/alias of the active provider, for display and for `_Session.model`."""
        return {"claude_code": self.claude_code_model, "openrouter": self.openrouter_model,
                "anthropic": self.ripple_model, "vertex": self.vertex_model}.get(self.llm_provider or "", "none")


@lru_cache
def get_settings() -> Settings:
    return Settings()
