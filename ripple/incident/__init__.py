"""The incident pipeline (M8): a reported event becomes an investigated, decided incident.

    models.py     the agents' structured replies and the DecisionPacket
    agents/       orchestrator, analyst, comms, planner - each generates, none decides
    validate.py   referential checks on every agent reply
    store.py      `_Incident`, `_Option`, `_JevDecision`, `_Approval` in FalkorDB
    pipeline.py   the run, approvals and live impact

Decisions are Jev's (`ripple.decide`). See docs/m8_decision_pipeline.md.
"""
