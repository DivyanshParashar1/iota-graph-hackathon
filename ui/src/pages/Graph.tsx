import { useEffect, useState } from "react";
import { api } from "../api";
import type { GraphSample, Provenance } from "../api";
import GraphView from "../components/GraphView";
import { Btn, Card, Chip, ErrorLine } from "../components/ui";

/** The loaded instance graph, and "where did this come from?" for any node in it. */
export default function Graph() {
  const [sample, setSample] = useState<GraphSample>({ nodes: [], edges: [] });
  const [counts, setCounts] = useState<{ nodes: Record<string, number>; edges: Record<string, number> }>({
    nodes: {},
    edges: {},
  });
  const [selected, setSelected] = useState<{ id: string; label: string } | null>(null);
  const [prov, setProv] = useState<Provenance | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.graph(500).then(setSample).catch((e) => setError(String(e)));
    api
      .tenant()
      .then((t) => setCounts(t.counts))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!selected) return setProv(null);
    api.provenance(selected.id).then(setProv).catch(() => setProv(null));
  }, [selected]);

  return (
    <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
      <Card
        title="Your graph"
        right={
          <span className="text-[11px] text-slate-500">
            {sample.nodes.length} of {Object.values(counts.nodes).reduce((a, b) => a + b, 0)} nodes
          </span>
        }
      >
        <ErrorLine error={error} />
        <GraphView
          nodes={sample.nodes.map((n) => ({ id: n.id, label: n.label, title: n.title }))}
          links={sample.edges.map((e) => ({ source: e.source, target: e.target, type: e.type }))}
          height={560}
          onSelect={(n) => setSelected({ id: n.id, label: n.label })}
        />
      </Card>
      <div className="flex flex-col gap-4">
        <Card title="Counts">
          <table className="w-full text-xs">
            <tbody>
              {Object.entries(counts.nodes).map(([label, n]) => (
                <tr key={label} className="border-t border-slate-800">
                  <td className="py-1 text-slate-300">{label}</td>
                  <td className="py-1 text-right tabular-nums text-slate-400">{n}</td>
                </tr>
              ))}
              {Object.entries(counts.edges).map(([rel, n]) => (
                <tr key={rel} className="border-t border-slate-800">
                  <td className="py-1 font-mono text-[11px] text-slate-400">{rel}</td>
                  <td className="py-1 text-right tabular-nums text-slate-500">{n}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card
          title="Where did this come from?"
          right={selected ? <Btn kind="ghost" onClick={() => setSelected(null)}>clear</Btn> : undefined}
        >
          {!selected && <p className="text-xs text-slate-500">Click a node in the graph.</p>}
          {selected && (
            <div className="flex flex-col gap-2 text-xs">
              <div className="flex items-center gap-2">
                <Chip color="bg-sky-900">{selected.label}</Chip>
                <span className="font-mono text-slate-300">{selected.id}</span>
              </div>
              {!prov?.sources.length && <p className="text-slate-500">no provenance recorded for this node</p>}
              {prov?.sources.map((s) => (
                <div key={s.source_id} className="rounded bg-slate-950 p-2">
                  <div className="flex items-center gap-1">
                    <Chip color="bg-slate-800">{s.source_label.replace("_", "")}</Chip>
                    <span className="text-slate-400">{s.source_ref}</span>
                    <Chip color={s.confidence === "synthetic" ? "bg-fuchsia-800" : "bg-slate-800"}>
                      {s.confidence}
                    </Chip>
                  </div>
                  <div className="mt-1 break-words font-mono text-[11px] text-slate-500">{s.source_value}</div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
