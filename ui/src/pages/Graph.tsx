import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { GraphSample } from "../api";
import GraphView from "../components/GraphView";
import type { ViewLink, ViewNode } from "../components/GraphView";
import { Icon } from "../components/icons";
import ObjectView from "../components/ObjectView";
import { Btn, EmptyState, PageHeader, Panel, SearchInput, TypeIcon } from "../components/ui";
import { human } from "../ontologyText";
import { useOntology } from "../useOntology";

const SIZES = [300, 800, 2000];

/** The instance graph: a sample of the loaded objects, filterable by type, with an Object View inspector. */
export default function Graph() {
  const { spec, style } = useOntology();
  const [limit, setLimit] = useState(800);
  const [g, setG] = useState<GraphSample | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<{ id: string; label: string } | null>(null);

  useEffect(() => {
    setG(null);
    api.graph(limit).then(setG).catch((e: Error) => setError(e.message));
  }, [limit]);

  const byLabel = useMemo(() => {
    const m: Record<string, number> = {};
    for (const n of g?.nodes ?? []) m[n.label] = (m[n.label] ?? 0) + 1;
    return m;
  }, [g]);

  const nodes = useMemo<ViewNode[]>(() => (g?.nodes ?? []).filter((n) => !hidden.has(n.label)).map((n) => {
    const s = style(n.label);
    return { id: n.id, label: n.label, title: n.title, color: s.color, icon: s.icon };
  }), [g, hidden, style]);
  const visible = useMemo(() => new Set(nodes.map((n) => n.id)), [nodes]);
  const links = useMemo<ViewLink[]>(() => (g?.edges ?? []).filter((e) => visible.has(e.source) && visible.has(e.target))
    .map((e) => ({ source: e.source, target: e.target, type: e.type })), [g, visible]);
  const highlight = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return undefined;
    return new Set(nodes.filter((n) => n.title.toLowerCase().includes(t) || n.id.toLowerCase().includes(t)).map((n) => n.id));
  }, [q, nodes]);

  const labels = (spec?.types.map((t) => t.label) ?? Object.keys(byLabel)).filter((l) => byLabel[l]);
  const toggle = (l: string) => {
    const next = new Set(hidden);
    if (next.has(l)) next.delete(l);
    else next.add(l);
    setHidden(next);
  };

  return (
    <div className="flex h-full min-h-[600px] flex-col">
      <PageHeader
        crumbs={[{ label: "Graph" }]}
        title="Instance graph"
        subtitle={g ? `${nodes.length.toLocaleString()} of ${g.nodes.length.toLocaleString()} sampled objects · ${links.length.toLocaleString()} links` : "Loading the sample…"}
        right={<>
          <span className="text-[11px] text-faint">Sample</span>
          <div className="flex overflow-hidden border border-line-strong">
            {SIZES.map((s) => (
              <button key={s} onClick={() => setLimit(s)}
                      className={`h-7 px-2.5 text-[12px] ${limit === s ? "bg-accent-strong text-white" : "bg-raised text-muted hover:text-ink"}`}>{s}</button>
            ))}
          </div>
        </>}
      />
      <div className="grid min-h-0 flex-1 gap-3 p-3 lg:grid-cols-[240px_minmax(0,1fr)] xl:grid-cols-[240px_minmax(0,1fr)_400px]">
        <Panel title="Layers" icon="layers" className="hidden lg:flex"
               right={hidden.size > 0 ? <Btn small kind="minimal" onClick={() => setHidden(new Set())}>Show all</Btn> : null}>
          <div className="border-b border-line p-2">
            <SearchInput value={q} onChange={setQ} placeholder="Highlight by name or id" />
          </div>
          <div className="p-1.5">
            {labels.map((l) => {
              const s = style(l);
              const off = hidden.has(l);
              return (
                <button key={l} onClick={() => toggle(l)}
                        className={`flex w-full items-center gap-2 px-2 py-1.5 text-left hover:bg-hover ${off ? "opacity-45" : ""}`}>
                  <span className={`flex h-3.5 w-3.5 items-center justify-center border ${off ? "border-line-strong" : "border-accent bg-accent-strong"}`}>
                    {!off && <Icon name="check" size={10} className="text-white" strokeWidth={3} />}
                  </span>
                  <TypeIcon label={l} color={s.color} icon={s.icon} size={20} />
                  <span className="min-w-0 flex-1 truncate text-[12.5px] text-ink">{human(l)}</span>
                  <span className="text-[11px] tabular-nums text-muted">{byLabel[l] ?? 0}</span>
                </button>
              );
            })}
          </div>
        </Panel>
        <section className="relative min-h-[480px] overflow-hidden border border-line">
          {error ? <div className="p-4 text-[12px] text-rose-300">{error}</div> : !g ? (
            <div className="flex h-full items-center justify-center text-[12px] text-faint">Loading the graph…</div>
          ) : (
            <GraphView nodes={nodes} links={links} labelWith="title" highlight={highlight} selectedId={sel?.id ?? null}
                       onSelect={(n) => setSel({ id: n.id, label: n.label })} onBackground={() => setSel(null)}
                       nodeRadius={6} charge={-90} linkDistance={40} linkLabels={false}
                       emptyText="No objects loaded yet - approve the ontology to load data." />
          )}
        </section>
        <section className="hidden min-h-[480px] overflow-hidden border border-line xl:block">
          {sel ? <ObjectView key={sel.id} label={sel.label} id={sel.id} onClose={() => setSel(null)} /> : (
            <div className="h-full bg-panel">
              <EmptyState icon="eye" title="Select an object">
                Click a node to open its properties, links and sources here. <Link to="/objects" className="link">Browse all objects</Link>
              </EmptyState>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
