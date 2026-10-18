import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import type { ExpertRole, PropertySpec, TypeSpec } from "../api";
import GraphView from "../components/GraphView";
import type { ViewLink, ViewNode } from "../components/GraphView";
import { Icon } from "../components/icons";
import ObjectTable from "../components/ObjectTable";
import { LinkInspector, SentenceView, relKey } from "../components/OntologyBits";
import {
  Btn, Callout, EmptyState, KeyValue, PageHeader, Panel, Tabs, Tag, Td, Th, TableShell, TypeIcon,
} from "../components/ui";
import { PROPERTY_TYPES } from "../constants";
import { CARD_LABEL, CARD_SHORT, human, plural } from "../ontologyText";
import { setOntologyCache, useOntology } from "../useOntology";

type Tab = "overview" | "properties" | "links" | "objects";

/** One object type: what it means, its properties, how it links to the rest of the model, and its objects. */
export default function OntologyType() {
  const { label = "" } = useParams();
  const nav = useNavigate();
  const { view, spec, style, loading } = useOntology();
  const [tab, setTab] = useState<Tab>("overview");
  const [experts, setExperts] = useState<ExpertRole[]>([]);
  const [selLink, setSelLink] = useState<string | null>(null);

  useEffect(() => {
    api.experts().then((r) => setExperts(r.experts)).catch(() => setExperts([]));
  }, []);
  useEffect(() => {
    setSelLink(null);
  }, [label]);

  const type = spec?.types.find((t) => t.label === label);
  const counts = view?.counts ?? { nodes: {}, edges: {} };
  const out = useMemo(() => (spec?.relationships ?? []).filter((r) => r.from === label), [spec, label]);
  const inc = useMemo(() => (spec?.relationships ?? []).filter((r) => r.to === label && r.from !== label), [spec, label]);
  const indexed = useMemo(() => new Set((spec?.indexes ?? []).filter((i) => i.label === label).map((i) => i.property)), [spec, label]);

  const ego = useMemo(() => {
    const rels = [...out, ...inc];
    const labels = new Set([label, ...rels.flatMap((r) => [r.from, r.to])]);
    const nodes: ViewNode[] = [...labels].map((l) => {
      const s = style(l);
      return { id: l, label: l, title: human(l), color: s.color, icon: s.icon, size: l === label ? 1.5 : 1 };
    });
    const links: ViewLink[] = rels.map((r) => ({ source: r.from, target: r.to, type: r.type, badge: CARD_SHORT[r.cardinality], key: relKey(r) }));
    return { nodes, links };
  }, [out, inc, label, style]);

  if (!spec) {
    return <div className="p-6 text-[12px] text-faint">{loading ? "Loading…" : "No ontology yet."}</div>;
  }
  if (!type) {
    return (
      <div className="p-6">
        <EmptyState icon="cube" title={`No object type "${label}"`} action={<Link className="link text-[12px]" to="/ontology">Back to the ontology</Link>} />
      </div>
    );
  }

  const s = style(type.label);
  const focusing = experts.filter((e) => e.focus_types.includes(type.label) && e.status !== "retired");
  const n = counts.nodes[type.label] ?? 0;
  const selRel = spec.relationships.find((r) => relKey(r) === selLink);

  return (
    <div className="flex h-full min-h-[640px] flex-col">
      <PageHeader
        crumbs={[{ label: "Ontology", to: "/ontology" }, { label: "Object types", to: "/ontology" }, { label: human(type.label) }]}
        icon={<TypeIcon label={type.label} color={s.color} icon={s.icon} size={40} />}
        title={human(type.label)}
        subtitle={<span className="flex flex-wrap items-center gap-x-3"><span className="font-mono text-faint">{type.label}</span><span>{n.toLocaleString()} objects</span><span>{type.properties.length} properties</span><span>{out.length + inc.length} link types</span></span>}
        right={<>
          {type.tags.map((t) => <Tag key={t}>{t}</Tag>)}
          <Btn icon="table" onClick={() => nav(`/objects/${encodeURIComponent(type.label)}`)}>Explore objects</Btn>
        </>}
      />
      <Tabs<Tab>
        className="bg-panel"
        value={tab}
        onChange={setTab}
        tabs={[
          { id: "overview", label: "Overview", icon: "info" },
          { id: "properties", label: "Properties", icon: "list", count: type.properties.length },
          { id: "links", label: "Link types", icon: "link", count: out.length + inc.length },
          { id: "objects", label: "Objects", icon: "table", count: n },
        ]}
      />
      <div className="min-h-0 flex-1 p-3">
        {tab === "overview" && (
          <div className="grid h-full gap-3 xl:grid-cols-[minmax(0,1fr)_420px]">
            <div className="flex min-w-0 flex-col gap-3">
              <Panel title="About" icon="info" className="shrink-0">
                <div className="flex flex-col gap-3 p-4">
                  <p className="text-[14px] leading-relaxed text-body">{type.description || "No description."}</p>
                  <KeyValue rows={[
                    ["API name", <span className="font-mono">{type.label}</span>],
                    ["Title property", <span className="font-mono">{type.display?.title_property || "name"}</span>],
                    ["ID pattern", <span className="font-mono">{type.id_pattern}</span>],
                    ["Plural", plural(type.label)],
                    ["Indexed on", indexed.size ? <span className="flex gap-1">{[...indexed].map((p) => <Tag key={p} mono icon="key">{p}</Tag>)}</span> : <span className="text-faint">—</span>],
                  ]} />
                </div>
              </Panel>
              <Panel title="How it connects" icon="link" count={out.length + inc.length} className="shrink-0">
                <ul className="divide-y divide-line">
                  {[...out, ...inc].map((r) => (
                    <li key={relKey(r)} className="flex items-start gap-3 px-4 py-2.5">
                      <Tag mono intent={r.from === type.label ? "primary" : "none"}>{r.from === type.label ? "out" : "in"}</Tag>
                      <div className="min-w-0 flex-1 text-[13px]">
                        <SentenceView rel={r} style={style} />
                        {r.description && <div className="mt-0.5 text-[12px] text-faint">{r.description}</div>}
                      </div>
                      <span className="font-mono text-[11px] text-muted">{r.type}</span>
                    </li>
                  ))}
                  {out.length + inc.length === 0 && <li className="p-4 text-[12px] text-faint">This type has no links.</li>}
                </ul>
              </Panel>
              <Panel title="Experts reasoning over this type" icon="experts" count={focusing.length} className="shrink-0">
                <ul className="divide-y divide-line">
                  {focusing.map((e) => (
                    <li key={e.id} className="flex items-start gap-3 px-4 py-2.5">
                      <Icon name="experts" size={15} className="mt-0.5 shrink-0 text-slate-500" />
                      <div className="min-w-0">
                        <Link to="/experts" className="text-[13px] font-medium text-ink hover:underline">{e.title}</Link>
                        <div className="text-[12px] text-muted">{e.mandate}</div>
                      </div>
                      <Tag intent={e.status === "approved" ? "success" : "warning"} className="ml-auto">{e.status}</Tag>
                    </li>
                  ))}
                  {focusing.length === 0 && <li className="p-4 text-[12px] text-faint">No expert role focuses on {human(type.label)} yet.</li>}
                </ul>
              </Panel>
            </div>
            <Panel title="Neighbourhood" icon="graph" className="min-h-[420px]">
              <GraphView nodes={ego.nodes} links={ego.links} selectedId={type.label} nodeRadius={13} charge={-700} linkDistance={130}
                         onOpen={(nd) => nav(`/ontology/types/${encodeURIComponent(nd.id)}`)}
                         onSelect={(nd) => nd.id !== type.label && nav(`/ontology/types/${encodeURIComponent(nd.id)}`)} />
            </Panel>
          </div>
        )}

        {tab === "properties" && <PropertiesTab type={type} indexed={indexed} />}

        {tab === "links" && (
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_380px]">
            <TableShell>
              <thead><tr><Th>Direction</Th><Th>Link type</Th><Th>Other type</Th><Th>Cardinality</Th><Th>Meaning</Th><Th right>Links</Th></tr></thead>
              <tbody>
                {[...out, ...inc].map((r) => {
                  const other = r.from === type.label ? r.to : r.from;
                  const os = style(other);
                  return (
                    <tr key={relKey(r)} onClick={() => setSelLink(relKey(r))}
                        className={`cursor-pointer border-t border-line align-top ${selLink === relKey(r) ? "bg-accent-soft" : "hover:bg-hover"}`}>
                      <Td><Tag mono intent={r.from === type.label ? "primary" : "none"}>{r.from === type.label ? "outgoing" : "incoming"}</Tag></Td>
                      <Td><span className="font-mono text-ink">{r.type}</span></Td>
                      <Td>
                        <Link to={`/ontology/types/${encodeURIComponent(other)}`} onClick={(e) => e.stopPropagation()} className="flex items-center gap-1.5 hover:underline">
                          <TypeIcon label={other} color={os.color} icon={os.icon} size={18} />{human(other)}
                        </Link>
                      </Td>
                      <Td><span title={CARD_LABEL[r.cardinality]}><Tag mono>{CARD_SHORT[r.cardinality]}</Tag></span></Td>
                      <Td className="max-w-[420px]"><SentenceView rel={r} style={style} /></Td>
                      <Td right className="text-ink">{(counts.edges[r.type] ?? 0).toLocaleString()}</Td>
                    </tr>
                  );
                })}
              </tbody>
            </TableShell>
            <Panel title="Link type" icon="link">
              {selRel ? <LinkInspector rel={selRel} counts={counts} style={style} onClose={() => setSelLink(null)} />
                : <EmptyState icon="link" title="Select a link type">Its meaning, cardinality and properties appear here.</EmptyState>}
            </Panel>
          </div>
        )}

        {tab === "objects" && (
          <div className="h-full min-h-[480px] overflow-hidden border border-line bg-panel">
            <ObjectTable type={type} className="h-full" onOpen={(id) => nav(`/objects/${encodeURIComponent(type.label)}/${encodeURIComponent(id)}`)} />
          </div>
        )}
      </div>
    </div>
  );
}

function PropertiesTab({ type, indexed }: { type: TypeSpec; indexed: Set<string> }) {
  const { spec } = useOntology();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<TypeSpec>(type);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setDraft(type), [type]);

  const setProp = (i: number, next: PropertySpec) =>
    setDraft({ ...draft, properties: draft.properties.map((p, j) => (i === j ? next : p)) });

  const save = async () => {
    if (!spec) return;
    setBusy(true);
    setError(null);
    setErrors([]);
    try {
      const v = await api.patchDraft({ ...spec, types: spec.types.map((t) => (t.label === type.label ? draft : t)) });
      setOntologyCache(v);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      if (e instanceof ApiError) setErrors(e.errors);
    } finally {
      setBusy(false);
    }
  };

  const props = editing ? draft.properties : type.properties;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <div className="text-[12px] text-muted">
          Every {human(type.label)} carries these properties. <span className="text-rose-300">*</span> required,
          <Icon name="key" size={11} className="mx-1 inline text-amber-300" />indexed.
        </div>
        <div className="ml-auto flex gap-2">
          {editing ? (
            <>
              <Btn kind="ghost" onClick={() => { setEditing(false); setDraft(type); setErrors([]); setError(null); }}>Cancel</Btn>
              <Btn kind="primary" icon="check" onClick={save} disabled={busy}>{busy ? "Validating…" : "Save as new draft version"}</Btn>
            </>
          ) : (
            <Btn icon="document" onClick={() => setEditing(true)}>Edit properties</Btn>
          )}
        </div>
      </div>
      {editing && (
        <Callout intent="primary" title="Editing creates a new draft version">
          The model has to be re-approved before the change reaches the graph. For structural changes, ask the ontology agent in the chat: it keeps the rationale and the data mapping in step.
        </Callout>
      )}
      {error && (
        <Callout intent="danger" title={error}>
          {errors.length > 0 && <ul className="mt-1 list-disc pl-4">{errors.map((e) => <li key={e}>{e}</li>)}</ul>}
        </Callout>
      )}
      <TableShell>
        <thead>
          <tr><Th>Property</Th><Th>Type</Th><Th>Unit</Th><Th>Required</Th><Th>Description</Th><Th>Allowed values</Th></tr>
        </thead>
        <tbody>
          {props.map((p, i) => (
            <tr key={i} className="border-t border-line align-top">
              <Td>
                {editing ? <input className="field w-40 font-mono" value={p.name} onChange={(e) => setProp(i, { ...p, name: e.target.value })} /> : (
                  <span className="flex items-center gap-1.5">
                    <span className="font-mono text-ink">{p.name}</span>
                    {p.required && <span className="text-rose-300">*</span>}
                    {indexed.has(p.name) && <span title="indexed"><Icon name="key" size={11} className="text-amber-300" /></span>}
                    {p.name === (type.display?.title_property || "name") && <Tag intent="primary">title</Tag>}
                  </span>
                )}
              </Td>
              <Td>
                {editing ? (
                  <select className="field" value={p.type} onChange={(e) => setProp(i, { ...p, type: e.target.value })}>
                    {PROPERTY_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                ) : <Tag mono>{p.type}</Tag>}
              </Td>
              <Td>{editing ? <input className="field w-20" value={p.unit} onChange={(e) => setProp(i, { ...p, unit: e.target.value })} /> : <span className="text-muted">{p.unit || "—"}</span>}</Td>
              <Td>{editing ? <input type="checkbox" checked={p.required} onChange={(e) => setProp(i, { ...p, required: e.target.checked })} /> : p.required ? <Icon name="check" size={14} className="text-emerald-400" /> : <span className="text-faint">—</span>}</Td>
              <Td className="min-w-[260px] max-w-[460px]">
                {editing ? <input className="field w-full" value={p.description} onChange={(e) => setProp(i, { ...p, description: e.target.value })} />
                  : <span className="text-body">{p.description || <span className="text-faint">—</span>}</span>}
              </Td>
              <Td>
                {p.options.length ? <span className="flex flex-wrap gap-1">{p.options.map((o) => <Tag key={o}>{o}</Tag>)}</span> : <span className="text-faint">—</span>}
              </Td>
            </tr>
          ))}
        </tbody>
      </TableShell>
    </div>
  );
}
