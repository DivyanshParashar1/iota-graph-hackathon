"""Embedders. The default HashEmbedder is local, deterministic across runs and processes, and 384-d.

HashEmbedder: lowercase word tokens (light stemming, stopwords dropped) plus bigrams, feature-hashed with
blake2b into signed buckets, then L2-normalized. Good enough for keyword-ish semantic search over our
templated documents, with zero dependencies. OpenAICompatEmbedder (OpenRouter or OpenAI /embeddings) is optional.
"""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache

_TOKEN = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    "a an the and or of to in on for with by at from is are was were be been it its this that these those as "
    "we our us you your they their them he she his her i me my do does did what which who whom how why when "
    "where there here have has had not no so if then than into over about can could would should will shall "
    "any all some just also more most very up out".split()
)


def _stem(t: str) -> str:
    for suf in ("ing", "ies", "es", "s", "ed"):
        if len(t) > len(suf) + 3 and t.endswith(suf):
            t = t[: -len(suf)] + ("y" if suf == "ies" else "")
            break
    if len(t) > 4 and t.endswith("e"):  # approve/approved, expedite/expediting
        t = t[:-1]
    return t


def tokens(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


class HashEmbedder:
    name = "hash"

    def __init__(self, dim: int = 384):
        self.dim = dim

    def _bucket(self, feat: str) -> tuple[int, float]:
        h = hashlib.blake2b(feat.encode(), digest_size=8).digest()
        n = int.from_bytes(h, "little")
        return n % self.dim, (1.0 if (n >> 63) & 1 else -1.0)

    def embed(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        toks = tokens(text)
        feats = [(t, 1.0) for t in toks] + [(f"{a}_{b}", 0.7) for a, b in zip(toks, toks[1:])]
        for f, w in feats:
            i, s = self._bucket(f)
            v[i] += s * w
        norm = math.sqrt(sum(x * x for x in v))
        if norm == 0:
            v[0] = 1.0
            return v
        return [x / norm for x in v]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class OpenAICompatEmbedder:
    """Embeddings over an OpenAI-compatible /embeddings endpoint (OpenRouter or OpenAI). The vector index takes
    this embedder's `dim`: given, or probed from the model on first use."""

    def __init__(self, api_key: str, model: str, base_url: str, name: str, dim: int | None = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.name = name
        self._dim = dim

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._dim = len(self.embed("dimension probe"))
        return self._dim

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        import httpx

        out: list[list[float]] = []
        for i in range(0, len(texts), 256):
            r = httpx.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts[i : i + 256]},
                timeout=120,
            )
            r.raise_for_status()
            data = sorted(r.json()["data"], key=lambda d: d.get("index", 0))
            out += [d["embedding"] for d in data]
        return out

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]


def cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return 1.0 - dot / (na * nb)


@lru_cache
def get_embedder():
    from ripple.config import get_settings

    s = get_settings()
    if s.ripple_embeddings == "openrouter" and s.openrouter_api_key:
        return OpenAICompatEmbedder(s.openrouter_api_key, s.openrouter_embed_model, s.openrouter_base_url,
                                    "openrouter", s.ripple_embed_dim)
    if s.ripple_embeddings == "openai" and s.openai_api_key:
        return OpenAICompatEmbedder(s.openai_api_key, "text-embedding-3-small", "https://api.openai.com/v1",
                                    "openai", s.ripple_embed_dim or 1536)
    return HashEmbedder(384)
