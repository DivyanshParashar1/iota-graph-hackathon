import { useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { colorFor } from "./colors";
import { Icon, iconFor } from "./icons";

// Ripple's primitives, in the Gotham idiom of the landing page: hairlines instead of filled boxes, large light type
// over small uppercase captions, near-white for emphasis, colour only where it carries meaning (a type, an intent).
// Tokens live in index.css.

/** A count in brackets, Gotham-style: [12]. */
export function Count({ n }: { n: ReactNode }) {
  return <span className="font-mono text-[11px] tabular-nums text-faint">[{n}]</span>;
}

/** A section caption with an optional count, and actions on the right. */
export function Caption({ title, count, right, className = "" }: {
  title: ReactNode; count?: ReactNode; right?: ReactNode; className?: string;
}) {
  return (
    <div className={`flex min-h-9 items-center gap-2 ${className}`}>
      <h2 className="micro text-muted">{title}</h2>
      {count !== undefined && <Count n={count} />}
      <div className="ml-auto flex items-center gap-2">{right}</div>
    </div>
  );
}

export function Card({ title, children, right, className = "", pad = true }: {
  title?: ReactNode; children: ReactNode; right?: ReactNode; className?: string; pad?: boolean;
}) {
  return (
    <section className={`rise border border-line ${className}`}>
      {(title || right) && <Caption title={title} right={right} className="border-b border-line px-3" />}
      <div className={pad ? "p-3" : ""}>{children}</div>
    </section>
  );
}

/** A full-height pane with a caption strip, used for the workspace columns. */
export function Panel({ title, icon, count, right, children, className = "", bodyClassName = "" }: {
  title: ReactNode; icon?: string; count?: ReactNode; right?: ReactNode; children: ReactNode; className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={`flex min-h-0 flex-col overflow-hidden border border-line ${className}`}>
      <header className="flex h-9 shrink-0 items-center gap-2 border-b border-line px-3">
        {icon && <Icon name={icon} size={13} className="text-faint" />}
        <h2 className="micro text-muted">{title}</h2>
        {count !== undefined && <Count n={count} />}
        <div className="ml-auto flex items-center gap-1.5">{right}</div>
      </header>
      <div className={`min-h-0 flex-1 overflow-auto ${bodyClassName}`}>{children}</div>
    </section>
  );
}

/** A figure: caption, a large light number, a quiet note. Sits on a hairline, so a row of them reads as a strip. */
export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string }) {
  return (
    <div className="rise border-l border-line px-4 py-1">
      <div className="eyebrow">{label}</div>
      <div className={`mt-1 text-[34px] font-light leading-none tabular-nums tracking-tight ${tone ?? "text-ink"}`}>{value}</div>
      {sub && <div className="mt-1.5 text-[11.5px] text-faint">{sub}</div>}
    </div>
  );
}

type BtnKind = "default" | "primary" | "danger" | "ghost" | "success" | "minimal";

export function Btn({ children, onClick, kind = "default", disabled, icon, title, small, type = "button" }: {
  children?: ReactNode;
  onClick?: () => void;
  kind?: BtnKind;
  disabled?: boolean;
  icon?: string;
  title?: string;
  small?: boolean;
  type?: "button" | "submit";
}) {
  const k = {
    default: "border-white/25 text-ink hover:border-white/60 hover:bg-white/[0.04]",
    primary: "border-ink bg-ink text-black hover:bg-white",
    success: "border-emerald-400/60 text-emerald-300 hover:bg-emerald-400/10",
    danger: "border-rose-400/50 text-rose-300 hover:bg-rose-400/10",
    ghost: "border-line-strong text-body hover:border-white/40 hover:text-ink",
    minimal: "border-transparent text-muted hover:text-ink",
  }[kind];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap border transition-colors disabled:pointer-events-none disabled:opacity-35 ${small ? "h-6 px-2 text-[11.5px]" : "h-8 px-3.5 text-[12.5px]"} ${k}`}
    >
      {icon && <Icon name={icon} size={small ? 12 : 13} />}
      {children}
    </button>
  );
}

/** A deep fill class (bg-amber-900) as its bright mark (bg-amber-400); the classes it yields are all used in DOT. */
const brighten = (c: string) =>
  c.replace(/bg-(\w+)-[5-9]00(\/\d+)?/, (_, hue: string) => (hue === "slate" ? "bg-slate-500" : `bg-${hue}-400`));

/** A short label with a colour bar; `color` is a background class. */
export function Chip({ children, color = "bg-slate-500", onClick, title }: {
  children: ReactNode; color?: string; onClick?: () => void; title?: string;
}) {
  color = brighten(color);
  return (
    <span
      title={title}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 border border-line-strong py-px pr-1.5 font-mono text-[10.5px] text-body ${onClick ? "cursor-pointer hover:border-white/40" : ""}`}
    >
      <span className={`w-[3px] self-stretch ${color}`} />
      {children}
    </span>
  );
}

type Intent = "none" | "primary" | "success" | "warning" | "danger" | "info";

const DOT: Record<Intent, string> = {
  none: "bg-slate-500", primary: "bg-sky-400", info: "bg-violet-400", success: "bg-emerald-400",
  warning: "bg-amber-400", danger: "bg-rose-400",
};
const TEXT: Record<Intent, string> = {
  none: "text-muted", primary: "text-sky-300", info: "text-violet-300", success: "text-emerald-300",
  warning: "text-amber-300", danger: "text-rose-300",
};

/** A status as a square dot and an uppercase caption: no fill, no box. */
export function Tag({ children, intent = "none", icon, mono, title, onClick, className = "" }: {
  children: ReactNode; intent?: Intent; icon?: string; mono?: boolean; title?: string; onClick?: () => void;
  className?: string;
}) {
  return (
    <span
      title={title}
      onClick={onClick}
      className={`inline-flex h-5 items-center gap-1.5 whitespace-nowrap leading-none ${mono ? "font-mono text-[11px] text-muted" : `micro ${TEXT[intent]}`} ${onClick ? "cursor-pointer hover:text-ink" : ""} ${className}`}
    >
      {icon ? <Icon name={icon} size={11} /> : !mono && <span className={`h-1.5 w-1.5 shrink-0 ${DOT[intent]}`} />}
      {children}
    </span>
  );
}

export function Callout({ intent = "primary", title, children, icon }: {
  intent?: "primary" | "warning" | "danger" | "success"; title?: ReactNode; children?: ReactNode; icon?: string;
}) {
  const k = {
    primary: ["border-sky-400", "text-sky-300", "info"],
    warning: ["border-amber-400", "text-amber-300", "alert"],
    danger: ["border-rose-400", "text-rose-300", "alert"],
    success: ["border-emerald-400", "text-emerald-300", "check"],
  }[intent];
  return (
    <div className={`flex gap-2.5 border-l py-1 pl-3 pr-2 ${k[0]}`}>
      <Icon name={icon ?? k[2]} size={14} className={`mt-px shrink-0 ${k[1]}`} />
      <div className="min-w-0 text-[12.5px] text-body">
        {title && <div className={`micro mb-0.5 ${k[1]}`}>{title}</div>}
        {children}
      </div>
    </div>
  );
}

export function ErrorLine({ error }: { error: string | null }) {
  return error ? <Callout intent="danger">{error}</Callout> : null;
}

export function Tabs<T extends string>({ tabs, value, onChange, className = "" }: {
  tabs: { id: T; label: ReactNode; icon?: string; count?: number }[]; value: T; onChange: (t: T) => void;
  className?: string;
}) {
  return (
    <div className={`flex h-10 shrink-0 items-end gap-5 border-b border-line px-4 ${className}`} role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={`micro -mb-px flex h-full items-center gap-1.5 border-b transition-colors ${value === t.id ? "border-ink text-ink" : "border-transparent text-faint hover:text-body"}`}
        >
          {t.label}
          {t.count !== undefined && <Count n={t.count} />}
        </button>
      ))}
    </div>
  );
}

/** Two-column label/value grid. */
export function KeyValue({ rows, className = "" }: { rows: [ReactNode, ReactNode][]; className?: string }) {
  return (
    <dl className={`grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-4 gap-y-1.5 text-[12px] ${className}`}>
      {rows.map(([k, v], i) => (
        <div key={i} className="contents">
          <dt className="text-faint">{k}</dt>
          <dd className="min-w-0 break-words text-body">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function EmptyState({ icon = "cube", title, children, action }: {
  icon?: string; title: ReactNode; children?: ReactNode; action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <Icon name={icon} size={22} className="text-slate-500" strokeWidth={1.3} />
      <div className="text-[15px] font-light text-body">{title}</div>
      {children && <div className="max-w-sm text-[12px] text-faint">{children}</div>}
      {action}
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder = "Search…", className = "", autoFocus }: {
  value: string; onChange: (v: string) => void; placeholder?: string; className?: string; autoFocus?: boolean;
}) {
  return (
    <label className={`relative flex items-center ${className}`}>
      <Icon name="search" size={13} className="pointer-events-none absolute left-2 text-faint" />
      <input
        autoFocus={autoFocus}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="field h-7 w-full pl-7"
      />
    </label>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="border border-line-strong px-1 font-mono text-[10px] text-faint">{children}</kbd>;
}

/** An object type's mark: its icon, drawn in its colour. */
export function TypeIcon({ label, icon = "", color = "", size = 22 }: {
  label: string; icon?: string; color?: string; size?: number;
}) {
  const c = colorFor(label, color);
  return (
    <span className="inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size, color: c }}>
      <Icon name={iconFor(icon, label)} size={Math.round(size * 0.72)} strokeWidth={1.6} />
    </span>
  );
}

/** A type name with its mark; opens its object type page. */
export function TypeTag({ label, icon = "", color = "", link = true }: {
  label: string; icon?: string; color?: string; link?: boolean;
}) {
  const inner = (
    <span className="inline-flex items-center gap-1 text-[12px] text-ink hover:underline hover:decoration-white/40 hover:underline-offset-4">
      <TypeIcon label={label} icon={icon} color={color} size={16} />
      {label}
    </span>
  );
  return link ? <Link to={`/ontology/types/${encodeURIComponent(label)}`}>{inner}</Link> : inner;
}

export function Breadcrumbs({ items }: { items: { label: ReactNode; to?: string }[] }) {
  return (
    <nav className="micro flex items-center gap-1.5">
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <span className="text-slate-600">/</span>}
          {it.to ? <Link to={it.to} className="text-faint hover:text-ink">{it.label}</Link>
            : <span className="text-muted">{it.label}</span>}
        </span>
      ))}
    </nav>
  );
}

/** A page header: a caption trail, a large light title, a quiet subtitle, and actions on the right. */
export function PageHeader({ title, icon, crumbs, subtitle, right, children }: {
  title: ReactNode; icon?: ReactNode; crumbs?: { label: ReactNode; to?: string }[]; subtitle?: ReactNode;
  right?: ReactNode; children?: ReactNode;
}) {
  return (
    <div className="shrink-0 border-b border-line px-6 pb-5 pt-4">
      {crumbs && <Breadcrumbs items={crumbs} />}
      <div className="mt-3 flex flex-wrap items-end gap-x-6 gap-y-3">
        {icon}
        <div className="rise min-w-0">
          <h1 className="truncate text-[30px] font-light leading-none tracking-[-0.02em] text-ink">{title}</h1>
          {subtitle && <div className="mt-2 text-[12.5px] text-muted">{subtitle}</div>}
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">{right}</div>
      </div>
      {children}
    </div>
  );
}

/** A hairline meter, 0..1. */
export function Meter({ value, tone = "bg-ink", className = "" }: { value: number; tone?: string; className?: string }) {
  return (
    <div className={`h-[2px] w-full overflow-hidden bg-line ${className}`}>
      <div className={`h-full transition-[width] duration-500 ${tone}`} style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
    </div>
  );
}

export function Collapsible({ title, children, defaultOpen = true, right }: {
  title: ReactNode; children: ReactNode; defaultOpen?: boolean; right?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-line last:border-b-0">
      <div className="flex h-9 items-center gap-1.5 px-3">
        <button onClick={() => setOpen(!open)} className="flex flex-1 items-center gap-1.5 text-left">
          <Icon name={open ? "chevronDown" : "chevronRight"} size={12} className="text-faint" />
          <span className="micro text-muted">{title}</span>
        </button>
        {right}
      </div>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}

export const statusColor = (s: string) =>
  ({ proposed: "bg-amber-400", approved: "bg-sky-400", executed: "bg-emerald-400", rejected: "bg-rose-400", undone: "bg-slate-500", open: "bg-amber-400", closed: "bg-slate-500",
     auto_approved: "bg-emerald-400", pending: "bg-amber-400", not_selected: "bg-slate-600", superseded: "bg-slate-500",
     awaiting_approval: "bg-amber-400", resolved: "bg-slate-500", failed: "bg-rose-400", received: "bg-violet-400",
     consulting: "bg-violet-400", analysing: "bg-violet-400", planning: "bg-violet-400", deciding: "bg-violet-400",
     draft: "bg-amber-400", live: "bg-emerald-400", retired: "bg-slate-500",
     critical: "bg-rose-400", high: "bg-amber-400", medium: "bg-amber-500", low: "bg-slate-500" } as Record<string, string>)[s] ??
  "bg-slate-500";

export const statusIntent = (s: string): Intent =>
  (({ approved: "primary", executed: "success", auto_approved: "success", live: "success", resolved: "none",
      rejected: "danger", failed: "danger", critical: "danger", high: "warning", proposed: "warning",
      pending: "warning", awaiting_approval: "warning", draft: "warning", medium: "warning", received: "info",
      consulting: "info", analysing: "info", planning: "info", deciding: "info", open: "warning" } as Record<string, Intent>)[s] ?? "none");

// Dense data tables: sticky caption header, hairline rows.
export function TableShell({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-auto border-y border-line">
      <table className="w-full border-collapse text-[12.5px]">{children}</table>
    </div>
  );
}

export function Th({ children, right }: { children?: ReactNode; right?: boolean }) {
  return (
    <th className={`micro sticky top-0 z-10 h-9 border-b border-line bg-canvas px-3 !font-normal text-faint ${right ? "text-right" : "text-left"}`}>
      {children}
    </th>
  );
}

export function Td({ children, right, className = "" }: { children?: ReactNode; right?: boolean; className?: string }) {
  return <td className={`px-3 py-2 ${right ? "text-right tabular-nums" : ""} ${className}`}>{children}</td>;
}
