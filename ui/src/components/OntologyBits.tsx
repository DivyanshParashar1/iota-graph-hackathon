import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { OntologySpec, RelationshipSpec, TypeSpec } from "../api";
import { CARD_LABEL, CARD_SHORT, human, sentence } from "../ontologyText";
import type { TypeStyle } from "../useOntology";
import { Icon } from "./icons";
import { Btn, KeyValue, Tag, TypeIcon } from "./ui";

// Shared pieces of the ontology screens: a link type as a readable sentence, the selection inspector, and the
// "From -[TYPE]-> To" chip.

type StyleFn = (label: string) => TypeStyle;

export function TypeRef({ label, text, style }: { label: string; text?: string; style: StyleFn }) {
  const s = style(label);
  return (
    <Link to={`/ontology/types/${encodeURIComponent(label)}`}
          className="inline-flex items-baseline gap-1 rounded-[2px] font-semibold hover:underline" style={{ color: s.color }}>
      {text ?? human(label)}
    </Link>
  );
}

export function SentenceView({ rel, style, className = "" }: { rel: RelationshipSpec; style: StyleFn; className?: string }) {
  const s = sentence(rel);
  return (
    <span className={`leading-relaxed text-body ${className}`}>
      {s.parts.map((p, i) => ("type" in p ? <TypeRef key={i} label={p.type} text={p.text} style={style} /> : <span key={i}>{p.text}</span>))}
    </span>
  );
}

export function LinkChip({ rel, style, onClick, active }: {
  rel: RelationshipSpec; style: StyleFn; onClick?: () => void; active?: boolean;
}) {
  const f = style(rel.from);
  const t = style(rel.to);
  return (
    <button onClick={onClick}
            className={`flex w-full items-center gap-1.5 rounded-[3px] px-2 py-1.5 text-left hover:bg-hover ${active ? "bg-accent-soft shadow-[inset_2px_0_0] shadow-accent" : ""}`}>
      <TypeIcon label={rel.from} color={f.color} icon={f.icon} size={18} />
      <span className="flex min-w-0 flex-1 items-center gap-1">
        <span className="h-px w-2 bg-slate-600" />
        <span className="truncate font-mono text-[11px] text-body">{rel.type}</span>
        <Icon name="arrowRight" size={11} className="shrink-0 text-slate-500" />
      </span>
      <TypeIcon label={rel.to} color={t.color} icon={t.icon} size={18} />
      <span className="ml-1 w-8 shrink-0 text-right font-mono text-[10px] text-faint">{CARD_SHORT[rel.cardinality] ?? ""}</span>
    </button>
  );
}

export const relKey = (r: RelationshipSpec) => `${r.type}:${r.from}->${r.to}`;

export function TypeInspector({ type, spec, counts, style, onOpen, onSelectLink }: {
  type: TypeSpec; spec: OntologySpec; counts: { nodes: Record<string, number>; edges: Record<string, number> };
  style: StyleFn; onOpen: () => void; onSelectLink: (r: RelationshipSpec) => void;
}) {
  const s = style(type.label);
  const out = spec.relationships.filter((r) => r.from === type.label);
  const inc = spec.relationships.filter((r) => r.to === type.label && r.from !== type.label);
  const indexed = new Set(spec.indexes.filter((i) => i.label === type.label).map((i) => i.property));
  return (
    <div className="flex flex-col">
      <div className="flex items-start gap-3 border-b border-line p-3">
        <TypeIcon label={type.label} color={s.color} icon={s.icon} size={36} />
        <div className="min-w-0 flex-1">
          <div className="eyebrow">Object type</div>
          <div className="truncate text-[15px] font-semibold text-ink">{human(type.label)}</div>
          <div className="font-mono text-[11px] text-faint">{type.label}</div>
        </div>
        <Btn small kind="primary" icon="external" onClick={onOpen}>Open</Btn>
      </div>
      <div className="flex flex-col gap-3 p-3">
        <p className="text-[12.5px] leading-relaxed text-body">{type.description || <span className="text-faint">No description.</span>}</p>
        <div className="grid grid-cols-3 gap-2">
          <MiniStat label="Objects" value={(counts.nodes[type.label] ?? 0).toLocaleString()} />
          <MiniStat label="Properties" value={type.properties.length} />
          <MiniStat label="Link types" value={out.length + inc.length} />
        </div>
        <KeyValue rows={[
          ["Title property", <span className="font-mono">{type.display?.title_property || "name"}</span>],
          ["ID pattern", <span className="font-mono">{type.id_pattern}</span>],
          ...(type.tags.length ? [["Tags", <span className="flex flex-wrap gap-1">{type.tags.map((t) => <Tag key={t}>{t}</Tag>)}</span>] as [string, ReactNode]] : []),
        ]} />
        {(out.length > 0 || inc.length > 0) && (
          <div>
            <div className="eyebrow mb-1.5">How it connects</div>
            <ul className="flex flex-col gap-1.5">
              {[...out, ...inc].map((r) => (
                <li key={relKey(r)} className="flex gap-2 text-[12px]">
                  <button onClick={() => onSelectLink(r)} title="Inspect this link type"
                          className="mt-0.5 h-fit shrink-0 rounded-[2px] border border-line-strong bg-raised px-1 font-mono text-[10px] text-muted hover:border-accent hover:text-ink">
                    {r.type}
                  </button>
                  <SentenceView rel={r} style={style} />
                </li>
              ))}
            </ul>
          </div>
        )}
        <div>
          <div className="eyebrow mb-1.5">Properties</div>
          <ul className="divide-y divide-line rounded-[3px] border border-line">
            {type.properties.map((p) => (
              <li key={p.name} className="px-2 py-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-[11.5px] text-ink">{p.name}</span>
                  {p.required && <span className="text-[10px] text-rose-300" title="required">*</span>}
                  {indexed.has(p.name) && <span title="indexed"><Icon name="key" size={11} className="text-amber-300" /></span>}
                  <span className="ml-auto font-mono text-[10.5px] text-faint">{p.type}{p.unit ? ` · ${p.unit}` : ""}</span>
                </div>
                {p.description && <div className="mt-0.5 text-[11.5px] text-muted">{p.description}</div>}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export function LinkInspector({ rel, counts, style, onClose }: {
  rel: RelationshipSpec; counts: { edges: Record<string, number> }; style: StyleFn; onClose?: () => void;
}) {
  const f = style(rel.from);
  const t = style(rel.to);
  return (
    <div className="flex flex-col">
      <div className="border-b border-line p-3">
        <div className="flex items-center justify-between">
          <div className="eyebrow">Link type</div>
          {onClose && <Btn small kind="minimal" icon="close" onClick={onClose} />}
        </div>
        <div className="mt-2 flex items-center gap-2">
          <Link to={`/ontology/types/${encodeURIComponent(rel.from)}`} className="flex items-center gap-1.5 text-[12px] font-medium text-ink hover:underline">
            <TypeIcon label={rel.from} color={f.color} icon={f.icon} size={22} />{human(rel.from)}
          </Link>
          <span className="flex flex-1 items-center">
            <span className="h-px flex-1 bg-slate-600" />
            <span className="mx-1 rounded-[3px] border border-sky-800 bg-accent-soft px-1.5 py-0.5 font-mono text-[11px] text-sky-200">{rel.type}</span>
            <span className="h-px flex-1 bg-slate-600" />
            <Icon name="chevronRight" size={12} className="-ml-1 text-slate-500" />
          </span>
          <Link to={`/ontology/types/${encodeURIComponent(rel.to)}`} className="flex items-center gap-1.5 text-[12px] font-medium text-ink hover:underline">
            <TypeIcon label={rel.to} color={t.color} icon={t.icon} size={22} />{human(rel.to)}
          </Link>
        </div>
      </div>
      <div className="flex flex-col gap-3 p-3">
        <div className="rounded-[3px] border border-line bg-sunken p-2.5 text-[13px]">
          <SentenceView rel={rel} style={style} />
        </div>
        {rel.description && <p className="text-[12.5px] leading-relaxed text-body">{rel.description}</p>}
        <KeyValue rows={[
          ["Cardinality", <span className="flex items-center gap-2">{CARD_LABEL[rel.cardinality] ?? rel.cardinality}<Tag mono>{CARD_SHORT[rel.cardinality] ?? "?"}</Tag></span>],
          ["Links loaded", <span className="tabular-nums">{(counts.edges[rel.type] ?? 0).toLocaleString()}</span>],
          ["Direction", <span>{human(rel.from)} → {human(rel.to)}{rel.from === rel.to ? " (self-link)" : ""}</span>],
        ]} />
        {rel.properties.length > 0 && (
          <div>
            <div className="eyebrow mb-1.5">Properties on the link</div>
            <ul className="divide-y divide-line rounded-[3px] border border-line">
              {rel.properties.map((p) => (
                <li key={p.name} className="px-2 py-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11.5px] text-ink">{p.name}</span>
                    <span className="ml-auto font-mono text-[10.5px] text-faint">{p.type}{p.unit ? ` · ${p.unit}` : ""}</span>
                  </div>
                  {p.description && <div className="mt-0.5 text-[11.5px] text-muted">{p.description}</div>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-[3px] border border-line bg-sunken px-2 py-1.5">
      <div className="text-[10px] uppercase tracking-wide text-faint">{label}</div>
      <div className="text-[15px] font-semibold tabular-nums text-ink">{value}</div>
    </div>
  );
}
