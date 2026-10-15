import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Ontology as O, SubGraph } from "../api";
import GraphView from "../components/GraphView";
import { Card, Chip } from "../components/ui";

export default function Ontology({ tenant }: { tenant: string }) {
  const [o, setO] = useState<O | null>(null);
  useEffect(() => {
    api.ontology().then(setO);
  }, [tenant]);

  const graph: SubGraph = useMemo(() => {
    if (!o) return { nodes: [], links: [] };
    const labels = new Set(o.labels.map((l) => l.label));
    const links = o.relationships.flatMap((r) =>
      r.from.split("|").flatMap((a) =>
        r.to
          .split("|")
          .filter((b) => labels.has(a) && labels.has(b))
          .map((b) => ({ source: a, target: b, type: `${r.type} (${r.count})` })),
      ),
    );
    return { nodes: o.labels.map((l) => ({ id: l.label, label: l.label, name: `${l.count} nodes` })), links };
  }, [o]);

  return (
    <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
      <Card
        title="Ontology (object types and link types)"
        right={o && <span className="text-xs text-slate-400">{o.totals.nodes.toLocaleString()} nodes, {o.totals.edges.toLocaleString()} edges, {o.totals.memory_nodes} memory nodes</span>}
      >
        <GraphView graph={graph} height={600} showLabels />
      </Card>
      <Card title="Counts">
        <div className="max-h-[640px] overflow-y-auto">
          <table className="w-full text-xs">
            <tbody>
              {o?.labels.map((l) => (
                <tr key={l.label} className="border-t border-slate-800 align-top">
                  <td className="py-1">
                    <Chip>{l.label}</Chip> <span className="text-slate-500">{l.graph}</span>
                    <div className="text-slate-400">{l.description}</div>
                  </td>
                  <td className="text-right tabular-nums">{l.count.toLocaleString()}</td>
                </tr>
              ))}
              {o?.relationships.map((r) => (
                <tr key={`${r.type}-${r.from}-${r.to}`} className="border-t border-slate-800">
                  <td className="py-1 font-mono">
                    ({r.from})-[:{r.type}]-&gt;({r.to})
                  </td>
                  <td className="text-right tabular-nums">{r.count.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
