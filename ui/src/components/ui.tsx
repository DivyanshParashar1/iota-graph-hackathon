import { useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { colorFor } from "./colors";
import { Icon, iconFor } from "./icons";

// Ripple's primitives, in the Blueprint idiom: hairline borders, 3px radii, uppercase section headers, one blue
// for primary actions. Colours come from the tokens in index.css.

export function Card({ title, children, right, className = "", pad = true }: {
  title?: ReactNode; children: ReactNode; right?: ReactNode; className?: string; pad?: boolean;
}) {
  return (
    <section className={`rounded-[4px] border border-line bg-panel ${className}`}>
      {(title || right) && (
        <div className="flex min-h-9 items-center justify-between gap-2 border-b border-line px-3 py-1.5">
          {title && <h2 className="eyebrow">{title}</h2>}
          {right}
        </div>
      )}
      <div className={pad ? "p-3" : ""}>{children}</div>
    </section>
  );
}

/** A full-height pane with a header strip, used for the workspace columns. */
export function Panel({ title, icon, count, right, children, className = "", bodyClassName = "" }: {
  title: ReactNode; icon?: string; count?: ReactNode; right?: ReactNode; children: ReactNode; className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={`flex min-h-0 flex-col overflow-hidden rounded-[4px] border border-line bg-panel ${className}`}>
      <header className="flex h-9 shrink-0 items-center gap-2 border-b border-line px-3">
        {icon && <Icon name={icon} size={14} className="text-faint" />}
        <h2 className="eyebrow !text-muted">{title}</h2>
        {count !== undefined && (
          <span className="rounded-full bg-raised px-1.5 text-[10.5px] tabular-nums text-muted">{count}</span>
        )}
        <div className="ml-auto flex items-center gap-1.5">{right}</div>
      </header>
      <div className={`min-h-0 flex-1 overflow-auto ${bodyClassName}`}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string }) {
  return (
    <div className="rounded-[4px] border border-line bg-panel px-3 py-2">
      <div className="eyebrow">{label}</div>
      <div className={`mt-0.5 text-[20px] font-semibold tabular-nums leading-tight ${tone ?? "text-ink"}`}>{value}</div>
      {sub && <div className="text-[11px] text-faint">{sub}</div>}
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
    default: "border-line-strong bg-raised text-body hover:bg-hover hover:text-ink",
    primary: "border-sky-500 bg-sky-600 text-white hover:bg-sky-500",
    success: "border-emerald-500 bg-emerald-600 text-white hover:bg-emerald-500",
    danger: "border-rose-600 bg-rose-700 text-white hover:bg-rose-600",
    ghost: "border-line-strong bg-transparent text-body hover:bg-hover hover:text-ink",
    minimal: "border-transparent bg-transparent text-muted hover:bg-hover hover:text-ink",
  }[kind];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-[3px] border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${small ? "h-6 px-1.5 text-[11px]" : "h-7 px-2.5 text-[12px]"} ${k}`}
    >
      {icon && <Icon name={icon} size={small ? 12 : 14} />}
      {children}
    </button>
  );
}

export function Chip({ children, color = "bg-raised", onClick, title }: {
  children: ReactNode; color?: string; onClick?: () => void; title?: string;
}) {
  return (
    <span
      title={title}
      onClick={onClick}
      className={`inline-flex items-center gap-1 rounded-[3px] px-1.5 py-px font-mono text-[11px] text-slate-100 ${color} ${onClick ? "cursor-pointer hover:ring-1 hover:ring-slate-400" : ""}`}
    >
      {children}
    </span>
  );
}

type Intent = "none" | "primary" | "success" | "warning" | "danger" | "info";

/** A Blueprint "minimal" tag: tinted background, coloured text. */
export function Tag({ children, intent = "none", icon, mono, title, onClick, className = "" }: {
  children: ReactNode; intent?: Intent; icon?: string; mono?: boolean; title?: string; onClick?: () => void;
  className?: string;
}) {
  const k = {
    none: "bg-raised text-body border-line-strong",
    primary: "bg-accent-soft text-sky-300 border-sky-800",
    info: "bg-violet-900/40 text-violet-300 border-violet-800",
    success: "bg-success-soft text-emerald-300 border-emerald-800",
    warning: "bg-warning-soft text-amber-300 border-amber-800",
    danger: "bg-danger-soft text-rose-300 border-rose-800",
  }[intent];
  return (
    <span
      title={title}
      onClick={onClick}
      className={`inline-flex h-5 items-center gap-1 whitespace-nowrap rounded-[3px] border px-1.5 text-[11px] leading-none ${mono ? "font-mono" : "font-medium"} ${k} ${onClick ? "cursor-pointer hover:brightness-125" : ""} ${className}`}
    >
      {icon && <Icon name={icon} size={11} />}
      {children}
    </span>
  );
}

export function Callout({ intent = "primary", title, children, icon }: {
  intent?: "primary" | "warning" | "danger" | "success"; title?: ReactNode; children?: ReactNode; icon?: string;
}) {
  const k = {
    primary: ["border-sky-700 bg-accent-soft", "text-sky-300", "info"],
    warning: ["border-amber-700 bg-warning-soft", "text-amber-300", "alert"],
    danger: ["border-rose-700 bg-danger-soft", "text-rose-300", "alert"],
    success: ["border-emerald-700 bg-success-soft", "text-emerald-300", "check"],
  }[intent];
  return (
    <div className={`flex gap-2 rounded-[3px] border-l-[3px] px-3 py-2 ${k[0]}`}>
      <Icon name={icon ?? k[2]} size={15} className={`mt-px ${k[1]}`} />
      <div className="min-w-0 text-[12px] text-body">
        {title && <div className={`font-semibold ${k[1]}`}>{title}</div>}
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
    <div className={`flex h-9 shrink-0 items-end gap-4 border-b border-line px-3 ${className}`} role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={`-mb-px flex h-full items-center gap-1.5 border-b-2 text-[12px] font-medium transition-colors ${value === t.id ? "border-accent text-ink" : "border-transparent text-muted hover:text-ink"}`}
        >
          {t.icon && <Icon name={t.icon} size={13} />}
          {t.label}
          {t.count !== undefined && (
            <span className="rounded-full bg-raised px-1.5 text-[10.5px] tabular-nums text-muted">{t.count}</span>
          )}
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
      <Icon name={icon} size={30} className="text-slate-600" strokeWidth={1.3} />
      <div className="text-[13px] font-semibold text-muted">{title}</div>
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
  return (
    <kbd className="rounded-[3px] border border-line-strong bg-raised px-1 font-mono text-[10px] text-muted">
      {children}
    </kbd>
  );
}

/** An object type's badge: its icon on its colour. */
export function TypeIcon({ label, icon = "", color = "", size = 22 }: {
  label: string; icon?: string; color?: string; size?: number;
}) {
  const c = colorFor(label, color);
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-[4px]"
      style={{ width: size, height: size, background: `${c}26`, color: c, boxShadow: `inset 0 0 0 1px ${c}55` }}
    >
      <Icon name={iconFor(icon, label)} size={Math.round(size * 0.64)} strokeWidth={1.8} />
    </span>
  );
}

/** A type name as a clickable pill that opens its object type page. */
export function TypeTag({ label, icon = "", color = "", link = true }: {
  label: string; icon?: string; color?: string; link?: boolean;
}) {
  const inner = (
    <span className="inline-flex items-center gap-1.5 rounded-[3px] border border-line-strong bg-raised py-0.5 pl-0.5 pr-1.5 text-[12px] font-medium text-ink hover:border-slate-500">
      <TypeIcon label={label} icon={icon} color={color} size={17} />
      {label}
    </span>
  );
  return link ? <Link to={`/ontology/types/${encodeURIComponent(label)}`}>{inner}</Link> : inner;
}

export function Breadcrumbs({ items }: { items: { label: ReactNode; to?: string }[] }) {
  return (
    <nav className="flex items-center gap-1 text-[12px]">
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-1">
          {i > 0 && <Icon name="chevronRight" size={12} className="text-slate-600" />}
          {it.to ? <Link to={it.to} className="text-muted hover:text-ink">{it.label}</Link>
            : <span className="text-ink">{it.label}</span>}
        </span>
      ))}
    </nav>
  );
}

/** A page header: breadcrumbs, a title with an optional icon, and actions on the right. */
export function PageHeader({ title, icon, crumbs, subtitle, right, children }: {
  title: ReactNode; icon?: ReactNode; crumbs?: { label: ReactNode; to?: string }[]; subtitle?: ReactNode;
  right?: ReactNode; children?: ReactNode;
}) {
  return (
    <div className="shrink-0 border-b border-line bg-panel px-5 pb-3 pt-2.5">
      {crumbs && <Breadcrumbs items={crumbs} />}
      <div className="mt-1.5 flex flex-wrap items-center gap-3">
        {icon}
        <div className="min-w-0">
          <h1 className="truncate text-[17px] font-semibold leading-tight text-ink">{title}</h1>
          {subtitle && <div className="mt-0.5 text-[12px] text-muted">{subtitle}</div>}
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">{right}</div>
      </div>
      {children}
    </div>
  );
}

/** A thin horizontal meter, 0..1. */
export function Meter({ value, tone = "bg-accent", className = "" }: { value: number; tone?: string; className?: string }) {
  return (
    <div className={`h-1.5 w-full overflow-hidden rounded-full bg-raised ${className}`}>
      <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
    </div>
  );
}

export function Collapsible({ title, children, defaultOpen = true, right }: {
  title: ReactNode; children: ReactNode; defaultOpen?: boolean; right?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-line last:border-b-0">
      <div className="flex h-8 items-center gap-1.5 px-3">
        <button onClick={() => setOpen(!open)} className="flex flex-1 items-center gap-1.5 text-left">
          <Icon name={open ? "chevronDown" : "chevronRight"} size={12} className="text-faint" />
          <span className="eyebrow !text-muted">{title}</span>
        </button>
        {right}
      </div>
      {open && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}

export const statusColor = (s: string) =>
  ({ proposed: "bg-amber-700", approved: "bg-sky-700", executed: "bg-emerald-700", rejected: "bg-rose-800", undone: "bg-slate-600", open: "bg-amber-700", closed: "bg-slate-600",
     auto_approved: "bg-emerald-700", pending: "bg-amber-700", not_selected: "bg-slate-700", superseded: "bg-slate-600",
     awaiting_approval: "bg-amber-700", resolved: "bg-slate-600", failed: "bg-rose-800", received: "bg-violet-700",
     consulting: "bg-violet-700", analysing: "bg-violet-700", planning: "bg-violet-700", deciding: "bg-violet-700",
     draft: "bg-amber-700", live: "bg-emerald-700", retired: "bg-slate-600",
     critical: "bg-rose-700", high: "bg-amber-600", medium: "bg-amber-800", low: "bg-slate-600" } as Record<string, string>)[s] ??
  "bg-slate-700";

export const statusIntent = (s: string): Intent =>
  (({ approved: "primary", executed: "success", auto_approved: "success", live: "success", resolved: "none",
      rejected: "danger", failed: "danger", critical: "danger", high: "warning", proposed: "warning",
      pending: "warning", awaiting_approval: "warning", draft: "warning", medium: "warning", received: "info",
      consulting: "info", analysing: "info", planning: "info", deciding: "info", open: "warning" } as Record<string, Intent>)[s] ?? "none");

// Dense data tables: sticky uppercase header, hairline rows.
export function TableShell({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-auto rounded-[4px] border border-line bg-panel">
      <table className="w-full border-collapse text-[12.5px]">{children}</table>
    </div>
  );
}

export function Th({ children, right }: { children?: ReactNode; right?: boolean }) {
  return (
    <th className={`sticky top-0 z-10 h-8 border-b border-line bg-raised px-3 text-[10.5px] font-semibold uppercase tracking-[0.06em] text-faint ${right ? "text-right" : "text-left"}`}>
      {children}
    </th>
  );
}

export function Td({ children, right, className = "" }: { children?: ReactNode; right?: boolean; className?: string }) {
  return <td className={`px-3 py-2 ${right ? "text-right tabular-nums" : ""} ${className}`}>{children}</td>;
}
