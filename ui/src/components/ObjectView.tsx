import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import type { ObjectDetail } from "../api";
import { human, plural, verb } from "../ontologyText";
import { useOntology } from "../useOntology";
import GraphView from "./GraphView";
import type { ViewLink, ViewNode } from "./GraphView";
import { Icon } from "./icons";
import { formatValue } from "./ObjectTable";
import { Btn, EmptyState, Tabs, Tag, TypeIcon } from "./ui";
import { CONFIDENCE_COLORS } from "./colors";

type Tab = "properties" | "links" | "graph" | "provenance";

const objUrl = (label: string, id: string) => `/objects/${encodeURIComponent(label)}/${encodeURIComponent(id)}`;

/** One object, the way Foundry's Object View shows it: header, properties, linked objects, a search-around
 *  graph, and (Ripple's addition) where each value came from. */
export default function ObjectView({ label, id, onClose, initialTab = "properties" }: {
  label: string; id: string; onClose?: () => void; initialTab?: Tab;
}) {
  const { typeMap, style } = useOntology();
  const nav = useNavigate();
  const [obj, setObj] = useState<ObjectDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>(initialTab);

  useEffect(() => {
    setObj(null);
    setError(null);
    api.object(label, id).then(setObj).catch((e: Error) => setError(e.message));
  }, [label, id]);

  const type = typeMap[label];
  const s = style(label);
  const linkCount = obj?.links.reduce((a, g) => a + g.objects.length, 0) ?? 0;

  return (
    <div className="flex h-full min-h-0 flex-col bg-panel">
      <div className="flex shrink-0 items-start gap-3 border-b border-line px-4 py-3">
        <TypeIcon label={label} color={s.color} icon={s.icon} size={40} />
        <div className="min-w-0 flex-1">
          <Link to={`/ontology/types/${encodeURIComponent(label)}`} className="eyebrow hover:text-muted" style={{ color: s.color }}>{human(label)}</Link>
          <div className="truncate text-[17px] font-semibold leading-snug text-ink">{obj?.title ?? (error ? "Not found" : "Loading…")}</div>
          <div className="mt-0.5 flex items-center gap-2 font-mono text-[11px] text-faint">
            <Icon name="key" size={11} />{id}
          </div>
        </div>
        {onClose && <Btn small kind="minimal" icon="close" onClick={onClose} title="Close" />}
      </div>
      <Tabs<Tab>
        value={tab}
        onChange={setTab}
        tabs={[
          { id: "properties", label: "Properties", icon: "list" },
          { id: "links", label: "Links", icon: "link", count: linkCount },
          { id: "graph", label: "Graph", icon: "graph" },
          { id: "provenance", label: "Provenance", icon: "document", count: obj?.provenance.length },
        ]}
      />
      <div className="min-h-0 flex-1 overflow-auto">
        {error && <div className="p-4 text-[12px] text-rose-300">{error}</div>}
        {obj && tab === "properties" && (
          <dl className="divide-y divide-line">
            {(type?.properties ?? Object.keys(obj.properties).filter((k) => k !== "id").map((k) => ({ name: k, type: "", unit: "", description: "", required: false, options: [] }))).map((p) => (
              <div key={p.name} className="grid grid-cols-[minmax(9rem,38%)_1fr] gap-3 px-4 py-2" title={p.description}>
                <dt className="min-w-0">
                  <div className="truncate text-[12px] text-muted">{human(p.name.replace(/_/g, " ")).replace(/^./, (c) => c.toUpperCase())}</div>
                  {p.description && <div className="truncate text-[10.5px] text-faint">{p.description}</div>}
                </dt>
                <dd className="min-w-0 break-words text-[13px] text-ink">
                  {p.type === "enum" && obj.properties[p.name] ? <Tag>{String(obj.properties[p.name])}</Tag> : formatValue(obj.properties[p.name], p.unit, p.type)}
                </dd>
              </div>
            ))}
            {"confidence" in obj.properties && (
              <div className="grid grid-cols-[minmax(9rem,38%)_1fr] gap-3 px-4 py-2">
                <dt className="text-[12px] text-muted">Data confidence</dt>
                <dd><Tag intent={obj.properties.confidence === "exact" ? "success" : obj.properties.confidence === "synthetic" ? "info" : "warning"}>{String(obj.properties.confidence)}</Tag></dd>
              </div>
            )}
          </dl>
        )}
        {obj && tab === "links" && (
          obj.links.length === 0 ? <EmptyState icon="link" title="No linked objects" /> : (
            <div className="flex flex-col">
              {obj.links.map((g) => {
                const gs = style(g.label);
                const n = g.objects.length;
                return (
                  <section key={`${g.type}:${g.direction}:${g.label}`} className="border-b border-line">
                    <header className="flex items-center gap-2 bg-sunken px-4 py-2">
                      <TypeIcon label={g.label} color={gs.color} icon={gs.icon} size={20} />
                      <div className="min-w-0 flex-1 text-[12.5px]">
                        {g.direction === "out" ? (
                          <span>This {human(label)} <b className="font-medium text-ink">{verb(g.type)}</b> {n} {n === 1 ? human(g.label) : plural(g.label)}</span>
                        ) : (
                          <span>{n} {n === 1 ? human(g.label) : plural(g.label)} <b className="font-medium text-ink">{verb(g.type)}</b> this {human(label)}</span>
                        )}
                      </div>
                      <Tag mono>{g.direction === "out" ? "→" : "←"} {g.type}</Tag>
                    </header>
                    <ul>
                      {g.objects.map((o) => (
                        <li key={o.id}>
                          <button onClick={() => nav(objUrl(o.label, o.id))}
                                  className="group flex w-full items-center gap-2 px-4 py-1.5 text-left hover:bg-hover">
                            <span className="h-1.5 w-1.5" style={{ background: gs.color }} />
                            <span className="min-w-0 flex-1 truncate text-[12.5px] text-ink">{o.title}</span>
                            <span className="font-mono text-[10.5px] text-faint">{o.id}</span>
                            <Icon name="chevronRight" size={12} className="text-slate-600 group-hover:text-muted" />
                          </button>
                        </li>
                      ))}
                    </ul>
                  </section>
                );
              })}
            </div>
          )
        )}
        {obj && tab === "graph" && <SearchAround root={obj} />}
        {obj && tab === "provenance" && (
          obj.provenance.length === 0 ? (
            <EmptyState icon="document" title="No recorded sources">This object was not traced back to a form answer or an upload.</EmptyState>
          ) : (
            <ul className="divide-y divide-line">
              {obj.provenance.map((p) => (
                <li key={p.source_id} className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <Icon name={p.source_label === "_Attachment" ? "document" : "chat"} size={14} className="text-faint" />
                    <span className="text-[12.5px] font-medium text-ink">{p.source_ref || p.source_id}</span>
                    <span className="font-mono text-[10.5px] text-faint">{p.source_id}</span>
                    <span className={`ml-auto px-1.5 py-px text-[10.5px] text-slate-100 ${CONFIDENCE_COLORS[p.confidence] ?? "bg-raised"}`}>{p.confidence}</span>
                  </div>
                  <div className="mt-1 text-[11.5px] text-muted">
                    {p.source_label === "_Attachment" ? "Uploaded file" : "Answer in the onboarding data pack"} · source: {p.source}
                  </div>
                  {p.source_value && <pre className="mt-1.5 max-h-28 overflow-auto bg-sunken p-2 font-mono text-[11px] text-body">{p.source_value}</pre>}
                </li>
              ))}
            </ul>
          )
        )}
      </div>
    </div>
  );
}

/** A graph of the object and its neighbours. Clicking a neighbour searches around it (adds its own links);
 *  double-clicking opens it. */
function SearchAround({ root }: { root: ObjectDetail }) {
  const { style } = useOntology();
  const nav = useNavigate();
  const [nodes, setNodes] = useState<Map<string, ViewNode>>(new Map());
  const [links, setLinks] = useState<Map<string, ViewLink>>(new Map());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>(root.id);

  const merge = useCallback((d: ObjectDetail, ns: Map<string, ViewNode>, ls: Map<string, ViewLink>) => {
    const add = (id: string, label: string, title: string) => {
      if (!ns.has(id)) {
        const s = style(label);
        ns.set(id, { id, label, title, color: s.color, icon: s.icon });
      }
    };
    add(d.id, d.label, d.title);
    for (const g of d.links) {
      for (const o of g.objects.slice(0, 40)) {
        add(o.id, o.label, o.title);
        const [a, b] = g.direction === "out" ? [d.id, o.id] : [o.id, d.id];
        ls.set(`${a}|${g.type}|${b}`, { source: a, target: b, type: g.type });
      }
    }
  }, [style]);

  useEffect(() => {
    const ns = new Map<string, ViewNode>();
    const ls = new Map<string, ViewLink>();
    merge(root, ns, ls);
    const r = ns.get(root.id);
    if (r) r.size = 1.4;
    setNodes(ns);
    setLinks(ls);
    setExpanded(new Set([root.id]));
    setSelected(root.id);
  }, [root, merge]);

  const expand = async (n: ViewNode) => {
    setSelected(n.id);
    if (expanded.has(n.id) || busy) return;
    setBusy(n.id);
    try {
      const d = await api.object(n.label, n.id);
      const ns = new Map(nodes);
      const ls = new Map(links);
      merge(d, ns, ls);
      setNodes(ns);
      setLinks(ls);
      setExpanded(new Set([...expanded, n.id]));
    } catch {
      /* a neighbour of a type outside the approved spec cannot be opened; leave it unexpanded */
    } finally {
      setBusy(null);
    }
  };

  const nodeList = useMemo(() => [...nodes.values()], [nodes]);
  const linkList = useMemo(() => [...links.values()], [links]);
  const legend = useMemo(() => [...new Set(nodeList.map((n) => n.label))], [nodeList]);

  return (
    <div className="relative h-full min-h-[420px]">
      <GraphView nodes={nodeList} links={linkList} labelWith="title" selectedId={selected} nodeRadius={8}
                 charge={-420} linkDistance={80}
                 onSelect={(n) => void expand(n)} onOpen={(n) => nav(objUrl(n.label, n.id))} />
      <div className="pointer-events-none absolute bottom-2 left-2 right-12 flex flex-wrap items-center gap-x-3 gap-y-1 border border-line bg-panel/90 px-2 py-1 text-[10.5px] text-faint">
        {legend.map((l) => (
          <span key={l} className="flex items-center gap-1"><span className="h-2 w-2" style={{ background: style(l).color }} />{human(l)}</span>
        ))}
        <span className="ml-auto">{busy ? "searching around…" : "click: search around · double-click: open"}</span>
      </div>
    </div>
  );
}
