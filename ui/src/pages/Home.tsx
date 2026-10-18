import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { AskResult, Hotspot, Overview } from "../api";
import { Icon } from "../components/icons";
import {
  Btn, Callout, EmptyState, Meter, PageHeader, Panel, Stat, Tag, TypeIcon, TypeTag, statusIntent,
} from "../components/ui";
import { human, plural } from "../ontologyText";
import { useOntology } from "../useOntology";

/** The live company at a glance: what is in the graph, where it is exposed, what needs a decision, and the
 *  experts to ask. The default page once there is an approved ontology; before that, onboarding is. */
export default function Home() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [noTenant, setNoTenant] = useState(false);
  const { style } = useOntology();
  const nav = useNavigate();

  useEffect(() => {
    api.overview().then(setOv).catch((e) => {
      if (e instanceof ApiError && (e.status === 404 || e.status === 400)) setNoTenant(true);
      else setError(e instanceof Error ? e.message : String(e));
    });
  }, []);

  if (noTenant) return <Navigate to="/onboarding" replace />;
  if (error) return <div className="p-6"><Callout intent="danger" title="Could not load the overview">{error}</Callout></div>;
  if (!ov) return <div className="p-6 text-[12px] text-faint">Loading the overview…</div>;
  if (!ov.has_ontology) return <Navigate to="/onboarding" replace />;

  const nodes = Object.values(ov.counts.nodes).reduce((a, b) => a + b, 0);
  const edges = Object.values(ov.counts.edges).reduce((a, b) => a + b, 0);
  const live = ov.stage === "ready";
  const typeCounts = Object.entries(ov.counts.nodes).sort((a, b) => b[1] - a[1]);
  const openIncidents = ov.incidents.total - (ov.incidents.by_status.resolved ?? 0);

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        crumbs={[{ label: "Overview" }]}
        icon={<span className="flex h-10 w-10 items-center justify-center rounded-[4px] bg-accent-soft text-accent"><Icon name="building" size={22} /></span>}
        title={ov.tenant.name ?? ov.tenant.id}
        subtitle={<span className="flex flex-wrap items-center gap-x-3">
          {ov.tenant.industry && <span>{ov.tenant.industry}</span>}
          <span>Supply chain knowledge graph · ontology v{ov.version}</span>
        </span>}
        right={<>
          {live ? <Tag intent="success" icon="check">Live</Tag> : <Tag intent="warning">Onboarding: {ov.stage}</Tag>}
          {ov.tenant.seeded_from === "mock" && <Tag intent="info">Mock data</Tag>}
          {ov.tenant.has_synthetic && ov.tenant.seeded_from !== "mock" && <Tag intent="info" title="Some answers were synthesized or autofilled">Contains synthetic data</Tag>}
          <Btn icon="schema" onClick={() => nav("/ontology")}>Ontology</Btn>
          <Btn icon="table" onClick={() => nav("/objects")}>Explore objects</Btn>
        </>}
      >
        {!live && (
          <div className="mt-3">
            <Callout intent="primary" title={`Onboarding is at the ${ov.stage} stage`}>
              The graph below is from the last approved ontology. <Link to="/onboarding" className="link">Continue onboarding</Link>
              {ov.busy && " - an agent is working right now."}
            </Callout>
          </div>
        )}
      </PageHeader>

      <div className="flex flex-col gap-3 p-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Stat label="Objects" value={nodes.toLocaleString()} sub={`${ov.types} object types`} />
          <Stat label="Links" value={edges.toLocaleString()} sub={`${ov.relationships} link types`} />
          <Stat label="Hot spots" value={ov.hotspots.length} tone={ov.hotspots.length ? "text-amber-300" : "text-ink"} sub="from the graph" />
          <Stat label="Open incidents" value={openIncidents} sub={`${ov.incidents.total} in total`} />
          <Stat label="Needs you" value={ov.incidents.needs_you} tone={ov.incidents.needs_you ? "text-rose-300" : "text-ink"} sub="awaiting approval" />
          <Stat label="Expert agents" value={ov.experts.filter((e) => e.status === "approved").length} sub={`${ov.experts.length} roles`} />
        </div>

        <div className="flex flex-wrap gap-2">
          {typeCounts.map(([label, n]) => {
            const s = style(label);
            return (
              <Link key={label} to={`/objects/${encodeURIComponent(label)}`}
                    className="flex items-center gap-2 rounded-[4px] border border-line bg-panel py-1.5 pl-1.5 pr-3 hover:border-line-strong hover:bg-raised">
                <TypeIcon label={label} color={s.color} icon={s.icon} size={24} />
                <span className="text-[12px] text-muted">{human(label)}</span>
                <span className="text-[13px] font-semibold tabular-nums text-ink">{n.toLocaleString()}</span>
              </Link>
            );
          })}
        </div>

        <div className="grid gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
          <Panel title="Hot spots" icon="alert" count={ov.hotspots.length}
                 right={<span className="text-[11px] text-faint">read off the approved ontology</span>}>
            {ov.hotspots.length === 0 ? (
              <EmptyState icon="check" title="No hot spots found">
                No object is in a risky state, and nothing depends on a single partner over a many-to-many link.
              </EmptyState>
            ) : (
              <ul className="divide-y divide-line">
                {ov.hotspots.map((h, i) => <HotspotRow key={i} h={h} />)}
              </ul>
            )}
          </Panel>

          <Panel title="Incidents" icon="incident" count={ov.incidents.total}
                 right={<Btn small kind="ghost" onClick={() => nav("/incidents")}>Open</Btn>}>
            <div className="flex flex-col gap-2 p-3">
              {ov.incidents.needs_you > 0 && (
                <Callout intent="danger" title={`${ov.incidents.needs_you} decision${ov.incidents.needs_you === 1 ? "" : "s"} waiting for you`}>
                  <Link to="/incidents" className="link">Review and approve</Link>
                </Callout>
              )}
              {ov.incidents.recent.length === 0 ? (
                <EmptyState icon="incident" title="No incidents">Events reported to Ripple show up here.</EmptyState>
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {ov.incidents.recent.map((inc) => (
                    <li key={inc.id}>
                      <Link to="/incidents" className="flex flex-col gap-1 rounded-[3px] border border-line bg-sunken px-2.5 py-2 hover:border-line-strong">
                        <span className="flex items-center gap-1.5">
                          <Tag intent={statusIntent(inc.status)}>{inc.status.replace(/_/g, " ")}</Tag>
                          {inc.priority && <Tag intent={statusIntent(inc.priority)}>{inc.priority}</Tag>}
                          <span className="ml-auto font-mono text-[10.5px] text-faint">{inc.kind}</span>
                        </span>
                        <span className="text-[12.5px] leading-snug text-ink">{inc.summary}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Panel>
        </div>

        <AskExperts experts={ov.experts.filter((e) => e.status === "approved")} />
      </div>
    </div>
  );
}

function HotspotRow({ h }: { h: Hotspot }) {
  const { style } = useOntology();
  const label = h.kind === "status" ? h.label! : h.to!;
  const s = style(label);
  const n = h.kind === "status" ? h.count! : h.single!;
  const ratio = n / Math.max(h.total, 1);
  const severe = ratio >= 0.25;
  return (
    <li className="flex gap-3 px-4 py-3">
      <TypeIcon label={label} color={s.color} icon={s.icon} size={30} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] font-medium text-ink">
            {h.kind === "status" ? (
              <>{n} of {h.total} {plural(label)} have {human(h.property!).replace(/_/g, " ")} <b className="text-amber-200">{h.value}</b></>
            ) : (
              <>{n} of {h.total} {plural(label)} are linked to only one {human(h.from!)}</>
            )}
          </span>
          <Tag intent={severe ? "danger" : "warning"}>{Math.round(ratio * 100)}%</Tag>
          <span className="ml-auto font-mono text-[10.5px] text-faint">
            {h.kind === "status" ? `${h.label}.${h.property}` : `${h.from} ${h.rel} ${h.to}`}
          </span>
        </div>
        <div className="mt-0.5 text-[11.5px] text-muted">
          {h.kind === "status"
            ? (h.description || `Objects whose ${h.property} is ${h.value}.`)
            : `${h.rel} is many-to-many, yet each of these has a single ${human(h.from!)} on it. If that link is a source of supply, there is no alternate.`}
        </div>
        <Meter value={ratio} tone={severe ? "bg-rose-500" : "bg-amber-500"} className="mt-2 max-w-md" />
        <div className="mt-2 flex flex-wrap gap-1.5">
          {h.sample.map((o) => (
            <Link key={o.id} to={`/objects/${encodeURIComponent(label)}/${encodeURIComponent(o.id)}`}
                  className="inline-flex items-center gap-1.5 rounded-[3px] border border-line-strong bg-raised px-1.5 py-0.5 text-[11.5px] text-ink hover:border-slate-500">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.color }} />
              {o.title}
              <span className="font-mono text-[10px] text-faint">{o.id}</span>
            </Link>
          ))}
          {n > h.sample.length && (
            <Link to={`/objects/${encodeURIComponent(label)}`} className="link self-center text-[11.5px]">+{n - h.sample.length} more</Link>
          )}
        </div>
      </div>
    </li>
  );
}

function AskExperts({ experts }: { experts: Overview["experts"] }) {
  const { style } = useOntology();
  const [sel, setSel] = useState(experts[0]?.id ?? "");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<AskResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const role = experts.find((e) => e.id === sel);

  const ask = async (question = q) => {
    if (!role || !question.trim()) return;
    setBusy(true);
    setError(null);
    setAnswer(null);
    try {
      setAnswer(await api.askExpert(role.id, question.trim()));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!experts.length) {
    return (
      <Panel title="Ask an expert" icon="experts">
        <EmptyState icon="experts" title="No approved expert roles" action={<Link to="/experts" className="link text-[12px]">Review the roles</Link>} />
      </Panel>
    );
  }

  return (
    <Panel title="Ask an expert" icon="experts" count={experts.length}
           right={<Link to="/experts" className="link text-[11.5px]">Manage roles</Link>}>
      <div className="grid gap-0 lg:grid-cols-[300px_minmax(0,1fr)]">
        <ul className="border-b border-line p-1.5 lg:border-b-0 lg:border-r">
          {experts.map((e) => (
            <li key={e.id}>
              <button onClick={() => { setSel(e.id); setAnswer(null); setError(null); }}
                      className={`flex w-full items-start gap-2 rounded-[3px] px-2 py-2 text-left hover:bg-hover ${sel === e.id ? "bg-accent-soft shadow-[inset_2px_0_0] shadow-accent" : ""}`}>
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-900/60 text-violet-300"><Icon name="experts" size={12} /></span>
                <span className="min-w-0">
                  <span className="block truncate text-[12.5px] font-medium text-ink">{e.title}</span>
                  <span className="line-clamp-2 text-[11px] text-faint">{e.mandate}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
        {role && (
          <div className="flex min-w-0 flex-col gap-2.5 p-3">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-faint">Reasons over</span>
              {role.focus_types.map((t) => <TypeTag key={t} label={t} color={style(t).color} icon={style(t).icon} />)}
            </div>
            <div className="flex gap-2">
              <input className="field h-8 flex-1 text-[13px]" value={q} onChange={(e) => setQ(e.target.value)}
                     onKeyDown={(e) => e.key === "Enter" && void ask()}
                     placeholder={`Ask the ${role.title}…`} disabled={busy} />
              <Btn kind="primary" icon="arrowRight" onClick={() => void ask()} disabled={busy || !q.trim()}>
                {busy ? "Thinking…" : "Ask"}
              </Btn>
            </div>
            {role.playbook.length > 0 && !answer && !busy && (
              <div className="flex flex-wrap gap-1.5">
                {role.playbook.map((p) => (
                  <button key={p} onClick={() => { setQ(p); void ask(p); }}
                          className="rounded-full border border-line-strong bg-raised px-2.5 py-1 text-left text-[11.5px] text-body hover:border-accent hover:text-ink">
                    {p.length > 90 ? `${p.slice(0, 89)}…` : p}
                  </button>
                ))}
              </div>
            )}
            {busy && (
              <div className="flex items-center gap-2 text-[12px] text-violet-200">
                <span className="h-2 w-2 animate-pulse rounded-full bg-violet-400" />
                The {role.title} is querying the graph…
              </div>
            )}
            {error && <Callout intent="danger" title="The expert could not answer">{error}</Callout>}
            {answer && (
              <div className="rounded-[4px] border border-line bg-sunken p-3">
                <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-body">{answer.text || answer.reason}</p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-line pt-2 text-[10.5px] text-faint">
                  <span>{answer.turns} turns · {answer.steps.filter((s) => s.kind === "tool_call").length} graph queries</span>
                  {answer.ids.slice(0, 8).map((id) => <Tag key={id} mono>{id}</Tag>)}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Panel>
  );
}
