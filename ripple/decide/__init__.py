"""Decisions. Jev - TypeSafe's decision model - is the only component in Ripple that decides anything.

    jev.py         the client: JevRequest -> JevResult (typed answers with probabilities), over HTTP
    compile.py     DecisionPacket -> JevRequest, and the smaller requests the orchestrator needs answered
    policy.py      what Jev's probabilities mean for autonomy: auto-approve or a human queue
    precedents.py  documented human decisions in real disruptions, rendered into Jev's state

Every LLM agent upstream (orchestrator, experts, analyst, comms, planner) only generates evidence, drafts and
options. See docs/m8_decision_pipeline.md.
"""
