"""What Jev's answers mean for autonomy. Jev decides; this module only applies fixed thresholds from config to
its probabilities, so the same answers always produce the same verdicts.

* The event is **auto** when Jev's most probable priority level is `critical` and P(critical) is at least
  `RIPPLE_AUTO_PRIORITY_MIN`. Critical means waiting for a person would make the decision moot.
* In an auto event: the top option of each exclusive group is `auto_approved` (a winning "wait" option only
  when `RIPPLE_AUTO_APPROVE_WAIT`), its siblings are `not_selected`, and each independent action with
  P(yes) >= `RIPPLE_AUTO_NOUL_MIN` is `auto_approved`; the rest stay `pending` for a human.
* Otherwise every option is `pending`, shown with Jev's probability, and a person approves.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ripple.config import get_settings
from ripple.decide.compile import PRIORITY_LEVELS, QuestionMap
from ripple.decide.jev import JevResult
from ripple.incident.models import DecisionPacket, is_wait


@dataclass(frozen=True)
class Thresholds:
    priority_min: float = 0.5
    noul_min: float = 0.6
    approve_wait: bool = True

    @classmethod
    def from_settings(cls, settings=None) -> Thresholds:
        s = settings or get_settings()
        return cls(s.ripple_auto_priority_min, s.ripple_auto_noul_min, s.ripple_auto_approve_wait)


@dataclass
class Verdict:
    group_id: str
    option_id: str
    mode: str
    probability: float  # Jev's P(this option) in its choice, or P(yes) for an independent action
    rank: int  # 1 = Jev's top option in its group; independent actions rank by P(yes) within the group
    status: str  # auto_approved | pending | not_selected
    reason: str


@dataclass
class Outcome:
    priority: str
    priority_probabilities: dict[str, float]
    auto: bool
    reason: str
    verdicts: list[Verdict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {**asdict(self), "verdicts": [asdict(v) for v in self.verdicts]}

    def by_option(self) -> dict[str, Verdict]:
        return {v.option_id: v for v in self.verdicts}


def apply(packet: DecisionPacket, result: JevResult, qmap: QuestionMap,
          thresholds: Thresholds | None = None) -> Outcome:
    t = thresholds or Thresholds.from_settings()
    pr = result[qmap.priority]
    order = [name for name, _ in PRIORITY_LEVELS]
    top_level = max(order, key=lambda n: (pr.p(n), order.index(n)))  # a tie goes to the more urgent level
    p_crit = pr.p("critical")
    auto = top_level == "critical" and p_crit >= t.priority_min
    if auto:
        reason = f"critical (P={p_crit:.2f} >= {t.priority_min}): no time for a human approval"
    elif top_level == "critical":
        reason = f"critical is the top level but P={p_crit:.2f} < {t.priority_min}: a human decides"
    else:
        reason = f"priority {top_level} (P={pr.p(top_level):.2f}): a human decides"
    out = Outcome(priority=top_level, priority_probabilities={n: pr.p(n) for n in order}, auto=auto, reason=reason)

    choice_of = {gid: q for q, gid in qmap.choice.items()}
    noul_of = {oid: q for q, (_, oid) in qmap.noul.items()}
    for g in packet.decision_groups:
        if g.mode == "exclusive":
            ans = result[choice_of[g.id]]
            ranked = sorted(g.options, key=lambda o: (-ans.p(o.id), o.id))
            for rank, o in enumerate(ranked, 1):
                p = ans.p(o.id)
                if not auto:
                    status, why = "pending", f"Jev ranks this {rank} of {len(ranked)} (P={p:.2f})"
                elif rank == 1 and (not is_wait(o) or t.approve_wait):
                    status, why = "auto_approved", f"Jev's choice in a critical event (P={p:.2f})"
                elif rank == 1:
                    status, why = "pending", "Jev chose to wait; holds are not auto-approved by config"
                else:
                    status, why = "not_selected", f"another option was Jev's choice (P={p:.2f})"
                out.verdicts.append(Verdict(g.id, o.id, g.mode, p, rank, status, why))
        else:
            probs = {o.id: result[noul_of[o.id]].p_true for o in g.options}
            ranked = sorted(g.options, key=lambda o: (-probs[o.id], o.id))
            for rank, o in enumerate(ranked, 1):
                p = probs[o.id]
                if auto and p >= t.noul_min:
                    status, why = "auto_approved", f"P(do it now)={p:.2f} >= {t.noul_min} in a critical event"
                elif auto:
                    status, why = "pending", f"P(do it now)={p:.2f} < {t.noul_min}: left for a human"
                else:
                    status, why = "pending", f"P(do it now)={p:.2f}"
                out.verdicts.append(Verdict(g.id, o.id, g.mode, p, rank, status, why))
    return out
