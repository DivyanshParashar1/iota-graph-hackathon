"""Embedders. The default HashEmbedder is local, deterministic across runs and processes, and 384-d.

HashEmbedder: lowercase word tokens (light stemming, stopwords dropped) plus bigrams, feature-hashed with
blake2b into signed buckets, then L2-normalized. Good enough for keyword-ish semantic search over our
templated documents, with zero dependencies. OpenAIEmbedder (text-embedding-3-small, 1536-d) is optional.
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
            return t[: -len(suf)] + ("y" if suf == "ies" else "")
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


class OpenAIEmbedder:
    """text-embedding-3-small over HTTPS. Needs OPENAI_API_KEY; the vector index must be 1536-d."""

    name = "openai"
    dim = 1536

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        import httpx

        out: list[list[float]] = []
        for i in range(0, len(texts), 256):
            r = httpx.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts[i : i + 256]},
                timeout=60,
            )
            r.raise_for_status()
            out += [d["embedding"] for d in r.json()["data"]]
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
    if s.ripple_embeddings == "openai" and s.openai_api_key:
        return OpenAIEmbedder(s.openai_api_key)
    return HashEmbedder(384)
