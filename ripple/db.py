"""FalkorDB access: embedded (falkordblite) or remote, plus tenant scoping.

Every product query goes through a `TenantScope`, which can only open the two graphs that belong to its
tenant (`tenant_<id>` for operational data, `mem_<id>` for agent memory). Isolation is enforced here, in
code, not in prompts.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from ripple.config import TENANTS, Settings, get_settings
from ripple.graph.queries import Q


class TenantViolation(PermissionError):
    """Raised when code tries to open a graph that does not belong to its tenant."""


def _col_name(h: Any) -> str:
    return h[1] if isinstance(h, (list, tuple)) else str(h)


class GraphHandle:
    """Thin wrapper over a falkordb Graph: rows come back as dicts keyed by column name."""

    def __init__(self, graph, name: str):
        self._g = graph
        self.name = name

    def query(self, cypher: str, params: dict | None = None, *, read_only: bool = False) -> list[dict]:
        fn = self._g.ro_query if read_only else self._g.query
        res = fn(cypher, params or {})
        cols = [_col_name(h) for h in (res.header or [])]
        return [dict(zip(cols, row)) for row in res.result_set]

    def run(self, qname: str, params: dict | None = None) -> list[dict]:
        """Run a named query from graph/queries/<qname>.cypher."""
        return self.query(Q(qname), params)

    def raw(self, cypher: str, params: dict | None = None):
        return self._g.query(cypher, params or {})

    def delete(self) -> None:
        try:
            self._g.delete()
        except Exception:  # noqa: BLE001 - deleting a missing graph is fine
            pass


class DB:
    """One FalkorDB connection (embedded server or remote client)."""

    def __init__(self, mode: str = "embedded", path: str | Path | None = None, settings: Settings | None = None,
                 db_index: int | None = None):
        s = settings or get_settings()
        self.mode = mode
        self.path = Path(path) if path else s.db_path
        self.db_index = s.falkordb_db if db_index is None else db_index
        if mode == "embedded":
            from redislite.falkordb_client import FalkorDB

            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._db = FalkorDB(str(self.path))
        elif mode == "remote":
            import redis
            from falkordb import FalkorDB

            pool = redis.ConnectionPool(host=s.falkordb_host, port=s.falkordb_port, db=self.db_index,
                                        username=s.falkordb_username or None, password=s.falkordb_password or None,
                                        decode_responses=True)
            self._db = FalkorDB(connection_pool=pool)
        else:
            raise ValueError(f"unknown RIPPLE_DB_MODE {mode!r}")
        self._lock = threading.Lock()
        self.closed = False

    def graph(self, name: str) -> GraphHandle:
        return GraphHandle(self._db.select_graph(name), name)

    def list_graphs(self) -> list[str]:
        try:
            return sorted(self._db.list_graphs() or [])
        except Exception:  # noqa: BLE001
            return []

    def flush(self) -> None:
        """Delete every graph in this database (tests / rebuilds only)."""
        self._db.connection.flushdb()

    def save(self) -> None:
        """Force a snapshot so a hard kill can't lose memory (embedded mode)."""
        with self._lock:
            try:
                self._db.connection.execute_command("SAVE")
            except Exception:  # noqa: BLE001 - remote servers may disallow SAVE
                pass

    def close(self) -> None:
        """Save and, in embedded mode, stop the private redis-server.

        redislite only shuts the server down when it holds the sole client connection; worker threads leave
        extra pooled connections open, so drop them first and force a SHUTDOWN if the server is still up."""
        if self.closed:
            return
        if self.mode == "remote":
            self._db.connection.connection_pool.disconnect()
            self.closed = True
            return
        self.save()
        if self.mode == "embedded":
            client = self._db.connection
            try:
                client.connection_pool.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self._db.close()
            try:
                if client.pid:
                    client.shutdown(save=True, now=True, force=True)
            except Exception:  # noqa: BLE001 - the server is already gone
                pass
        self.closed = True


_DBS: dict[str, DB] = {}
_DBS_LOCK = threading.Lock()


def get_db(path: str | Path | None = None, mode: str | None = None, settings: Settings | None = None,
           db_index: int | None = None) -> DB:
    """Return the process-wide DB for a path (embedded) or the remote server (+ logical db). Cached."""
    s = settings or get_settings()
    mode = mode or s.ripple_db_mode
    idx = s.falkordb_db if db_index is None else db_index
    key = f"remote:{s.falkordb_host}:{s.falkordb_port}/{idx}" if mode == "remote" else str(Path(path or s.db_path).resolve())
    with _DBS_LOCK:
        db = _DBS.get(key)
        if db is None or db.closed:
            db = DB(mode, path, s, idx)
            _DBS[key] = db
        return db


def close_db(db: DB) -> None:
    with _DBS_LOCK:
        for k, v in list(_DBS.items()):
            if v is db:
                del _DBS[k]
    db.close()


def ops_graph_name(tenant_id: str) -> str:
    return f"tenant_{tenant_id}"


def mem_graph_name(tenant_id: str) -> str:
    return f"mem_{tenant_id}"


class TenantScope:
    """Everything a tool may touch for one tenant. Raises on any other graph name."""

    def __init__(self, tenant_id: str, db: DB | None = None):
        if tenant_id not in TENANTS:
            raise TenantViolation(f"unknown tenant {tenant_id!r}")
        self.tenant_id = tenant_id
        self.db = db or get_db()
        self._allowed = {ops_graph_name(tenant_id), mem_graph_name(tenant_id)}

    def graph(self, name: str) -> GraphHandle:
        if name not in self._allowed:
            raise TenantViolation(f"tenant {self.tenant_id!r} may not open graph {name!r}")
        return self.db.graph(name)

    @property
    def ops(self) -> GraphHandle:
        return self.graph(ops_graph_name(self.tenant_id))

    @property
    def mem(self) -> GraphHandle:
        return self.graph(mem_graph_name(self.tenant_id))

    def flush(self) -> None:
        """Delete every graph in this database (tests / rebuilds only)."""
        self._db.connection.flushdb()

    def save(self) -> None:
        self.db.save()

    def __repr__(self) -> str:
        return f"TenantScope({self.tenant_id!r})"


def now_ms() -> int:
    return int(time.time() * 1000)
