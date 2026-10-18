"""Google Vertex AI (RIPPLE_LLM_PROVIDER=vertex): Gemini or Claude, picked by VERTEX_MODEL.

Gemini (`gemini-*`) goes through Vertex's OpenAI-compatible chat endpoint, so it is `OpenRouterClient`'s
translation pointed at Vertex; Gemini 3's thought signatures ride on `ToolCall.extra` and are sent back on the
next turn, which its multi-turn tool use requires. Claude (`claude-*`) is `AnthropicClient` over the pinned SDK's
`AnthropicVertex` transport.

Auth needs no extra dependency: the SDK's own path wants `google-auth`, which is not pinned, so the bearer token
comes from VERTEX_ACCESS_TOKEN or, failing that, `gcloud auth print-access-token` (cached and refreshed before its
hour runs out). Jev never comes here - it stays on its own endpoint.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time

from ripple.llm.anthropic_client import AnthropicClient
from ripple.llm.base import LLMError, Reply
from ripple.llm.openrouter import OpenRouterClient

_TOKEN_TTL = 45 * 60  # gcloud tokens live an hour; refresh well before
MALFORMED_RETRIES = 3
_lock = threading.Lock()
_cache: dict = {"token": None, "at": 0.0}


def _gcloud(*args: str) -> str:
    exe = shutil.which("gcloud")
    if not exe:
        raise LLMError("Vertex AI needs VERTEX_ACCESS_TOKEN or the `gcloud` CLI (gcloud auth login)")
    try:
        out = subprocess.run([exe, *args], capture_output=True, text=True, timeout=60, check=True)
    except subprocess.CalledProcessError as e:
        raise LLMError(f"gcloud {' '.join(args)} failed: {e.stderr.strip()[:500]}") from None
    except subprocess.TimeoutExpired:
        raise LLMError(f"gcloud {' '.join(args)} timed out") from None
    return out.stdout.strip()


def access_token(static: str | None = None) -> str:
    """The bearer token: the configured one, else a cached `gcloud auth print-access-token`."""
    if static:
        return static
    with _lock:
        if not _cache["token"] or time.time() - _cache["at"] > _TOKEN_TTL:
            _cache["token"] = _gcloud("auth", "print-access-token")
            _cache["at"] = time.time()
        return _cache["token"]


def default_project() -> str | None:
    """`gcloud config get-value project`, or None when gcloud is missing or has no project set."""
    try:
        return _gcloud("config", "get-value", "project") or None
    except LLMError:
        return None


def endpoint(project_id: str, region: str) -> str:
    host = "aiplatform.googleapis.com" if region == "global" else f"{region}-aiplatform.googleapis.com"
    return f"https://{host}/v1/projects/{project_id}/locations/{region}/endpoints/openapi"


class GeminiVertexClient(OpenRouterClient):
    """Gemini on Vertex AI through its OpenAI-compatible chat completions endpoint."""

    name = "vertex"

    def __init__(self, project_id: str, region: str, model: str, token: str | None = None, http=None):
        super().__init__("", f"google/{model}" if "/" not in model else model, endpoint(project_id, region), http)
        self._static_token = token

    def payload(self, *args) -> dict:
        body = super().payload(*args)
        if "reasoning" in body:  # Vertex takes OpenAI's flat field, not OpenRouter's object
            body["reasoning_effort"] = body.pop("reasoning")["effort"]
        return body

    def complete(self, **kw) -> Reply:
        self._headers = {"Authorization": f"Bearer {access_token(self._static_token)}"}
        for _ in range(MALFORMED_RETRIES):  # Gemini intermittently emits a call it cannot parse; a resample fixes it
            reply = super().complete(**kw)
            if reply.stop_reason != "malformed_function_call":
                return reply
        raise LLMError(f"{self.model} produced a malformed function call {MALFORMED_RETRIES} times")


def make_client(project_id: str, region: str, model: str, token: str | None = None):
    """The Vertex client for this model: Claude through the Anthropic SDK, anything else as Gemini."""
    if model.startswith("claude"):
        return ClaudeVertexClient(project_id, region, model, token)
    return GeminiVertexClient(project_id, region, model, token)


class ClaudeVertexClient(AnthropicClient):
    name = "vertex"

    def __init__(self, project_id: str, region: str, model: str, token: str | None = None, client=None):
        from anthropic import AnthropicVertex

        self._static_token = token
        super().__init__("", model, client=client or AnthropicVertex(
            project_id=project_id, region=region, access_token=token or "pending"))

    def complete(self, *, system: str = "", messages: list[dict], tools: list[dict] | None = None,
                 schema: dict | None = None, max_tokens: int | None = None, effort: str | None = None) -> Reply:
        self._c.access_token = access_token(self._static_token)
        return super().complete(system=system, messages=messages, tools=tools, schema=schema,
                                max_tokens=max_tokens, effort=effort)
