"""Shared fixtures: one golden embedded DB built once per test session (both tenants, DataCo sample of
3000 orders), copied for every test module that writes, so tests never see each other's actions."""

from __future__ import annotations

import os
import shutil
import time

import pytest

from ripple.db import TenantScope, close_db, get_db

SAMPLE = 3000


@pytest.fixture(scope="session")
def golden_path(tmp_path_factory):
    from ripple.ingest.build import build_all

    d = tmp_path_factory.mktemp("golden")
    path = d / "golden.db"
    db = get_db(path, mode="embedded")
    t0 = time.time()
    build_all(db, SAMPLE)
    print(f"\n[conftest] golden DB built in {time.time() - t0:.1f}s")
    close_db(db)
    return path


def open_copy(golden_path, tmp_path_factory, name: str):
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
    db = get_db(d / "full.db", mode="embedded")
    t0 = time.time()
    out = build_all(db, None)
    os.environ["RIPPLE_FULL_BUILD_SECONDS"] = f"{time.time() - t0:.1f}"
    db.build_report = out
    yield db
    close_db(db)


@pytest.fixture
def db_copy_path(golden_path, tmp_path):
    """A private copy of the golden DB file (not opened), for restart tests."""
    p = tmp_path / "ripple.db"
    shutil.copy(golden_path, p)
    return p
