"""LangGraph state: ids only. Everything substantive lives on the Incident blackboard in FalkorDB."""

from __future__ import annotations

from typing import Literal, TypedDict


class IncidentState(TypedDict, total=False):
    tenant_id: str
    incident_id: str | None
    disruption_id: str | None
    event: dict
    mode: Literal["scripted", "llm"]
