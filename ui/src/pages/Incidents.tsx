import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, streamSteps } from "../api";
import type { IncidentDetail, IncidentGroup, IncidentOption, IncidentRow, Step } from "../api";
import StepStream from "../components/Chat/StepStream";
import { Icon } from "../components/icons";
import { Btn, Card, Chip, ErrorLine, PageHeader, statusColor } from "../components/ui";

const RUNNING = new Set(["received", "consulting", "analysing", "planning", "deciding"]);
const LEVELS = ["low", "medium", "high", "critical"];

const pct = (p: number | null | undefined) => (p == null ? "-" : `${Math.round(p * 100)}%`);

function Bar({ p, tone = "bg-sky-500" }: { p: number | null | undefined; tone?: string }) {
  return (
    <div className="h-[2px] w-full bg-line">
      <div className={`h-full ${tone}`} style={{ width: `${Math.round((p ?? 0) * 100)}%` }} />
    </div>
  );
}

const label = (s: string) => s.replace(/_/g, " ");

const CONF_TONE: Record<string, string> = {
  fact: "text-emerald-300",
  ballpark: "text-amber-300",
  unknown: "text-rose-300",
};

/** Card tint and status badge per option status: green approved, red rejected, amber superseded, blue awaiting. */
const OPTION_THEME: Record<string, { card: string; badge: string; text: string; label: string }> = {
  approved: { card: "border-l-4 border-l-emerald-500 bg-emerald-400/[0.07]", badge: "bg-emerald-500 text-black", text: "text-emerald-300", label: "✓ Approved" },
  auto_approved: { card: "border-l-4 border-l-emerald-500 bg-emerald-400/[0.07]", badge: "bg-emerald-500 text-black", text: "text-emerald-300", label: "✓ Auto-approved" },
  rejected: { card: "border-l-4 border-l-rose-500 bg-rose-400/[0.07]", badge: "bg-rose-500 text-black", text: "text-rose-300", label: "✕ Rejected" },
  superseded: { card: "border-l-4 border-l-amber-500 bg-amber-400/[0.05] opacity-80", badge: "bg-amber-400 text-black", text: "text-amber-300", label: "Superseded" },
  not_selected: { card: "border-l-4 border-l-slate-600 bg-sunken/40 opacity-75", badge: "bg-slate-600 text-white", text: "text-muted", label: "Not selected" },
  pending: { card: "border-l-4 border-l-sky-500 bg-sky-400/[0.06]", badge: "bg-sky-500 text-black", text: "text-sky-300", label: "Awaiting decision" },
};
const DEFAULT_THEME = OPTION_THEME.pending;

function Kicker({ children }: { children: React.ReactNode }) {
  return <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-faint">{children}</div>;
}

function MetricTile({ name, value, unit, basis }: { name: string; value: unknown; unit?: string; basis?: string[] }) {
  return (
    <div className="border border-line bg-sunken px-3 py-2">
      <div className="text-[11px] capitalize leading-snug text-muted">{label(name)}</div>
      <div className="mt-0.5 text-base font-semibold tabular-nums text-ink">
        {typeof value === "number" ? value.toLocaleString() : String(value)}{" "}
        <span className="text-xs font-normal text-muted">{unit}</span>
      </div>
      {!!basis?.length && <div className="mt-0.5 font-mono text-[10px] text-faint">{basis.join(" ")}</div>}
    </div>
  );
}

/** A reported event, investigated by the experts, planned, and decided by Jev. People approve what Jev's
 *  priority leaves to them; a critical event's choices are already approved. */
export default function Incidents() {
  const [rows, setRows] = useState<IncidentRow[]>([]);
  const [open, setOpen] = useState("");
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState("");
  const [summary, setSummary] = useState("");
  const [kind, setKind] = useState("");
  const openRef = useRef(open);
  openRef.current = open;

  const loadList = useCallback(async () => {
    try {
      const out = await api.incidents();
      setRows(out.incidents);
      setOpen((cur) => cur || out.incidents[0]?.id || "");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    if (!id) return;
    try {
      setDetail(await api.incident(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    void loadDetail(open);
  }, [open, loadDetail]);

  // The live trail, and a refresh whenever the pipeline moves.
  useEffect(() => {
    return streamSteps(0, (s) => {
      if (s.stage !== "incident") return;
      setSteps((cur) => [...cur.slice(-400), s]);
      if (["stage", "decision", "done", "error", "write"].includes(s.kind)) {
        void loadList();
        const iid = (s.data as { incident?: string } | null)?.incident;
        if (iid && iid === openRef.current) void loadDetail(iid);
      }
    });
  }, [loadList, loadDetail]);

  // While a run is in flight, poll as a fallback for a dropped stream.
  const running = detail ? RUNNING.has(detail.incident.status) : false;
  useEffect(() => {
    if (!running || !open) return;
    const t = window.setInterval(() => void loadDetail(open), 2500);
    return () => window.clearInterval(t);
  }, [running, open, loadDetail]);

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  };

  const report = () =>
    act("report", async () => {
      const out = await api.reportEvent({ summary: summary.trim(), kind: kind.trim() || "event", source: "ui" });
      setSummary("");
      setKind("");
      await loadList();
      setOpen(out.incident_id);
    });

  const decide = (optionId: string, approve: boolean) =>
    act(optionId, async () => {
      const d = approve ? await api.approveOption(open, optionId) : await api.rejectOption(open, optionId);
      setDetail(d);
      await loadList();
    });

  const incidentSteps = useMemo(
    () => steps.filter((s) => !open || (s.data as { incident?: string } | null)?.incident === open || !s.data),
    [steps, open],
  );

  return (
    <div className="flex h-full flex-col">
    <PageHeader
      crumbs={[{ label: "Incidents" }]}
      title="Incidents"
      subtitle="Events coming in from the supply chain, worked by the expert agents and decided by Jev."
    />
    <div className="grid gap-3 p-4 lg:grid-cols-[340px_1fr]">
      <div className="flex flex-col gap-4">
        <Card title="Report an event">
          <div className="flex flex-col gap-2 text-sm">
            <input
              className="field"
              placeholder="kind, e.g. site_fire, port_closure"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            />
            <textarea
              className="field h-24"
              placeholder="What happened? e.g. Fire reported at the Felixstowe bonded warehouse, unit 4."
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
            />
            <div>
              <Btn kind="primary" disabled={!summary.trim() || busy === "report"} onClick={() => void report()}>
                {busy === "report" ? "sending…" : "Report"}
              </Btn>
            </div>
            <p className="text-xs text-slate-500">
              Feeds post the same body to <span className="font-mono">/api/events/&lt;tenant&gt;</span>.
            </p>
          </div>
        </Card>
        <Card title="Incidents">
          {!rows.length && <div className="text-sm text-slate-500">no incidents yet</div>}
          <ul className="flex flex-col gap-1">
            {rows.map((r) => (
              <li key={r.id}>
                <button
                  onClick={() => setOpen(r.id)}
                  className={`w-full p-2 text-left text-xs border-l ${open === r.id ? "border-ink bg-white/[0.03]" : "border-transparent hover:border-line-strong"}`}
                >
                  <div className="flex flex-wrap items-center gap-1">
                    <Chip color={statusColor(r.status)}>{r.status}</Chip>
                    {r.priority && <Chip color={statusColor(r.priority)}>{r.priority}</Chip>}
                    <span className="text-slate-500">{r.kind}</span>
                  </div>
                  <div className="mt-1 line-clamp-2 text-slate-300">{r.summary}</div>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="flex min-w-0 flex-col gap-4">
        <ErrorLine error={error} />
        {!detail && <div className="text-sm text-slate-500">Select or report an incident.</div>}
        {detail && <IncidentView d={detail} busy={busy} onDecide={decide} onRerun={() => act("rerun", async () => {
          const out = await api.rerunIncident(open);
          await loadList();
          setOpen(out.incident_id);
        })} />}
        <Card title="Agent trail">
          <StepStream steps={incidentSteps} height={300} />
        </Card>
      </div>
    </div>
    </div>
  );
}

function IncidentView({
  d,
  busy,
  onDecide,
  onRerun,
}: {
  d: IncidentDetail;
  busy: string;
  onDecide: (optionId: string, approve: boolean) => void;
  onRerun: () => void;
}) {
  const inc = d.incident;
  const out = inc.outcome;
  return (
    <>
      <Card
        title={inc.id}
        right={
          <div className="flex items-center gap-2">
            <Chip color={statusColor(inc.status)}>{inc.status}</Chip>
            {inc.priority && <Chip color={statusColor(inc.priority)}>{inc.priority}</Chip>}
            {inc.auto && <Chip color="bg-emerald-800">no human needed</Chip>}
            <Btn kind="ghost" disabled={busy === "rerun"} onClick={onRerun}>
              re-run
            </Btn>
          </div>
        }
      >
        <div className="text-sm text-slate-200">{inc.summary}</div>
        <div className="mt-1 text-xs text-slate-500">
          {inc.kind} · {inc.source} · {inc.received_at}
        </div>
        {inc.error && <div className="mt-2"><ErrorLine error={inc.error} /></div>}
        {out && (
          <div className="mt-3 grid gap-1">
            <div className="text-xs text-slate-400">Jev's priority: {out.reason}</div>
            {LEVELS.map((l) => (
              <div key={l} className="grid grid-cols-[70px_1fr_40px] items-center gap-2 text-xs">
                <span className="text-slate-400">{l}</span>
                <Bar p={out.priority_probabilities[l]} tone={l === out.priority ? "bg-violet-500" : "bg-slate-500"} />
                <span className="tabular-nums text-slate-400">{pct(out.priority_probabilities[l])}</span>
              </div>
            ))}
            {!!out.precedents?.length && (
              <div className="text-xs text-slate-500">precedents shown to Jev: {out.precedents.join(", ")}</div>
            )}
          </div>
        )}
      </Card>

      {d.groups.map((g) => (
        <GroupCard key={g.id} g={g} busy={busy} onDecide={onDecide} />
      ))}

      <div className="grid items-start gap-4 2xl:grid-cols-2">
      {inc.analysis && (
        <Card title="Impact analysis">
          <div className="border-l-2 border-l-amber-400 bg-amber-400/[0.06] px-3 py-2 text-sm leading-relaxed text-ink">
            {inc.analysis.impact_summary}
          </div>
          {!!inc.analysis.metrics.length && (
            <>
              <div className="mt-4"><Kicker>Key numbers</Kicker></div>
              <div className="grid gap-2 sm:grid-cols-2">
                {inc.analysis.metrics.map((m) => (
                  <MetricTile key={m.name} name={m.name} value={m.value} unit={m.unit} basis={m.basis_evidence_ids} />
                ))}
              </div>
            </>
          )}
        </Card>
      )}
      {!!d.impact.length && (
        <Card title={`Approved: live impact (${d.impact.length})`}>
          <div className="flex flex-col gap-3">
            {d.impact.map((i) => (
              <div key={i.option_id} className="border border-line bg-sunken/50 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Chip color={statusColor(i.status)}>{i.status}</Chip>
                  {!i.reversible && <Chip color="bg-rose-900">irreversible</Chip>}
                  {i.effective_at && <span className="text-xs text-muted">takes effect {i.effective_at}</span>}
                </div>
                <div className="mt-1.5 font-medium text-ink">{i.title}</div>
                {!!i.metrics.length && (
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    {i.metrics.map((m) => (
                      <MetricTile key={m.name} name={m.name} value={m.value} unit={m.unit} />
                    ))}
                  </div>
                )}
                {!!i.messages.length && (
                  <div className="mt-3">
                    <Kicker>Messages queued</Kicker>
                    <ul className="flex flex-col gap-1">
                      {i.messages.map((m) => (
                        <li key={m.id} className="text-xs text-body">
                          <span className="text-muted">✉ {m.recipient_role}</span> · {m.subject}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {!!i.nodes.length && (
                  <details className="mt-3 text-xs">
                    <summary className="cursor-pointer text-muted hover:text-ink">
                      {i.nodes.length} graph objects affected
                    </summary>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {i.nodes.map((n) => (
                        <Chip key={n.id} title={n.label}>
                          {n.label}:{n.id} {n.title !== n.id ? n.title : ""}
                        </Chip>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
      </div>

      {inc.report && (
        <Card title="Evidence">
          <p className="mb-3 text-sm leading-relaxed text-body">{inc.report.situation}</p>
          <ul className="flex flex-col divide-y divide-line border border-line">
            {inc.report.evidence.map((e) => (
              <li key={e.id} className="grid grid-cols-[44px_1fr] gap-3 px-3 py-2">
                <span className="font-mono text-xs text-sky-300">{e.id}</span>
                <div>
                  <div className="text-sm leading-snug text-ink">{e.claim}</div>
                  <div className="mt-0.5 flex gap-2 text-[11px]">
                    <span className="text-faint">{label(e.from_agent)}</span>
                    <span className={CONF_TONE[e.confidence] ?? "text-muted"}>{e.confidence}</span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {!!inc.relevant?.length && (
        <Card title="Experts (relevance by Jev)">
          <div className="grid gap-1 text-xs">
            {inc.relevant.map((r) => (
              <div key={r.name} className="grid grid-cols-[1fr_120px_40px] items-center gap-2">
                <span className={r.consulted ? "text-slate-200" : "text-slate-500"}>
                  {r.title} {r.consulted ? "· consulted" : ""}
                </span>
                <Bar p={r.p} />
                <span className="tabular-nums text-slate-400">{pct(r.p)}</span>
              </div>
            ))}
          </div>
          {!!inc.exchanges?.length && (
            <details className="mt-3 text-xs">
              <summary className="cursor-pointer text-slate-400">questions and answers ({inc.exchanges.length})</summary>
              <div className="mt-2 flex flex-col gap-2">
                {inc.exchanges.map((x, i) => (
                  <div key={i} className="border-l border-line-strong py-1 pl-3">
                    <div className="text-slate-500">
                      round {x.round} · {x.expert}
                      {!x.ok && " · could not answer"}
                    </div>
                    <div className="text-sky-300">Q: {x.question}</div>
                    <div className="whitespace-pre-wrap text-slate-300">A: {x.answer}</div>
                  </div>
                ))}
              </div>
            </details>
          )}
        </Card>
      )}

      {!!inc.comms?.drafts.length && (
        <Card title="Drafted messages (sent only with their option)">
          <div className="flex flex-col gap-2 text-xs">
            {inc.comms.drafts.map((m) => (
              <details key={m.id} className="border-l border-line-strong py-1 pl-3">
                <summary className="cursor-pointer">
                  <span className="font-mono text-slate-500">{m.id}</span> {m.recipient_role} · {m.channel} ·{" "}
                  <span className="text-slate-200">{m.subject}</span>
                </summary>
                <div className="mt-1 whitespace-pre-wrap text-slate-300">{m.body}</div>
              </details>
            ))}
          </div>
        </Card>
      )}

      {!!d.jev.length && (
        <Card title="Jev calls">
          <div className="flex flex-col gap-1 text-xs">
            {d.jev.map((j) => (
              <details key={j.id}>
                <summary className="cursor-pointer text-slate-400">
                  {j.purpose} · {Object.keys(j.answers).length} questions · {Math.round(j.ms)} ms · {j.model}
                </summary>
                <div className="mt-1 grid gap-1 pl-3">
                  {Object.entries(j.answers).map(([q, a]) => (
                    <div key={q} className="text-slate-400">
                      <span className="font-mono">{q}</span> → <span className="text-slate-200">{a.top}</span>{" "}
                      ({pct(a.probabilities[a.top])})
                    </div>
                  ))}
                </div>
              </details>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}

function GroupCard({
  g,
  busy,
  onDecide,
}: {
  g: IncidentGroup;
  busy: string;
  onDecide: (optionId: string, approve: boolean) => void;
}) {
  const sorted = [...g.options].sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));
  return (
    <Card title={`${g.id} · ${g.mode === "exclusive" ? "pick one" : "each on its own"}`}>
      <div className="mb-3 text-base font-medium text-ink">{g.question}</div>
      <div className="flex flex-col gap-2">
        {sorted.map((o) => (
          <OptionRow key={o.id} o={o} mode={g.mode} busy={busy === o.id} onDecide={onDecide} />
        ))}
      </div>
    </Card>
  );
}

function OptionRow({
  o,
  mode,
  busy,
  onDecide,
}: {
  o: IncidentOption;
  mode: string;
  busy: boolean;
  onDecide: (optionId: string, approve: boolean) => void;
}) {
  const approved = o.status === "approved" || o.status === "auto_approved";
  const theme = OPTION_THEME[o.status ?? "pending"] ?? DEFAULT_THEME;
  return (
    <div className={`border border-line p-4 transition-colors ${theme.card}`}>
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`px-2 py-0.5 text-xs font-bold ${theme.badge}`}>{theme.label}</span>
            {o.is_wait && <Chip>wait</Chip>}
            {o.alternative_to && <span className="text-xs text-muted">fallback for {o.alternative_to}</span>}
          </div>
          <div className="mt-1.5 text-base font-semibold leading-snug text-ink">{o.title}</div>
        </div>
        <div className="flex shrink-0 gap-2">
          {!approved && (
            <button
              disabled={busy}
              onClick={() => onDecide(o.id, true)}
              className="h-10 min-w-[104px] bg-emerald-500 px-5 text-sm font-bold text-black transition-colors hover:bg-emerald-400 disabled:opacity-40"
            >
              ✓ Approve
            </button>
          )}
          {o.status !== "rejected" && (
            <button
              disabled={busy}
              onClick={() => onDecide(o.id, false)}
              className={`h-10 min-w-[96px] border-2 px-5 text-sm font-bold transition-colors disabled:opacity-40 ${
                approved
                  ? "border-white/30 text-body hover:border-white/60 hover:text-ink"
                  : "border-rose-400 text-rose-300 hover:bg-rose-400/15"
              }`}
            >
              {approved ? "Undo" : "✕ Reject"}
            </button>
          )}
        </div>
      </div>
      <div className="mt-3 grid gap-4 text-sm leading-relaxed text-ink md:grid-cols-3">
        <div>
          <Kicker>Reversibility</Kicker>
          <span className="font-medium">{o.reversible ? "Reversible" : <span className="text-rose-300">Irreversible</span>}</span>
          {o.time_to_effect_hours != null && <span className="text-muted"> · effect in ~{o.time_to_effect_hours}h</span>}
        </div>
        {o.cost_estimate && (
          <div>
            <Kicker>Cost</Kicker>
            {o.cost_estimate}
          </div>
        )}
        {o.risk && (
          <div>
            <Kicker>Risk</Kicker>
            {o.risk}
          </div>
        )}
      </div>
      {!!o.steps.length && (
        <div className="mt-3">
          <Kicker>Steps</Kicker>
          <ol className="list-decimal space-y-1 pl-5 text-sm leading-relaxed text-body marker:text-faint">
            {o.steps.map((st, i) => (
              <li key={i}>{st}</li>
            ))}
          </ol>
        </div>
      )}
      <div className="mt-4 border-t border-line pt-2 text-[11px] text-faint">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span
            title={mode === "exclusive" ? "P(Jev's choice)" : "P(do it now)"}
            className="inline-flex items-center gap-2 rounded-sm bg-violet-400/10 px-2 py-0.5 text-violet-300"
          >
            Jev's confidence
            <span className="h-1 w-12 bg-violet-400/20">
              <span className="block h-full bg-violet-400" style={{ width: `${Math.round((o.probability ?? 0) * 100)}%` }} />
            </span>
            <span className="text-xs font-semibold tabular-nums">{pct(o.probability)}</span>
          </span>
          <span>type: {o.action_kind}</span>
          <span className="flex items-center gap-1">
            evidence:
            {o.evidence_ids.length ? o.evidence_ids.map((id) => <span key={id} className="font-mono text-muted">{id}</span>) : "-"}
          </span>
        </div>
        {o.reason && <div className="mt-1">{o.reason}</div>}
      </div>
    </div>
  );
}
