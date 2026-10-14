"""Sentinel: event -> RiskBearing nodes -> Disruption -> Incident -> recall similar episodes."""

from __future__ import annotations

from ripple.agents.runtime import AgentRun

NAME = "sentinel"
TOOLS = ["match_event_to_entities", "create_disruption", "open_incident", "recall_similar_episodes", "get_playbook"]
ROLE = ("You are Sentinel. Match the event to graph entities, create the Disruption, open the Incident, then recall "
        "similar past episodes. Finish with one or two sentences: what was hit and the most similar past incident.")


def run_scripted(run: AgentRun, event: dict) -> str:
    m = run.call(NAME, "match_event_to_entities", event=event)
    d = run.call(NAME, "create_disruption", event=event, entity_ids=m.node_ids)
    run.call(NAME, "open_incident", disruption_id=d.data["disruption_id"], mode=run.mode)
    r = run.call(NAME, "recall_similar_episodes", incident_id=run.incident_id)
    eps = r.data["episodes"]
    if eps:
        e = eps[0]
        rate = e.get("playbook_success_rate")
        msg = (f"Opened {run.incident_id}: {m.summary}. Similar to {e['incident_id']} ({e['title']}, score "
               f"{e['score']:.2f}, outcome {e['outcome']})"
               + (f"; playbook {e['playbook_id']} has {rate:.0%} success." if e.get("playbook_id") and rate is not None
                  else "."))
    else:
        msg = f"Opened {run.incident_id}: {m.summary}. No similar past episodes."
    run.message(NAME, msg, [run.incident_id] + [e["id"] for e in eps[:1]], data={"recall": eps[:3]})
    return msg


def task(event: dict, incident_id: str) -> str:
    return (f"New event: {event}. The incident id will be {incident_id}. Use match_event_to_entities, then "
            f"create_disruption with the matched entity ids, then open_incident, then recall_similar_episodes for "
            f"{incident_id}.")
