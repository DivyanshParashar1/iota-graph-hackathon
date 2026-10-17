import type { ReactNode } from "react";

export function Card({ title, children, right }: { title?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      {(title || right) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          {title && <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">{title}</h2>}
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="rounded-md bg-slate-950/70 p-3">
      <div className="text-xs uppercase text-slate-500">{label}</div>
      <div className="text-xl font-semibold tabular-nums text-slate-100">{value}</div>
      {sub && <div className="text-xs text-slate-400">{sub}</div>}
    </div>
  );
}

export function Btn({
  children,
  onClick,
  kind = "default",
  disabled,
}: {
  children: ReactNode;
  onClick?: () => void;
  kind?: "default" | "primary" | "danger" | "ghost";
  disabled?: boolean;
}) {
  const k = {
    default: "bg-slate-700 hover:bg-slate-600",
    primary: "bg-emerald-600 hover:bg-emerald-500",
    danger: "bg-rose-700 hover:bg-rose-600",
    ghost: "bg-transparent hover:bg-slate-800 border border-slate-700",
  }[kind];
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`rounded px-2.5 py-1 text-xs font-medium text-white disabled:opacity-40 ${k}`}
    >
      {children}
    </button>
  );
}

export function Chip({ children, color = "bg-slate-800", onClick, title }: { children: ReactNode; color?: string; onClick?: () => void; title?: string }) {
  return (
    <span
      title={title}
      onClick={onClick}
      className={`inline-block rounded px-1.5 py-0.5 font-mono text-[11px] text-slate-200 ${color} ${onClick ? "cursor-pointer hover:ring-1 hover:ring-slate-400" : ""}`}
    >
      {children}
    </span>
  );
}

export function ErrorLine({ error }: { error: string | null }) {
  return error ? <div className="rounded bg-rose-950 p-2 text-xs text-rose-200">{error}</div> : null;
}

export const statusColor = (s: string) =>
  ({ proposed: "bg-amber-700", approved: "bg-sky-700", executed: "bg-emerald-700", rejected: "bg-rose-800", undone: "bg-slate-600", open: "bg-orange-700", closed: "bg-slate-600",
     auto_approved: "bg-emerald-700", pending: "bg-amber-700", not_selected: "bg-slate-700", superseded: "bg-slate-600",
     awaiting_approval: "bg-amber-700", resolved: "bg-slate-600", failed: "bg-rose-800", received: "bg-violet-800",
     consulting: "bg-violet-700", analysing: "bg-violet-700", planning: "bg-violet-700", deciding: "bg-violet-700",
     critical: "bg-rose-700", high: "bg-orange-700", medium: "bg-amber-700", low: "bg-slate-600" } as Record<string, string>)[s] ??
  "bg-slate-700";
