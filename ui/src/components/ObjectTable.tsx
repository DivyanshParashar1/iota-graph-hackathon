import { useEffect, useState } from "react";
import { api } from "../api";
import type { ObjectPage, TypeSpec } from "../api";
import { Icon } from "./icons";
import { Btn, EmptyState, SearchInput, Td, Th } from "./ui";

const PAGE = 50;

export function formatValue(v: unknown, unit = "", type = ""): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") {
    if (type === "currency" || unit === "USD") {
      return v >= 1e6 ? `$${(v / 1e6).toFixed(v >= 1e7 ? 0 : 1)}M` : v >= 1e4 ? `$${(v / 1e3).toFixed(0)}k`
        : `$${v.toLocaleString(undefined, Number.isInteger(v) ? {} : { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    if (type === "percent" || unit === "%") return `${v}%`;
    const s = Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return unit ? `${s} ${unit}` : s;
  }
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}

/** One type's objects as a dense, searchable, paged table. */
export default function ObjectTable({ type, selectedId, onOpen, maxColumns = 6, className = "" }: {
  type: TypeSpec; selectedId?: string | null; onOpen: (id: string) => void; maxColumns?: number; className?: string;
}) {
  const [q, setQ] = useState("");
  const [skip, setSkip] = useState(0);
  const [page, setPage] = useState<ObjectPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setSkip(0);
    setQ("");
  }, [type.label]);

  useEffect(() => {
    setBusy(true);
    const t = setTimeout(() => {
      api.objects(type.label, { q, limit: PAGE, skip })
        .then((p) => { setPage(p); setError(null); })
        .catch((e: Error) => setError(e.message))
        .finally(() => setBusy(false));
    }, q ? 180 : 0);
    return () => clearTimeout(t);
  }, [type.label, q, skip]);

  const titleProp = page?.title_property ?? type.display?.title_property ?? "name";
  const cols = type.properties.filter((p) => p.name !== titleProp).slice(0, maxColumns);
  const total = page?.total ?? 0;
  const rows = page?.objects ?? [];

  return (
    <div className={`flex min-h-0 flex-col ${className}`}>
      <div className="flex shrink-0 items-center gap-2 border-b border-line px-3 py-2">
        <SearchInput value={q} onChange={(v) => { setQ(v); setSkip(0); }} placeholder={`Search ${type.label} by ${titleProp} or id`} className="w-72 max-w-full" />
        {busy && <span className="text-[11px] text-faint">loading…</span>}
        <span className="ml-auto text-[11.5px] tabular-nums text-faint">
          {q ? `${rows.length} match${rows.length === 1 ? "" : "es"}` : total ? `${skip + 1}–${Math.min(skip + PAGE, total)} of ${total.toLocaleString()}` : ""}
        </span>
        {!q && total > PAGE && (
          <span className="flex gap-1">
            <Btn small kind="ghost" icon="chevronLeft" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - PAGE))} title="Previous page" />
            <Btn small kind="ghost" icon="chevronRight" disabled={skip + PAGE >= total} onClick={() => setSkip(skip + PAGE)} title="Next page" />
          </span>
        )}
      </div>
      {error ? (
        <div className="p-3 text-[12px] text-rose-300">{error}</div>
      ) : !busy && rows.length === 0 ? (
        <EmptyState icon="table" title={q ? "No matches" : "No objects loaded"}>
          {q ? `Nothing of type ${type.label} matches "${q}".` : "Approve the ontology to load data into this type."}
        </EmptyState>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto">
          <table className="w-full border-collapse whitespace-nowrap text-[12.5px]">
            <thead>
              <tr>
                <Th>{titleProp}</Th>
                <Th>id</Th>
                {cols.map((c) => <Th key={c.name} right={["integer", "float", "currency", "percent"].includes(c.type)}>{c.name}</Th>)}
                <Th />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} onClick={() => onOpen(r.id)}
                    className={`group cursor-pointer border-t border-line ${selectedId === r.id ? "bg-accent-soft" : "hover:bg-hover"}`}>
                  <Td className="font-medium text-ink">{r.title}</Td>
                  <Td className="font-mono text-[11px] text-faint">{r.id}</Td>
                  {cols.map((c) => {
                    const v = r.properties[c.name];
                    const num = ["integer", "float", "currency", "percent"].includes(c.type);
                    return (
                      <Td key={c.name} right={num} className={c.type === "enum" ? "" : "text-body"}>
                        {c.type === "enum" && v ? (
                          <span className="rounded-[3px] bg-raised px-1.5 py-px text-[11px] text-body">{String(v)}</span>
                        ) : formatValue(v, c.unit, c.type)}
                      </Td>
                    );
                  })}
                  <Td><Icon name="chevronRight" size={13} className="text-slate-600 group-hover:text-muted" /></Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
