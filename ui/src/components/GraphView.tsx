import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { ForceGraphMethods, NodeObject, LinkObject } from "react-force-graph-2d";
import type { GraphLink, GraphNode, SubGraph } from "../api";
import { colorFor } from "./colors";

type N = GraphNode;
type L = { type: string };

interface Props {
  graph: SubGraph;
  highlight?: Set<string>;
  height?: number;
  onSelect?: (n: GraphNode) => void;
  showLabels?: boolean;
}

export default function GraphView({ graph, highlight, height = 520, onSelect, showLabels = false }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const fg = useRef<ForceGraphMethods<NodeObject<N>, LinkObject<N, L>> | undefined>(undefined);
  const [width, setWidth] = useState(800);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const data = useMemo(
    () => ({
      nodes: graph.nodes.map((n) => ({ ...n })),
      links: graph.links.map((l: GraphLink) => ({ source: l.source, target: l.target, type: l.type })),
    }),
    [graph],
  );

  useEffect(() => {
    const t = setTimeout(() => fg.current?.zoomToFit(400, 30), 600);
    return () => clearTimeout(t);
  }, [data]);

  const isHot = (id: string | number | undefined) => (highlight ? highlight.has(String(id)) : true);
  const endId = (x: string | number | NodeObject<N> | undefined) =>
    typeof x === "object" && x !== null ? String(x.id) : String(x);

  return (
    <div ref={wrap} className="w-full rounded-lg border border-slate-800 bg-slate-950">
      <ForceGraph2D<N, L>
        ref={fg}
        graphData={data}
        width={width}
        height={height}
        backgroundColor="#020617"
        nodeLabel={(n) => `${n.label}: ${n.name} (${n.id})`}
        nodeColor={(n) => (isHot(n.id) ? colorFor(n.label) : "#334155")}
        nodeVal={(n) => (n.label === "Disruption" || n.label === "Incident" ? 6 : n.label === "Order" ? 1.5 : 3)}
        linkColor={(l) => (isHot(endId(l.source)) && isHot(endId(l.target)) ? "#64748b" : "#1e293b")}
        linkDirectionalArrowLength={3}
        linkDirectionalArrowRelPos={1}
        linkDirectionalParticles={(l) => (isHot(endId(l.source)) && isHot(endId(l.target)) ? 2 : 0)}
        linkDirectionalParticleWidth={2}
        linkLabel={(l) => l.type}
        onNodeClick={(n) => onSelect?.({ id: String(n.id), label: n.label, name: n.name })}
        nodeRelSize={showLabels ? 5 : 3}
        nodeCanvasObjectMode={() => (showLabels ? "after" : undefined)}
        nodeCanvasObject={(n, ctx, scale) => {
          if (!showLabels || n.x === undefined || n.y === undefined) return;
          const fs = Math.max(10 / scale, 2);
          ctx.font = `${fs}px sans-serif`;
          ctx.fillStyle = "#e2e8f0";
          ctx.textAlign = "center";
          ctx.fillText(n.label, n.x, n.y + 12 / Math.sqrt(scale) + fs);
        }}
        cooldownTicks={120}
      />
    </div>
  );
}
