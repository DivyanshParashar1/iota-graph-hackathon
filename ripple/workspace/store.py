"""Employees, chat threads and chat messages, as `_`-prefixed platform nodes in the tenant's ops graph."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from ripple.db import TenantScope, new_id, now_ms


class Employee(BaseModel):
    id: str = ""
    name: str
    title: str = ""
    role_ids: list[str] = Field(default_factory=list)  # _ExpertRole ids this person works as
    ts: int = 0


def _unj(text: Any, default: Any) -> Any:
    try:
        return json.loads(text) if text else default
    except (TypeError, ValueError):
        return default


def save_employee(scope: TenantScope, e: Employee) -> Employee:
    e = e.model_copy(update={"id": e.id or new_id("EMP"), "ts": e.ts or now_ms()})
    scope.ops.run("employee_upsert", {"row": {"id": e.id, "name": e.name, "title": e.title,
                                              "roles_json": json.dumps(e.role_ids), "ts": e.ts}})
    return e


def list_employees(scope: TenantScope) -> list[Employee]:
    return [Employee(id=r["id"], name=r["name"] or "", title=r["title"] or "",
                     role_ids=_unj(r["roles_json"], []), ts=r["ts"] or 0)
            for r in scope.ops.run("employees_list", {})]


def get_employee(scope: TenantScope, eid: str) -> Employee | None:
    return next((e for e in list_employees(scope) if e.id == eid), None)


def delete_employee(scope: TenantScope, eid: str) -> None:
    scope.ops.run("employee_delete", {"id": eid})


def save_thread(scope: TenantScope, eid: str, tid: str = "", title: str = "") -> dict:
    ts = now_ms()
    row = {"id": tid or new_id("THR"), "employee_id": eid, "updated_at": ts}
    if not tid:
        row["ts"] = ts
    if title:
        row["title"] = title
    scope.ops.run("chat_thread_upsert", {"eid": eid, "row": row})
    return row


def list_threads(scope: TenantScope, eid: str, limit: int = 30) -> list[dict]:
    return scope.ops.run("chat_threads_list", {"eid": eid, "limit": limit})


def delete_thread(scope: TenantScope, tid: str) -> None:
    scope.ops.run("chat_thread_delete", {"id": tid})


def list_chat(scope: TenantScope, tid: str) -> list[dict]:
    return [{**{k: r[k] for k in ("id", "role", "text", "seq", "ts")}, "payload": _unj(r["payload_json"], {})}
            for r in scope.ops.run("chat_messages_list", {"tid": tid})]


def append_chat(scope: TenantScope, tid: str, role: str, text: str, payload: dict | None = None) -> dict:
    seq = len(scope.ops.run("chat_messages_list", {"tid": tid})) + 1
    row = {"id": new_id("CMS"), "role": role, "text": text, "payload_json": json.dumps(payload or {}, default=str),
           "seq": seq, "ts": now_ms()}
    scope.ops.run("chat_message_append", {"tid": tid, "row": row})
    return {**{k: row[k] for k in ("id", "role", "text", "seq", "ts")}, "payload": payload or {}}
