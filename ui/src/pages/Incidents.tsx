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
    <div className="h-1.5 w-full rounded bg-slate-800">
      <div className={`h-1.5 rounded ${tone}`} style={{ width: `${Math.round((p ?? 0) * 100)}%` }} />
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
      icon={<span className="flex h-9 w-9 items-center justify-center rounded-[4px] bg-danger-soft text-rose-300"><Icon name="incident" size={20} /></span>}
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
                  className={`w-full rounded p-2 text-left text-xs ${open === r.id ? "bg-slate-800" : "hover:bg-slate-800/60"}`}
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
        {inc.error && <div className="mt-2 rounded bg-rose-950 p-2 text-xs text-rose-200">{inc.error}</div>}
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

      {!!d.impact.length && (
        <Card title="Approved: live impact">
          <div className="flex flex-col gap-3">
            {d.impact.map((i) => (
              <div key={i.option_id} className="rounded bg-slate-950/60 p-2 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <Chip color={statusColor(i.status)}>{i.status}</Chip>
                  <span className="font-medium text-slate-200">{i.title}</span>
                  {i.effective_at && <span className="text-slate-500">takes effect {i.effective_at}</span>}
                  {!i.reversible && <Chip color="bg-rose-900">irreversible</Chip>}
                </div>
                {!!i.nodes.length && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {i.nodes.map((n) => (
                      <Chip key={n.id} title={n.label}>
                        {n.label}:{n.id} {n.title !== n.id ? n.title : ""}
                      </Chip>
                    ))}
                  </div>
                )}
                {i.metrics.map((m) => (
                  <div key={m.name} className="text-slate-400">
                    {m.name}: <span className="text-slate-200">{String(m.value)} {m.unit}</span>
                  </div>
                ))}
                {i.messages.map((m) => (
                  <div key={m.id} className="mt-1 text-slate-400">
                    ✉ {m.recipient_role}: <span className="text-slate-300">{m.subject}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Card>
      )}

      {inc.analysis && (
        <Card title="Impact analysis">
          <p className="text-sm text-slate-300">{inc.analysis.impact_summary}</p>
          <div className="mt-2 grid gap-1 text-xs sm:grid-cols-2">
            {inc.analysis.metrics.map((m) => (
              <div key={m.name} className="text-slate-400">
                {m.name}: <span className="text-slate-200">{String(m.value)} {m.unit}</span>{" "}
                <span className="text-slate-600">({m.basis_evidence_ids.join(", ")})</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {inc.report && (
        <Card title="Evidence">
          <p className="mb-2 text-sm text-slate-300">{inc.report.situation}</p>
          <ul className="flex flex-col gap-1 text-xs">
            {inc.report.evidence.map((e) => (
              <li key={e.id}>
                <span className="font-mono text-slate-500">{e.id}</span>{" "}
                <span className="text-slate-200">{e.claim}</span>{" "}
                <span className="text-slate-500">
                  ({e.from_agent}, {e.confidence})
                </span>
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
                  <div key={i} className="rounded bg-slate-950/60 p-2">
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
              <details key={m.id} className="rounded bg-slate-950/60 p-2">
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
      <div className="mb-2 text-sm text-slate-200">{g.question}</div>
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
  return (
    <div className="rounded bg-slate-950/60 p-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        {o.status && <Chip color={statusColor(o.status)}>{o.status}</Chip>}
        <span className="font-medium text-slate-200">{o.title}</span>
        <span className="text-slate-500">{o.action_kind}</span>
        {o.is_wait && <Chip>wait</Chip>}
        {o.alternative_to && <span className="text-slate-500">fallback for {o.alternative_to}</span>}
        <div className="ml-auto flex gap-1">
          {!approved && (
            <Btn kind="primary" disabled={busy} onClick={() => onDecide(o.id, true)}>
              approve
            </Btn>
          )}
          {o.status !== "rejected" && (
            <Btn kind="ghost" disabled={busy} onClick={() => onDecide(o.id, false)}>
              {approved ? "undo" : "reject"}
            </Btn>
          )}
        </div>
      </div>
      <div className="mt-1 grid grid-cols-[1fr_44px] items-center gap-2">
        <Bar p={o.probability} tone={approved ? "bg-emerald-500" : "bg-sky-500"} />
        <span className="tabular-nums text-slate-400" title={mode === "exclusive" ? "P(Jev's choice)" : "P(do it now)"}>
          {pct(o.probability)}
        </span>
      </div>
      <div className="mt-1 text-slate-400">
        {o.reversible ? "reversible" : "irreversible"}
        {o.time_to_effect_hours != null && ` · effect in ~${o.time_to_effect_hours}h`}
        {o.cost_estimate && ` · cost: ${o.cost_estimate}`}
        {o.risk && ` · risk: ${o.risk}`}
      </div>
      {!!o.steps.length && <div className="text-slate-500">steps: {o.steps.join("; ")}</div>}
      <div className="text-slate-600">
        rests on {o.evidence_ids.join(", ") || "-"}
        {o.reason && ` · ${o.reason}`}
      </div>
    </div>
  );
}
