import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { AskResult, Hotspot, Overview } from "../api";
import { Icon } from "../components/icons";
import { Btn, Callout, Caption, EmptyState, PageHeader, Stat, Tag, TypeTag, statusIntent } from "../components/ui";
import { human, plural } from "../ontologyText";
import { useOntology } from "../useOntology";

/** The live company at a glance: what is in the graph, where it is exposed, what needs a decision, and the
 *  experts to ask. The default page once there is an approved ontology; before that, onboarding is. */
export default function Home() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [noTenant, setNoTenant] = useState(false);
  const nav = useNavigate();

  useEffect(() => {
    api.overview().then(setOv).catch((e) => {
      if (e instanceof ApiError && (e.status === 404 || e.status === 400)) setNoTenant(true);
      else setError(e instanceof Error ? e.message : String(e));
    });
  }, []);

  if (noTenant) return <Navigate to="/onboarding" replace />;
  if (error) return <div className="p-6"><Callout intent="danger" title="Could not load the overview">{error}</Callout></div>;
  if (!ov) return <div className="micro p-6 text-faint">Loading<span className="blink">_</span></div>;
  if (!ov.has_ontology) return <Navigate to="/onboarding" replace />;

  const nodes = Object.values(ov.counts.nodes).reduce((a, b) => a + b, 0);
  const edges = Object.values(ov.counts.edges).reduce((a, b) => a + b, 0);
  const live = ov.stage === "ready";
  const openIncidents = ov.incidents.total - (ov.incidents.by_status.resolved ?? 0);
  const approved = ov.experts.filter((e) => e.status === "approved");

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        crumbs={[{ label: "Overview" }]}
        title={ov.tenant.name ?? ov.tenant.id}
        subtitle={<span className="flex flex-wrap items-center gap-x-4 gap-y-1">
          {ov.tenant.industry && <span>{ov.tenant.industry}</span>}
          <span>Ontology v{ov.version}</span>
          {live ? <Tag intent="success">Live</Tag> : <Tag intent="warning">Onboarding · {ov.stage}</Tag>}
          {ov.tenant.seeded_from === "mock" && <Tag intent="info">Mock data</Tag>}
          {ov.tenant.has_synthetic && ov.tenant.seeded_from !== "mock" &&
            <Tag intent="info" title="Some answers were synthesized or autofilled">Synthetic data</Tag>}
        </span>}
        right={<>
          <Btn onClick={() => nav("/ontology")}>Ontology</Btn>
          <Btn onClick={() => nav("/objects")}>Explore objects</Btn>
        </>}
      >
        {!live && (
          <div className="mt-4">
            <Callout intent="primary" title={`Onboarding is at the ${ov.stage} stage`}>
              The graph below is from the last approved ontology. <Link to="/onboarding" className="link">Continue onboarding</Link>
              {ov.busy && " - an agent is working right now."}
            </Callout>
          </div>
        )}
      </PageHeader>

      <div className="flex flex-col gap-10 px-6 pb-12 pt-6">
        <div className="grid grid-cols-2 gap-y-6 md:grid-cols-3 xl:grid-cols-6">
          <Stat label="Objects" value={nodes.toLocaleString()} sub={`${ov.types} object types`} />
          <Stat label="Links" value={edges.toLocaleString()} sub={`${ov.relationships} link types`} />
          <Stat label="Hot spots" value={ov.hotspots.length} tone={ov.hotspots.length ? "text-amber-300" : undefined} sub="read off the graph" />
          <Stat label="Open incidents" value={openIncidents} sub={`${ov.incidents.total} in total`} />
          <Stat label="Needs you" value={ov.incidents.needs_you} tone={ov.incidents.needs_you ? "text-rose-300" : undefined} sub="awaiting approval" />
          <Stat label="Expert agents" value={approved.length} sub={`${ov.experts.length} roles`} />
        </div>

        <Composition counts={ov.counts.nodes} />

        <div className="grid gap-10 xl:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
          <Section title="Hot spots" count={ov.hotspots.length} right={<span className="text-[11.5px] text-faint">Read off the approved ontology</span>}>
            {ov.hotspots.length === 0 ? (
              <EmptyState icon="check" title="No hot spots found">
                No object is in a risky state, and nothing depends on a single partner over a many-to-many link.
              </EmptyState>
            ) : (
              <ol className="divide-y divide-line">
                {ov.hotspots.map((h, i) => <HotspotRow key={i} h={h} />)}
              </ol>
            )}
          </Section>

          <Section title="Incidents" count={ov.incidents.total} right={<Link to="/incidents" className="text-[12px] text-muted hover:text-ink">Open →</Link>}>
            {ov.incidents.needs_you > 0 && (
              <div className="border-b border-line py-3">
                <Callout intent="danger" title={`${ov.incidents.needs_you} decision${ov.incidents.needs_you === 1 ? "" : "s"} waiting for you`}>
                  <Link to="/incidents" className="link">Review and approve</Link>
                </Callout>
              </div>
            )}
            {ov.incidents.recent.length === 0 ? (
              <EmptyState icon="incident" title="No incidents">Events reported to Ripple show up here.</EmptyState>
            ) : (
              <ul className="divide-y divide-line">
                {ov.incidents.recent.map((inc) => (
                  <li key={inc.id}>
                    <Link to="/incidents" className="group flex flex-col gap-1.5 py-3">
                      <span className="flex items-center gap-3">
                        <Tag intent={statusIntent(inc.status)}>{inc.status.replace(/_/g, " ")}</Tag>
                        {inc.priority && <Tag intent={statusIntent(inc.priority)}>{inc.priority}</Tag>}
                        <span className="ml-auto font-mono text-[10.5px] text-faint">{inc.kind}</span>
                      </span>
                      <span className="text-[13px] leading-snug text-body group-hover:text-ink">{inc.summary}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>

        <AskExperts experts={approved} />
      </div>
    </div>
  );
}

/** A titled block that sits on a hairline rather than in a box. */
function Section({ title, count, right, children }: { title: ReactNode; count?: number; right?: ReactNode; children: ReactNode }) {
  return (
    <section className="rise min-w-0">
      <Caption title={title} count={count} right={right} className="border-b border-line-strong" />
      {children}
    </section>
  );
}

/** What the graph holds, as one proportional bar with a legend beneath. */
function Composition({ counts }: { counts: Record<string, number> }) {
  const { style } = useOntology();
  const rows = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const total = rows.reduce((a, [, n]) => a + n, 0) || 1;
  return (
    <Section title="Objects by type" count={rows.length}>
      <div className="mt-4 flex h-[6px] w-full gap-px">
        {rows.map(([label, n]) => (
          <Link key={label} to={`/objects/${encodeURIComponent(label)}`} title={`${human(label)}: ${n}`}
                className="h-full transition-opacity hover:opacity-70" style={{ flexGrow: n, background: style(label).color }} />
        ))}
      </div>
      <ul className="mt-4 flex flex-wrap gap-x-7 gap-y-2">
        {rows.map(([label, n]) => (
          <li key={label}>
            <Link to={`/objects/${encodeURIComponent(label)}`} className="group flex items-baseline gap-2 text-[12.5px]">
              <span className="h-2 w-2 shrink-0 translate-y-[-1px]" style={{ background: style(label).color }} />
              <span className="text-muted group-hover:text-ink">{human(label)}</span>
              <span className="tabular-nums text-ink">{n.toLocaleString()}</span>
              <span className="font-mono text-[10.5px] tabular-nums text-faint">{Math.round((n / total) * 100)}%</span>
            </Link>
          </li>
        ))}
      </ul>
    </Section>
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
    <li className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-4 py-4">
      <div>
        <div className={`text-[26px] font-light leading-none tabular-nums ${severe ? "text-rose-300" : "text-amber-300"}`}>
          {Math.round(ratio * 100)}<span className="text-[14px] text-faint">%</span>
        </div>
        <div className="mt-1.5 font-mono text-[10.5px] tabular-nums text-faint">{n} / {h.total}</div>
      </div>
      <div className="min-w-0">
        <div className="text-[13.5px] text-ink">
          {h.kind === "status" ? (
            <>{plural(label)} with {human(h.property!).replace(/_/g, " ")} <span className="text-amber-200">{h.value}</span></>
          ) : (
            <>{plural(label)} linked to only one {human(h.from!)}</>
          )}
        </div>
        <div className="mt-1 text-[12px] leading-relaxed text-muted">
          {h.kind === "status"
            ? (h.description || `Objects whose ${h.property} is ${h.value}.`)
            : `${h.rel} is many-to-many, yet each of these has a single ${human(h.from!)} on it. If that link is a source of supply, there is no alternate.`}
        </div>
        <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px]">
          {h.sample.map((o) => (
            <Link key={o.id} to={`/objects/${encodeURIComponent(label)}/${encodeURIComponent(o.id)}`}
                  className="inline-flex items-baseline gap-1.5 text-body hover:text-ink">
              <span className="h-1.5 w-1.5 shrink-0" style={{ background: s.color }} />
              {o.title}
              <span className="font-mono text-[10px] text-faint">{o.id}</span>
            </Link>
          ))}
          {n > h.sample.length && (
            <Link to={`/objects/${encodeURIComponent(label)}`} className="link">+{n - h.sample.length} more</Link>
          )}
          <span className="ml-auto font-mono text-[10.5px] text-faint">
            {h.kind === "status" ? `${h.label}.${h.property}` : `${h.from} ${h.rel} ${h.to}`}
          </span>
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

  const manage = <Link to="/experts" className="text-[12px] text-muted hover:text-ink">Manage roles →</Link>;
  if (!experts.length) {
    return (
      <Section title="Ask an expert" right={manage}>
        <EmptyState icon="experts" title="No approved expert roles" />
      </Section>
    );
  }

  return (
    <Section title="Ask an expert" count={experts.length} right={manage}>
      <div className="grid lg:grid-cols-[280px_minmax(0,1fr)]">
        <ul className="border-b border-line py-2 lg:border-b-0 lg:border-r">
          {experts.map((e) => (
            <li key={e.id}>
              <button onClick={() => { setSel(e.id); setAnswer(null); setError(null); }}
                      className={`flex w-full flex-col border-l py-2 pl-3 pr-4 text-left transition-colors ${sel === e.id ? "border-ink" : "border-transparent hover:border-line-strong"}`}>
                <span className={`truncate text-[13px] ${sel === e.id ? "text-ink" : "text-body"}`}>{e.title}</span>
                <span className="line-clamp-2 text-[11.5px] text-faint">{e.mandate}</span>
              </button>
            </li>
          ))}
        </ul>
        {role && (
          <div className="flex min-w-0 flex-col gap-4 py-4 lg:pl-6">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="eyebrow">Reasons over</span>
              {role.focus_types.map((t) => <TypeTag key={t} label={t} color={style(t).color} icon={style(t).icon} />)}
            </div>
            <div className="flex gap-2">
              <input className="field h-9 flex-1 px-3 text-[13px]" value={q} onChange={(e) => setQ(e.target.value)}
                     onKeyDown={(e) => e.key === "Enter" && void ask()}
                     placeholder={`Ask the ${role.title}…`} disabled={busy} />
              <Btn kind="primary" onClick={() => void ask()} disabled={busy || !q.trim()}>
                {busy ? "Thinking…" : "Ask"}
              </Btn>
            </div>
            {role.playbook.length > 0 && !answer && !busy && (
              <ul className="flex flex-col">
                {role.playbook.map((p) => (
                  <li key={p}>
                    <button onClick={() => { setQ(p); void ask(p); }}
                            className="group flex w-full items-baseline gap-2 py-1 text-left text-[12.5px] text-muted hover:text-ink">
                      <Icon name="arrowRight" size={11} className="shrink-0 text-faint group-hover:text-ink" />
                      {p}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {busy && (
              <div className="micro text-muted">
                The {role.title} is querying the graph<span className="blink">_</span>
              </div>
            )}
            {error && <Callout intent="danger" title="The expert could not answer">{error}</Callout>}
            {answer && (
              <div className="border-l border-ink pl-4">
                <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-body">{answer.text || answer.reason}</p>
                <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-faint">
                  <span>{answer.turns} turns · {answer.steps.filter((s) => s.kind === "tool_call").length} graph queries</span>
                  {answer.ids.slice(0, 8).map((id) => <Tag key={id} mono>{id}</Tag>)}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Section>
  );
}
