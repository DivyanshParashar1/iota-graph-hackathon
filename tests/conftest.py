"""Shared fixtures: one golden embedded DB built once per test session (both tenants, DataCo sample of
3000 orders), copied for every test module that writes, so tests never see each other's actions."""

from __future__ import annotations

import os
import shutil
import time

import pytest

# Tests stay offline and deterministic whatever .env holds: hash embeddings, no LLM provider keys
# (environment variables win over .env). The LLM loop is tested through FakeAnthropic.
os.environ.update(RIPPLE_EMBEDDINGS="hash", OPENROUTER_API_KEY="", ANTHROPIC_API_KEY="", OPENAI_API_KEY="")

from ripple.db import TenantScope, close_db, get_db  # noqa: E402

SAMPLE = 3000
# RIPPLE_DB_MODE=remote runs the whole suite against a FalkorDB server (e.g. docker run -p 6379:6379
# falkordb/falkordb). Each fixture then gets its own Redis logical database, rebuilt from scratch.
REMOTE = os.environ.get("RIPPLE_DB_MODE") == "remote"
_next_index = iter(range(1, 10_000))


def remote_db(index: int | None = None):
    from ripple.ingest.build import build_all

    idx = index if index is not None else 1 + (next(_next_index) % 13)
    db = get_db(mode="remote", db_index=idx)
    db.flush()
    build_all(db, SAMPLE)
    return db


def open_db(ref):
    """Open a DB reference: a .db path (embedded) or ('remote', index)."""
    if isinstance(ref, tuple):
        return get_db(mode="remote", db_index=ref[1])
    return get_db(ref, mode="embedded")


@pytest.fixture(scope="session")
def golden_path(tmp_path_factory):
    from ripple.ingest.build import build_all

    if REMOTE:
        return None
    d = tmp_path_factory.mktemp("golden")
    path = d / "golden.db"
    db = get_db(path, mode="embedded")
    t0 = time.time()
    build_all(db, SAMPLE)
    print(f"\n[conftest] golden DB built in {time.time() - t0:.1f}s")
    close_db(db)
    return path


def open_copy(golden_path, tmp_path_factory, name: str):
    if REMOTE:
        return remote_db()
    d = tmp_path_factory.mktemp(name)
    p = d / "ripple.db"
    shutil.copy(golden_path, p)
    return get_db(p, mode="embedded")


@pytest.fixture(scope="session")
def built_db(golden_path, tmp_path_factory):
    db = open_copy(golden_path, tmp_path_factory, "built")
    yield db
    close_db(db)


@pytest.fixture(scope="module")
def fresh_db(golden_path, tmp_path_factory):
    """A private copy of the golden DB for a test module that writes."""
    db = open_copy(golden_path, tmp_path_factory, "fresh")
    yield db
    close_db(db)


@pytest.fixture(scope="session")
def scope_dataco(built_db):
    return TenantScope("dataco", built_db)


@pytest.fixture(scope="session")
def scope_nova(built_db):
    return TenantScope("nova", built_db)


@pytest.fixture(scope="session")
def sample_ids():
    from ripple.ingest.sample import sample_order_ids

    return sample_order_ids(SAMPLE)


@pytest.fixture(scope="session")
def full_db(tmp_path_factory):
    """The full DataCo dataset (slow)."""
    from ripple.ingest.build import build_all

    d = tmp_path_factory.mktemp("full")
    if REMOTE:
        db = get_db(mode="remote", db_index=14)
        db.flush()
    else:
        db = get_db(d / "full.db", mode="embedded")
    t0 = time.time()
    out = build_all(db, None)
    os.environ["RIPPLE_FULL_BUILD_SECONDS"] = f"{time.time() - t0:.1f}"
    db.build_report = out
    yield db
    close_db(db)


@pytest.fixture
def db_copy_path(golden_path, tmp_path):
    """A private copy of the golden DB (not opened), for restart tests: a .db path, or ('remote', index)."""
    if REMOTE:
        close_db(remote_db(15))
        return ("remote", 15)
    p = tmp_path / "ripple.db"
    shutil.copy(golden_path, p)
    return p
