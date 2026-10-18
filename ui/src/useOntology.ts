import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import type { OntologySpec, OntologyView, TypeSpec } from "./api";
import { paletteFor } from "./components/colors";
import { iconFor } from "./components/icons";

// One fetch of /api/ontology shared by every page that needs to draw a type (its colour, icon, title
// property), so a Supplier is the same green with the same glyph on the ontology, the explorer and the graph.

let cache: OntologyView | null = null;
let inflight: Promise<OntologyView> | null = null;
const listeners = new Set<(v: OntologyView | null) => void>();

function load(force = false): Promise<OntologyView> {
  if (!force && cache) return Promise.resolve(cache);
  if (!force && inflight) return inflight;
  inflight = api.ontology().then((v) => {
    cache = v;
    inflight = null;
    listeners.forEach((l) => l(v));
    return v;
  }).catch((e) => {
    inflight = null;
    throw e;
  });
  return inflight;
}

export function setOntologyCache(v: OntologyView) {
  cache = v;
  listeners.forEach((l) => l(v));
}

export interface TypeStyle {
  color: string;
  icon: string;
}

export function styleMap(spec: OntologySpec | null | undefined): Record<string, TypeStyle> {
  const types = spec?.types ?? [];
  const pal = paletteFor(types.map((t) => t.label));
  const out: Record<string, TypeStyle> = {};
  for (const t of types) out[t.label] = { color: t.display?.color || pal[t.label], icon: iconFor(t.display?.icon, t.label) };
  return out;
}

export function useOntology() {
  const [view, setView] = useState<OntologyView | null>(cache);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!cache);

  useEffect(() => {
    listeners.add(setView);
    load().then(setView).catch((e: Error) => setError(e.message)).finally(() => setLoading(false));
    return () => {
      listeners.delete(setView);
    };
  }, []);

  const reload = useCallback(() => load(true).then(setView).catch((e: Error) => setError(e.message)), []);
  const spec = view?.spec ?? null;
  const styles = useMemo(() => styleMap(spec), [spec]);
  const typeMap = useMemo(() => Object.fromEntries((spec?.types ?? []).map((t) => [t.label, t])) as Record<string, TypeSpec>, [spec]);
  const style = useCallback((label: string): TypeStyle => styles[label] ?? { color: "#8F99A8", icon: iconFor("", label) }, [styles]);

  return { view, spec, error, loading, reload, styles, style, typeMap };
}
