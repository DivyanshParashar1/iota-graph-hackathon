import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { ForceGraphMethods, LinkObject, NodeObject } from "react-force-graph-2d";
import { colorFor } from "./colors";

export interface ViewNode {
  id: string;
  /** The type. Decides the colour, and is what the ontology diagram draws. */
  label: string;
  /** The node's own name, drawn on the instance graph where every node of a type shares its label. */
  title: string;
  color?: string;
  size?: number;
}

export interface ViewLink {
  source: string;
  target: string;
  type: string;
}

type N = ViewNode;
type L = { type: string };

interface Props {
  nodes: ViewNode[];
  links: ViewLink[];
  highlight?: Set<string>;
  height?: number;
  onSelect?: (n: ViewNode) => void;
  showLabels?: boolean;
  /** Which text to draw under a node: its type (the ontology diagram) or its name (the instance graph). */
  labelWith?: "label" | "title";
}

/** The force graph, used for both the ontology diagram (types as nodes) and the instance graph. */
export default function GraphView({ nodes, links, highlight, height = 520, onSelect, showLabels = false,
                                   labelWith = "label" }: Props) {
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
    () => ({ nodes: nodes.map((n) => ({ ...n })), links: links.map((l) => ({ ...l })) }),
    [nodes, links],
  );

  useEffect(() => {
    const t = setTimeout(() => fg.current?.zoomToFit(400, 40), 600);
    return () => clearTimeout(t);
  }, [data]);

  const isHot = (id: string | number | undefined) => (highlight ? highlight.has(String(id)) : true);
  const endId = (x: string | number | NodeObject<N> | undefined) =>
    typeof x === "object" && x !== null ? String(x.id) : String(x);

  if (!nodes.length) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg border border-slate-800 bg-slate-950 text-xs text-slate-500">
        nothing to draw yet
      </div>
    );
  }

  return (
    <div ref={wrap} className="w-full rounded-lg border border-slate-800 bg-slate-950">
      <ForceGraph2D<N, L>
        ref={fg}
        graphData={data}
        width={width}
        height={height}
        backgroundColor="#020617"
        nodeLabel={(n) => `${n.label}${n.title && n.title !== n.label ? `: ${n.title}` : ""}`}
        nodeColor={(n) => (isHot(n.id) ? colorFor(n.label, n.color) : "#334155")}
        nodeVal={(n) => n.size ?? 3}
        linkColor={(l) => (isHot(endId(l.source)) && isHot(endId(l.target)) ? "#64748b" : "#1e293b")}
        linkDirectionalArrowLength={3.5}
        linkDirectionalArrowRelPos={1}
        linkLabel={(l) => l.type}
        linkCurvature={0.08}
        onNodeClick={(n) => onSelect?.({ id: String(n.id), label: n.label, title: n.title })}
        nodeRelSize={5}
        nodeCanvasObjectMode={() => (showLabels ? "after" : undefined)}
        nodeCanvasObject={(n, ctx, scale) => {
          if (!showLabels || n.x === undefined || n.y === undefined) return;
          // nodeVal is an area, so the drawn radius is nodeRelSize * sqrt(val): put the label below it
          // rather than at a fixed offset, or a big type's label lands inside its own circle.
          const r = 5 * Math.sqrt(n.size ?? 3);
          const text = labelWith === "title" ? n.title || n.label : n.label;
          ctx.font = `${Math.max(11 / scale, 3)}px ui-sans-serif, system-ui`;
          ctx.fillStyle = isHot(n.id) ? "#e2e8f0" : "#475569";
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          ctx.fillText(text.length > 28 ? `${text.slice(0, 27)}…` : text, n.x, n.y + r + 2);
        }}
      />
    </div>
  );
}
