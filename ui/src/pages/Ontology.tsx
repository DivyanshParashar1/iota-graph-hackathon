import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { RelationshipSpec } from "../api";
import GraphView from "../components/GraphView";
import type { ViewLink, ViewNode } from "../components/GraphView";
import { Icon } from "../components/icons";
import { LinkChip, LinkInspector, SentenceView, TypeInspector, relKey } from "../components/OntologyBits";
import { Btn, Callout, EmptyState, PageHeader, Panel, SearchInput, TableShell, Tabs, Tag, Td, Th, TypeIcon } from "../components/ui";
import { CARD_LABEL, CARD_SHORT, human, story } from "../ontologyText";
import { setOntologyCache, useOntology } from "../useOntology";

type Tab = "graph" | "read" | "types" | "links" | "rationale" | "history";
type Sel = { kind: "type"; id: string } | { kind: "link"; id: string } | null;

/** The ontology workspace: the schema as a graph, as prose and as tables, with the approve gate on top. */
export default function Ontology() {
  const { view, spec, error, loading, style, reload } = useOntology();
  const [tab, setTab] = useState<Tab>("graph");
  const [sel, setSel] = useState<Sel>(null);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionErrors, setActionErrors] = useState<string[]>([]);
  const [stage, setStage] = useState<string>("");
  useEffect(() => {
    api.session().then((st) => setStage(st.stage)).catch(() => setStage(""));
  }, [view]);
  const tooEarly = stage === "interview" || stage === "data";
  const nav = useNavigate();

  const counts = view?.counts ?? { nodes: {}, edges: {} };
  const totalNodes = Object.values(counts.nodes).reduce((a, b) => a + b, 0);
  const totalEdges = Object.values(counts.edges).reduce((a, b) => a + b, 0);

  const nodes = useMemo<ViewNode[]>(() => (spec?.types ?? []).map((t) => {
    const n = counts.nodes[t.label] ?? 0;
    const s = style(t.label);
    return { id: t.label, label: t.label, title: human(t.label), color: s.color, icon: s.icon,
             size: 1.25 + Math.min(1, Math.log10(n + 1) / 3), sub: `${n.toLocaleString()} objects` };
  }), [spec, counts.nodes, style]);
  const links = useMemo<ViewLink[]>(() => (spec?.relationships ?? []).map((r) => ({
    source: r.from, target: r.to, type: r.type, badge: CARD_SHORT[r.cardinality], key: relKey(r),
  })), [spec]);

  const approve = async () => {
    setBusy("approve");
    setActionError(null);
    setActionErrors([]);
    try {
      await api.approveOntology();
      const v = await api.ontology();
      setOntologyCache(v);
      nav("/experts");
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
      if (e instanceof ApiError) setActionErrors(e.errors);
    } finally {
      setBusy("");
    }
  };

  if (!view) {
    return <div className="p-6 text-[12px] text-faint">{error ?? (loading ? "Loading the ontology…" : "")}</div>;
  }
  if (!spec) {
    return (
      <div className="p-6">
        <EmptyState icon="schema" title="No ontology yet"
                    action={<Link to="/onboarding" className="link text-[12px]">Go to onboarding</Link>}>
          The ontology agent designs the model once the data stage is done.
        </EmptyState>
      </div>
    );
  }

  const q = filter.trim().toLowerCase();
  const types = spec.types.filter((t) => !q || t.label.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)
    || t.tags.some((g) => g.toLowerCase().includes(q)));
  const rels = spec.relationships.filter((r) => !q || [r.type, r.from, r.to].some((x) => x.toLowerCase().includes(q)));
  const selType = sel?.kind === "type" ? spec.types.find((t) => t.label === sel.id) : undefined;
  const selRel = sel?.kind === "link" ? spec.relationships.find((r) => relKey(r) === sel.id) : undefined;
  const highlight = q ? new Set(types.map((t) => t.label)) : undefined;
  const approved = view.row.status === "approved";
  const openType = (label: string) => nav(`/ontology/types/${encodeURIComponent(label)}`);
  const selectLink = (r: RelationshipSpec) => setSel({ kind: "link", id: relKey(r) });

  return (
    <div className="flex h-full min-h-[640px] flex-col">
      <PageHeader
        crumbs={[{ label: "Ontology" }]}
        icon={<span className="flex h-9 w-9 items-center justify-center rounded-[4px] bg-accent-soft text-accent"><Icon name="schema" size={20} /></span>}
        title="Supply chain ontology"
        subtitle={<span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span><b className="text-ink">{spec.types.length}</b> object types</span>
          <span><b className="text-ink">{spec.relationships.length}</b> link types</span>
          <span><b className="text-ink">{totalNodes.toLocaleString()}</b> objects</span>
          <span><b className="text-ink">{totalEdges.toLocaleString()}</b> links</span>
        </span>}
        right={<>
          <Tag mono>v{view.row.version}</Tag>
          <Tag intent={approved ? "success" : "warning"} icon={approved ? "check" : "document"}>{approved ? "Approved" : "Draft"}</Tag>
          {view.row.stale && <Tag intent="warning" icon="alert">Stale</Tag>}
          {view.has_approved && view.approved_version !== view.row.version && (
            <Tag intent="primary">v{view.approved_version} is live</Tag>
          )}
          <Btn icon="refresh" kind="ghost" onClick={() => void reload()}>Refresh</Btn>
          <Btn kind={approved && !view.row.stale ? "default" : "primary"} icon="check" onClick={approve}
               disabled={busy !== "" || view.errors.length > 0 || tooEarly}
               title={tooEarly ? `Onboarding is back at the ${stage} stage; finish it before approving` : undefined}>
            {busy === "approve" ? "Applying and loading…" : approved ? "Re-approve and reload" : "Approve and load data"}
          </Btn>
        </>}
      >
        {(view.errors.length > 0 || actionError) && (
          <div className="mt-3 flex flex-col gap-2">
            {view.errors.length > 0 && (
              <Callout intent="danger" title={`${view.errors.length} validation ${view.errors.length === 1 ? "error" : "errors"} - fix before approving`}>
                <ul className="mt-1 list-disc pl-4">{view.errors.map((e) => <li key={e}>{e}</li>)}</ul>
              </Callout>
            )}
            {actionError && (
              <Callout intent="danger" title={actionError}>
                {actionErrors.length > 0 && <ul className="mt-1 list-disc pl-4">{actionErrors.map((e) => <li key={e}>{e}</li>)}</ul>}
              </Callout>
            )}
          </div>
        )}
        {tooEarly && (
          <div className="mt-3">
            <Callout intent="primary" title={`Onboarding is back at the ${stage} stage`}>
              Finish that stage in the chat; the ontology agent then revises this model and it can be approved again.
            </Callout>
          </div>
        )}
        {view.row.stale && (
          <div className="mt-3">
            <Callout intent="warning" title="Upstream answers changed since this model was drafted">
              Re-approve to reload the data against the latest answers, or ask the ontology agent in the chat to revise it.
            </Callout>
          </div>
        )}
      </PageHeader>

      <Tabs<Tab>
        className="bg-panel"
        value={tab}
        onChange={setTab}
        tabs={[
          { id: "graph", label: "Schema graph", icon: "graph" },
          { id: "read", label: "Read the model", icon: "document" },
          { id: "types", label: "Object types", icon: "cube", count: spec.types.length },
          { id: "links", label: "Link types", icon: "link", count: spec.relationships.length },
          { id: "rationale", label: "Rationale", icon: "info" },
          { id: "history", label: "History", icon: "calendar", count: view.versions.length },
        ]}
      />

      <div className="min-h-0 flex-1 p-3">
        {tab === "graph" && (
          <div className="grid h-full min-h-[560px] grid-cols-1 gap-3 lg:grid-cols-[260px_minmax(0,1fr)_340px]">
            <Panel title="Model" icon="layers" className="hidden lg:flex"
                   right={null} bodyClassName="flex flex-col">
              <div className="border-b border-line p-2">
                <SearchInput value={filter} onChange={setFilter} placeholder="Filter types and links" />
              </div>
              <div className="eyebrow flex items-center px-3 pb-1 pt-2.5">Object types <span className="ml-auto tabular-nums">{types.length}</span></div>
              <div className="px-1.5">
                {types.map((t) => {
                  const s = style(t.label);
                  const active = sel?.kind === "type" && sel.id === t.label;
                  return (
                    <button key={t.label} onClick={() => setSel({ kind: "type", id: t.label })} onDoubleClick={() => openType(t.label)}
                            className={`flex w-full items-center gap-2 rounded-[3px] px-2 py-1.5 text-left hover:bg-hover ${active ? "bg-accent-soft shadow-[inset_2px_0_0] shadow-accent" : ""}`}>
                      <TypeIcon label={t.label} color={s.color} icon={s.icon} size={22} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[12.5px] font-medium text-ink">{human(t.label)}</span>
                        <span className="block truncate text-[10.5px] text-faint">{t.properties.length} properties</span>
                      </span>
                      <span className="text-[11px] tabular-nums text-muted">{(counts.nodes[t.label] ?? 0).toLocaleString()}</span>
                    </button>
                  );
                })}
              </div>
              <div className="eyebrow mt-2 flex items-center border-t border-line px-3 pb-1 pt-2.5">Link types <span className="ml-auto tabular-nums">{rels.length}</span></div>
              <div className="px-1.5 pb-2">
                {rels.map((r) => (
                  <LinkChip key={relKey(r)} rel={r} style={style} onClick={() => selectLink(r)}
                            active={sel?.kind === "link" && sel.id === relKey(r)} />
                ))}
              </div>
            </Panel>

            <section className="relative min-h-[480px] overflow-hidden rounded-[4px] border border-line">
              <GraphView
                nodes={nodes}
                links={links}
                highlight={highlight}
                selectedId={sel?.kind === "type" ? sel.id : null}
                selectedLink={sel?.kind === "link" ? sel.id : null}
                onSelect={(n) => setSel({ kind: "type", id: n.id })}
                onSelectLink={(l) => l.key && setSel({ kind: "link", id: l.key })}
                onOpen={(n) => openType(n.id)}
                onBackground={() => setSel(null)}
                nodeRadius={13}
                charge={-1400}
                linkDistance={200}
              />
              <div className="pointer-events-none absolute bottom-2 left-2 flex items-center gap-3 rounded-[3px] border border-line bg-panel/90 px-2 py-1 text-[10.5px] text-faint">
                <span>Click to inspect</span><span>Double-click to open</span><span>Drag to arrange</span>
              </div>
            </section>

            <Panel title={selRel ? "Link type" : selType ? "Object type" : "Inspector"} icon="eye">
              {selType ? (
                <TypeInspector type={selType} spec={spec} counts={counts} style={style}
                               onOpen={() => openType(selType.label)} onSelectLink={selectLink} />
              ) : selRel ? (
                <LinkInspector rel={selRel} counts={counts} style={style} onClose={() => setSel(null)} />
              ) : (
                <div className="flex flex-col gap-3 p-3">
                  <EmptyState icon="eye" title="Nothing selected">
                    Select an object type or a link in the graph to see what it means and how it connects.
                  </EmptyState>
                  {spec.rationale && (
                    <div>
                      <div className="eyebrow mb-1.5">Why this model</div>
                      <p className="text-[12px] leading-relaxed text-muted">{spec.rationale}</p>
                    </div>
                  )}
                </div>
              )}
            </Panel>
          </div>
        )}

        {tab === "read" && (
          <div className="mx-auto max-w-[900px]">
            <div className="mb-3 rounded-[4px] border border-line bg-panel p-4">
              <div className="eyebrow mb-1">In one paragraph</div>
              <p className="text-[13.5px] leading-relaxed text-body">{spec.rationale || "The ontology agent left no rationale."}</p>
            </div>
            <div className="flex flex-col gap-2.5">
              {story(spec).map(({ type, outgoing, incoming }) => {
                const s = style(type.label);
                return (
                  <article key={type.label} className="rounded-[4px] border border-line bg-panel">
                    <header className="flex items-center gap-3 border-b border-line px-4 py-2.5">
                      <TypeIcon label={type.label} color={s.color} icon={s.icon} size={28} />
                      <div className="min-w-0 flex-1">
                        <Link to={`/ontology/types/${encodeURIComponent(type.label)}`} className="text-[14px] font-semibold text-ink hover:underline">
                          {human(type.label)}
                        </Link>
                        <div className="text-[11px] text-faint">{(counts.nodes[type.label] ?? 0).toLocaleString()} objects · {type.properties.length} properties</div>
                      </div>
                      <div className="flex flex-wrap gap-1">{type.tags.map((t) => <Tag key={t}>{t}</Tag>)}</div>
                    </header>
                    <div className="px-4 py-3">
                      <p className="text-[13px] leading-relaxed text-body">{type.description}</p>
                      {outgoing.length > 0 && (
                        <ul className="mt-2.5 flex flex-col gap-1.5 border-l-2 pl-3" style={{ borderColor: `${s.color}66` }}>
                          {outgoing.map((o) => (
                            <li key={relKey(o.rel)} className="text-[13px]">
                              <SentenceView rel={o.rel} style={style} />
                              {o.rel.description && <span className="text-muted"> {o.rel.description}</span>}
                            </li>
                          ))}
                        </ul>
                      )}
                      {incoming.length > 0 && (
                        <div className="mt-2 text-[11.5px] text-faint">
                          Referenced by {incoming.map((r, i) => (
                            <span key={relKey(r)}>{i > 0 && ", "}<span style={{ color: style(r.from).color }}>{human(r.from)}</span> <span className="font-mono">{r.type}</span></span>
                          ))}
                        </div>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        )}

        {tab === "types" && (
          <TableShell>
            <thead>
              <tr>
                <Th>Object type</Th><Th>Description</Th><Th right>Properties</Th><Th right>Link types</Th><Th right>Objects</Th><Th>Tags</Th>
              </tr>
            </thead>
            <tbody>
              {spec.types.map((t) => {
                const s = style(t.label);
                const nl = spec.relationships.filter((r) => r.from === t.label || r.to === t.label).length;
                return (
                  <tr key={t.label} className="cursor-pointer border-t border-line hover:bg-hover" onClick={() => openType(t.label)}>
                    <Td><span className="flex items-center gap-2"><TypeIcon label={t.label} color={s.color} icon={s.icon} size={22} /><span className="font-medium text-ink">{human(t.label)}</span></span></Td>
                    <Td className="max-w-[460px] text-muted">{t.description}</Td>
                    <Td right>{t.properties.length}</Td>
                    <Td right>{nl}</Td>
                    <Td right className="text-ink">{(counts.nodes[t.label] ?? 0).toLocaleString()}</Td>
                    <Td><span className="flex flex-wrap gap-1">{t.tags.map((g) => <Tag key={g}>{g}</Tag>)}</span></Td>
                  </tr>
                );
              })}
            </tbody>
          </TableShell>
        )}

        {tab === "links" && (
          <TableShell>
            <thead>
              <tr><Th>Link type</Th><Th>From</Th><Th>To</Th><Th>Cardinality</Th><Th>Meaning</Th><Th right>Links</Th></tr>
            </thead>
            <tbody>
              {spec.relationships.map((r) => {
                const f = style(r.from);
                const t = style(r.to);
                return (
                  <tr key={relKey(r)} className="cursor-pointer border-t border-line align-top hover:bg-hover"
                      onClick={() => { setTab("graph"); selectLink(r); }}>
                    <Td><span className="font-mono text-[11.5px] text-ink">{r.type}</span></Td>
                    <Td><span className="flex items-center gap-1.5"><TypeIcon label={r.from} color={f.color} icon={f.icon} size={18} />{human(r.from)}</span></Td>
                    <Td><span className="flex items-center gap-1.5"><TypeIcon label={r.to} color={t.color} icon={t.icon} size={18} />{human(r.to)}</span></Td>
                    <Td><span className="flex items-center gap-1.5"><Tag mono>{CARD_SHORT[r.cardinality]}</Tag><span className="text-faint">{CARD_LABEL[r.cardinality]}</span></span></Td>
                    <Td className="max-w-[460px]"><SentenceView rel={r} style={style} /></Td>
                    <Td right className="text-ink">{(counts.edges[r.type] ?? 0).toLocaleString()}</Td>
                  </tr>
                );
              })}
            </tbody>
          </TableShell>
        )}

        {tab === "rationale" && (
          <div className="mx-auto grid max-w-[1100px] gap-3 lg:grid-cols-[2fr_1fr]">
            <Panel title="Why this model" icon="info">
              <div className="flex flex-col gap-3 p-4">
                <p className="text-[13.5px] leading-relaxed text-body">{spec.rationale || "No rationale recorded."}</p>
                {view.row.rationale && view.row.rationale !== spec.rationale && (
                  <p className="border-t border-line pt-3 text-[12.5px] leading-relaxed text-muted">{view.row.rationale}</p>
                )}
              </div>
            </Panel>
            <div className="flex flex-col gap-3">
              <Panel title="Assumptions" icon="alert" count={spec.coverage?.assumed?.length ?? 0}>
                <ul className="flex flex-col gap-1.5 p-3">
                  {(spec.coverage?.assumed ?? []).map((a) => (
                    <li key={a} className="flex gap-2 text-[12px] text-body"><Icon name="alert" size={13} className="mt-0.5 text-amber-400" />{a}</li>
                  ))}
                  {!spec.coverage?.assumed?.length && <li className="text-[12px] text-faint">None recorded.</li>}
                </ul>
              </Panel>
              <Panel title="Answers the model does not hold" icon="document" count={spec.coverage?.unmapped_answers?.length ?? 0}>
                <ul className="flex flex-col gap-1.5 p-3">
                  {(spec.coverage?.unmapped_answers ?? []).map((a) => (
                    <li key={a} className="flex gap-2 text-[12px] text-body"><Icon name="info" size={13} className="mt-0.5 text-sky-400" />{a}</li>
                  ))}
                  {!spec.coverage?.unmapped_answers?.length && <li className="text-[12px] text-faint">Everything answered is modelled.</li>}
                </ul>
              </Panel>
              <Panel title="Indexes" icon="key" count={spec.indexes.length}>
                <ul className="flex flex-wrap gap-1.5 p-3">
                  {spec.indexes.map((i) => <Tag key={`${i.label}.${i.property}`} mono>{i.label}.{i.property}</Tag>)}
                </ul>
              </Panel>
            </div>
          </div>
        )}

        {tab === "history" && (
          <TableShell>
            <thead><tr><Th>Version</Th><Th>Status</Th><Th>Stale</Th><Th>Saved</Th></tr></thead>
            <tbody>
              {view.versions.map((v) => (
                <tr key={v.id} className="border-t border-line">
                  <Td><span className="font-mono text-ink">v{v.version}</span>{v.version === view.row.version && <span className="ml-2 text-[11px] text-faint">current</span>}</Td>
                  <Td><Tag intent={v.status === "approved" ? "success" : v.status === "draft" ? "warning" : "none"}>{v.status}</Tag></Td>
                  <Td>{v.stale ? <Tag intent="warning">stale</Tag> : <span className="text-faint">-</span>}</Td>
                  <Td className="text-muted">{v.ts ? new Date(v.ts).toLocaleString() : ""}</Td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        )}
      </div>
    </div>
  );
}
