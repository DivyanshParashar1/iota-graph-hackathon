import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { ObjectHit } from "../api";
import { useOntology } from "../useOntology";
import { Icon } from "./icons";
import { Kbd, TypeIcon } from "./ui";

interface Item {
  key: string;
  group: string;
  title: string;
  sub?: string;
  icon: ReactNode;
  to: string;
}

const PAGES: [string, string, string][] = [
  ["Overview", "/", "layers"],
  ["My workspace", "/workspace", "users"],
  ["Onboarding", "/onboarding", "chat"],
  ["Ontology", "/ontology", "schema"],
  ["Object explorer", "/objects", "table"],
  ["Graph", "/graph", "graph"],
  ["Experts", "/experts", "experts"],
  ["Incidents", "/incidents", "incident"],
];

/** Global search (press / or Ctrl+K): pages, object types and objects of every approved type. */
export default function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const nav = useNavigate();
  const { spec, style } = useOntology();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<ObjectHit[]>([]);
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      setQ("");
      setHits([]);
      setActive(0);
    }
  }, [open]);

  useEffect(() => {
    const term = q.trim();
    if (!open || term.length < 2) {
      setHits([]);
      return;
    }
    setBusy(true);
    const t = setTimeout(() => {
      api.searchObjects(term, 4).then((r) => setHits(r.hits)).catch(() => setHits([])).finally(() => setBusy(false));
    }, 160);
    return () => clearTimeout(t);
  }, [q, open]);

  const items = useMemo<Item[]>(() => {
    const term = q.trim().toLowerCase();
    const out: Item[] = [];
    for (const [title, to, icon] of PAGES) {
      if (!term || title.toLowerCase().includes(term)) {
        out.push({ key: `p:${to}`, group: "Go to", title, to, icon: <Icon name={icon} size={15} className="text-muted" /> });
      }
    }
    for (const t of spec?.types ?? []) {
      if (!term || t.label.toLowerCase().includes(term) || t.description.toLowerCase().includes(term)) {
        const s = style(t.label);
        out.push({
          key: `t:${t.label}`, group: "Object types", title: t.label, sub: t.description,
          to: `/ontology/types/${encodeURIComponent(t.label)}`,
          icon: <TypeIcon label={t.label} color={s.color} icon={s.icon} size={20} />,
        });
      }
    }
    for (const h of hits) {
      const s = style(h.label);
      out.push({
        key: `o:${h.label}:${h.id}`, group: "Objects", title: h.title, sub: `${h.label} · ${h.id}`,
        to: `/objects/${encodeURIComponent(h.label)}/${encodeURIComponent(h.id)}`,
        icon: <TypeIcon label={h.label} color={s.color} icon={s.icon} size={20} />,
      });
    }
    return term ? out : out.slice(0, 14);
  }, [q, spec, hits, style]);

  useEffect(() => setActive(0), [q, hits.length]);

  useEffect(() => {
    listRef.current?.querySelector(`[data-idx="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  const go = (it: Item | undefined) => {
    if (!it) return;
    nav(it.to);
    onClose();
  };

  let lastGroup = "";
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/55 pt-[12vh] backdrop-blur-[1px]" onMouseDown={onClose}>
      <div
        className="w-[640px] max-w-[calc(100vw-32px)] overflow-hidden rounded-[6px] border border-line-strong bg-panel shadow-2xl shadow-black/60"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex h-12 items-center gap-2 border-b border-line px-3">
          <Icon name="search" size={16} className="text-faint" />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
              else if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
              else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
              else if (e.key === "Enter") go(items[active]);
            }}
            placeholder="Search objects, types and pages…"
            className="h-full flex-1 bg-transparent text-[14px] text-ink outline-none placeholder:text-faint"
          />
          {busy && <span className="text-[11px] text-faint">searching…</span>}
          <Kbd>Esc</Kbd>
        </div>
        <div ref={listRef} className="max-h-[52vh] overflow-auto py-1">
          {items.length === 0 && (
            <div className="px-4 py-8 text-center text-[12px] text-faint">
              {q.trim().length < 2 ? "Type to search" : busy ? "Searching…" : `Nothing matches "${q}"`}
            </div>
          )}
          {items.map((it, i) => {
            const header = it.group !== lastGroup ? it.group : null;
            lastGroup = it.group;
            return (
              <div key={it.key}>
                {header && <div className="eyebrow px-3 pb-1 pt-2">{header}</div>}
                <button
                  data-idx={i}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => go(it)}
                  className={`flex w-full items-center gap-2.5 px-3 py-1.5 text-left ${i === active ? "bg-accent-soft" : ""}`}
                >
                  {it.icon}
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] text-ink">{it.title}</span>
                    {it.sub && <span className="block truncate text-[11px] text-faint">{it.sub}</span>}
                  </span>
                  {i === active && <Icon name="arrowRight" size={14} className="text-accent" />}
                </button>
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-3 border-t border-line px-3 py-1.5 text-[11px] text-faint">
          <span className="flex items-center gap-1"><Kbd>↑</Kbd><Kbd>↓</Kbd> navigate</span>
          <span className="flex items-center gap-1"><Kbd>Enter</Kbd> open</span>
        </div>
      </div>
    </div>
  );
}
