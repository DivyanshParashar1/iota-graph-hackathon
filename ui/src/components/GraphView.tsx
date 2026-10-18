import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { ForceGraphMethods, LinkObject, NodeObject } from "react-force-graph-2d";
import { colorFor } from "./colors";
import { Icon, drawIcon, iconFor } from "./icons";

// The graph canvas for both the ontology (object types as nodes, link types as edges) and the instance graph.
// Drawn the way Palantir's graph tools draw it: an icon in a ring of the type's colour, the name on a pill
// below, and every edge carrying its relationship name (and, on the schema, its cardinality) mid-way.

export interface ViewNode {
  id: string;
  /** The type. Decides the colour and icon. */
  label: string;
  /** The node's own name: drawn on the instance graph, where every node of a type shares its label. */
  title: string;
  color?: string;
  icon?: string;
  /** Radius multiplier, 1 = default. */
  size?: number;
  /** A small second line under the name (e.g. "128 objects"). */
  sub?: string;
}

export interface ViewLink {
  source: string;
  target: string;
  type: string;
  /** Drawn next to the name, e.g. "1:N". */
  badge?: string;
  /** An id for selecting the link (the ontology inspector selects link types). */
  key?: string;
}

type N = ViewNode;
type L = { type: string; badge?: string; key?: string; curvature?: number };

const C = {
  bg: "#111418",
  grid: "rgba(64,72,84,0.22)",
  ring: "#1c2127",
  edge: "#5f6b7c",
  edgeHot: "#abb3bf",
  edgeDim: "rgba(64,72,84,0.35)",
  edgeDense: "rgba(115,128,145,0.28)",
  text: "#e5e8eb",
  textDim: "#5f6b7c",
  pill: "rgba(17,20,24,0.88)",
  pillLine: "#404854",
  select: "#4c90f0",
  linkText: "#abb3bf",
};

interface Props {
  nodes: ViewNode[];
  links: ViewLink[];
  /** Fixed height in px; omit to fill the parent's height. */
  height?: number;
  highlight?: Set<string>;
  selectedId?: string | null;
  selectedLink?: string | null;
  onSelect?: (n: ViewNode) => void;
  onSelectLink?: (l: ViewLink) => void;
  onOpen?: (n: ViewNode) => void;
  onBackground?: () => void;
  /** Which text goes under a node: its type (schema) or its own name (instances). */
  labelWith?: "label" | "title";
  /** Draw relationship names on the edges (default: on). */
  linkLabels?: boolean;
  /** Base node radius in graph units. */
  nodeRadius?: number;
  /** Force tuning: more negative spreads nodes further apart. */
  charge?: number;
  linkDistance?: number;
  toolbar?: boolean;
  emptyText?: string;
}

function trunc(s: string, n: number) {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

export default function GraphView({
  nodes, links, height, highlight, selectedId, selectedLink, onSelect, onSelectLink, onOpen, onBackground,
  labelWith = "label", linkLabels = true, nodeRadius = 9, charge = -260, linkDistance = 90, toolbar = true,
  emptyText = "Nothing to draw yet",
}: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const fg = useRef<ForceGraphMethods<NodeObject<N>, LinkObject<N, L>> | undefined>(undefined);
  const [size, setSize] = useState({ w: 800, h: height ?? 480 });
  const [hover, setHover] = useState<string | null>(null);
  const [showLabels, setShowLabels] = useState(true);
  const [showLinkLabels, setShowLinkLabels] = useState(linkLabels);
  const [frozen, setFrozen] = useState(false);
  const lastClick = useRef<{ id: string; t: number } | null>(null);
  const fitted = useRef(false);
  const prev = useRef<Map<string, NodeObject<N>>>(new Map());

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const measure = () => setSize({ w: el.clientWidth, h: height ?? Math.max(240, el.clientHeight) });
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    measure();
    return () => ro.disconnect();
  }, [height, nodes.length > 0]);

  // Parallel edges between the same two nodes fan out; a self link becomes a loop.
  const data = useMemo(() => {
    const pairCount = new Map<string, number>();
    const pairSeen = new Map<string, number>();
    for (const l of links) {
      const k = [l.source, l.target].sort().join("|");
      pairCount.set(k, (pairCount.get(k) ?? 0) + 1);
    }
    const ls = links.map((l) => {
      const k = [l.source, l.target].sort().join("|");
      const n = pairCount.get(k) ?? 1;
      const i = pairSeen.get(k) ?? 0;
      pairSeen.set(k, i + 1);
      let curvature = 0;
      if (l.source === l.target) curvature = 0.7 + i * 0.25;
      else if (n > 1) {
        const dir = l.source < l.target ? 1 : -1;
        curvature = dir * (i - (n - 1) / 2) * 0.35 || 0.18 * dir;
      }
      return { ...l, curvature };
    });
    // Keep the positions of nodes already on screen, and drop new ones next to a neighbour that is, so a
    // search-around grows the picture instead of re-shuffling it.
    const old = prev.current;
    const placed = new Map<string, NodeObject<N>>();
    const ns = nodes.map((n) => {
      const o = old.get(n.id);
      const v: NodeObject<N> = { ...n };
      if (o && o.x !== undefined) {
        v.x = o.x;
        v.y = o.y;
        if (o.fx !== undefined) {
          v.fx = o.fx;
          v.fy = o.fy;
        }
      }
      placed.set(n.id, v);
      return v;
    });
    for (const l of links) {
      for (const [a, b] of [[l.source, l.target], [l.target, l.source]]) {
        const na = placed.get(a);
        const nb = placed.get(b);
        if (na && nb && na.x === undefined && nb.x !== undefined) {
          const ang = Math.random() * Math.PI * 2;
          na.x = nb.x + Math.cos(ang) * 30;
          na.y = (nb.y ?? 0) + Math.sin(ang) * 30;
        }
      }
    }
    prev.current = placed;
    return { nodes: ns, links: ls };
  }, [nodes, links]);

  const neighbours = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const l of links) {
      if (!m.has(l.source)) m.set(l.source, new Set());
      if (!m.has(l.target)) m.set(l.target, new Set());
      m.get(l.source)!.add(l.target);
      m.get(l.target)!.add(l.source);
    }
    return m;
  }, [links]);

  useEffect(() => {
    const g = fg.current;
    if (!g) return;
    const ch = g.d3Force("charge") as unknown as { strength?: (v: number) => void } | undefined;
    ch?.strength?.(charge);
    const lk = g.d3Force("link") as unknown as { distance?: (v: number) => void } | undefined;
    lk?.distance?.(linkDistance);
    g.d3ReheatSimulation();
    setFrozen(false);
    fitted.current = false;
    // Fit a few times while the layout expands, until the user takes over (wheel, drag).
    const ts = [500, 1500, 3200].map((ms) => setTimeout(() => !fitted.current && g.zoomToFit(400, 60), ms));
    return () => ts.forEach(clearTimeout);
  }, [data, charge, linkDistance]);

  const focus = hover ?? selectedId ?? null;
  const isHot = useCallback((id: string) => {
    if (highlight && !highlight.has(id)) return false;
    if (!focus) return true;
    return id === focus || !!neighbours.get(focus)?.has(id);
  }, [highlight, focus, neighbours]);

  const endId = (x: unknown) => (typeof x === "object" && x !== null ? String((x as { id: string }).id) : String(x));
  const linkHot = (l: LinkObject<N, L>) => {
    const s = endId(l.source);
    const t = endId(l.target);
    if (highlight && (!highlight.has(s) || !highlight.has(t))) return false;
    if (!focus) return true;
    return s === focus || t === focus;
  };

  const radius = (n: N) => nodeRadius * (n.size ?? 1);
  const dense = links.length > 200;

  const toggleFreeze = () => {
    const g = fg.current;
    if (!g) return;
    if (frozen) {
      for (const n of data.nodes as NodeObject<N>[]) {
        n.fx = undefined;
        n.fy = undefined;
      }
      g.d3ReheatSimulation();
    } else {
      for (const n of data.nodes as NodeObject<N>[]) {
        n.fx = n.x;
        n.fy = n.y;
      }
    }
    setFrozen(!frozen);
  };

  if (!nodes.length) {
    return (
      <div className="flex h-full min-h-40 flex-col items-center justify-center gap-2 bg-canvas text-[12px] text-faint">
        <Icon name="graph" size={28} className="text-slate-600" strokeWidth={1.3} />
        {emptyText}
      </div>
    );
  }

  return (
    <div ref={wrap} onWheel={() => { fitted.current = true; }} className="relative h-full w-full overflow-hidden bg-canvas"
         style={{ backgroundImage: `radial-gradient(${C.grid} 1px, transparent 1px)`, backgroundSize: "22px 22px" }}>
      <ForceGraph2D<N, L>
        ref={fg}
        graphData={data}
        width={size.w}
        height={size.h}
        backgroundColor="rgba(0,0,0,0)"
        nodeRelSize={1}
        nodeVal={(n) => radius(n) ** 2}
        nodeLabel={(n) => `<div style="font:12px Inter,system-ui;padding:2px 4px"><b>${n.title || n.label}</b>${n.title && n.title !== n.label ? `<br/><span style="opacity:.7">${n.label}</span>` : ""}</div>`}
        warmupTicks={nodes.length <= 400 ? 120 : 40}
        cooldownTicks={220}
        d3VelocityDecay={0.32}
        linkCurvature={(l) => l.curvature ?? 0}
        linkColor={(l) => (selectedLink && l.key === selectedLink ? C.select : linkHot(l) ? (focus ? C.edgeHot : dense ? C.edgeDense : C.edge) : C.edgeDim)}
        linkWidth={(l) => (selectedLink && l.key === selectedLink ? 2.2 : focus && linkHot(l) ? 1.6 : dense ? 0.6 : 1)}
        linkDirectionalArrowLength={dense ? 2.5 : 5}
        linkDirectionalArrowRelPos={1}
        linkDirectionalArrowColor={(l) => (selectedLink && l.key === selectedLink ? C.select : linkHot(l) ? C.edgeHot : C.edgeDim)}
        linkHoverPrecision={6}
        onLinkClick={(l) => onSelectLink?.({ source: endId(l.source), target: endId(l.target), type: l.type, badge: l.badge, key: l.key })}
        onNodeHover={(n) => setHover(n ? String(n.id) : null)}
        onBackgroundClick={() => onBackground?.()}
        onNodeClick={(n) => {
          const v: ViewNode = { id: String(n.id), label: n.label, title: n.title, color: n.color, icon: n.icon };
          const now = Date.now();
          if (lastClick.current && lastClick.current.id === v.id && now - lastClick.current.t < 350) {
            onOpen?.(v);
            lastClick.current = null;
          } else {
            lastClick.current = { id: v.id, t: now };
            onSelect?.(v);
          }
        }}
        onNodeDrag={() => {
          fitted.current = true;
        }}
        onNodeDragEnd={(n) => {
          if (frozen) {
            n.fx = n.x;
            n.fy = n.y;
          }
        }}
        nodeCanvasObjectMode={() => "replace"}
        nodeCanvasObject={(n, ctx, scale) => {
          if (n.x === undefined || n.y === undefined) return;
          const id = String(n.id);
          const hot = isHot(id);
          const r = radius(n);
          const color = colorFor(n.label, n.color);
          ctx.globalAlpha = hot ? 1 : 0.22;
          if (id === selectedId) {
            ctx.beginPath();
            ctx.arc(n.x, n.y, r + 4.5, 0, 2 * Math.PI);
            ctx.fillStyle = "rgba(76,144,240,0.22)";
            ctx.fill();
            ctx.lineWidth = 1.5;
            ctx.strokeStyle = C.select;
            ctx.stroke();
          }
          ctx.beginPath();
          ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();
          ctx.lineWidth = Math.max(1, 1.6 / Math.sqrt(scale));
          ctx.strokeStyle = "rgba(17,20,24,0.9)";
          ctx.stroke();
          drawIcon(ctx, iconFor(n.icon, n.label), n.x, n.y, r * 1.18, "#111418", 2.1);

          const zoomedIn = nodes.length <= 30 || r * scale >= 13;
          if (showLabels && (zoomedIn || id === focus || id === selectedId)) {
            const text = trunc(labelWith === "title" ? n.title || n.label : n.label, 30);
            const fs = Math.max(11 / scale, 2.5);
            ctx.font = `600 ${fs}px Inter, "Segoe UI", system-ui, sans-serif`;
            const w = ctx.measureText(text).width;
            const pad = 3 / scale + 1;
            const y = n.y + r + 3 + 2 / scale;
            const h = fs + pad * 1.4 + (n.sub ? fs * 0.95 : 0);
            ctx.fillStyle = C.pill;
            ctx.strokeStyle = C.pillLine;
            ctx.lineWidth = 0.6 / scale;
            ctx.beginPath();
            ctx.roundRect(n.x - w / 2 - pad, y, w + pad * 2, h, 2 / scale + 0.5);
            ctx.fill();
            ctx.stroke();
            ctx.fillStyle = hot ? C.text : C.textDim;
            ctx.textAlign = "center";
            ctx.textBaseline = "top";
            ctx.fillText(text, n.x, y + pad * 0.7);
            if (n.sub) {
              ctx.font = `${fs * 0.82}px Inter, "Segoe UI", system-ui, sans-serif`;
              ctx.fillStyle = C.textDim;
              ctx.fillText(n.sub, n.x, y + pad * 0.7 + fs * 1.05);
            }
          }
          ctx.globalAlpha = 1;
        }}
        linkCanvasObjectMode={() => "after"}
        linkCanvasObject={(l, ctx, scale) => {
          if (!showLinkLabels) return;
          const s = l.source as NodeObject<N>;
          const t = l.target as NodeObject<N>;
          if (typeof s !== "object" || typeof t !== "object" || s.x === undefined || t.x === undefined) return;
          const hot = linkHot(l);
          const selected = !!selectedLink && l.key === selectedLink;
          if (!selected && (!hot || (data.links.length > 30 && scale < 1.6))) return;
          let x: number;
          let y: number;
          if (s === t) {
            const rr = radius(s) * (1 + (l.curvature ?? 0.7) * 2.3);
            x = s.x!;
            y = s.y! - rr - 6;
          } else {
            const dx = t.x! - s.x!;
            const dy = t.y! - s.y!;
            const len = Math.hypot(dx, dy);
            const a = Math.atan2(dy, dx);
            const d = len * (l.curvature ?? 0) * 0.5;
            x = (s.x! + t.x!) / 2 + d * Math.cos(a - Math.PI / 2);
            y = (s.y! + t.y!) / 2 + d * Math.sin(a - Math.PI / 2);
          }
          const fs = Math.max(9.5 / scale, 2);
          const label = l.badge ? `${l.type}  ${l.badge}` : l.type;
          ctx.font = `500 ${fs}px "JetBrains Mono", "Cascadia Mono", Consolas, monospace`;
          const w = ctx.measureText(label).width;
          const pad = 2.5 / scale + 0.5;
          ctx.fillStyle = selected ? "rgba(24,74,144,0.95)" : "rgba(28,33,39,0.94)";
          ctx.strokeStyle = selected ? C.select : C.pillLine;
          ctx.lineWidth = 0.6 / scale;
          ctx.beginPath();
          ctx.roundRect(x - w / 2 - pad, y - fs / 2 - pad, w + pad * 2, fs + pad * 2, 2 / scale);
          ctx.fill();
          ctx.stroke();
          ctx.fillStyle = selected ? "#ffffff" : C.linkText;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(label, x, y + 0.3 / scale);
        }}
      />
      {toolbar && (
        <div className="absolute right-2 top-2 flex flex-col overflow-hidden rounded-[3px] border border-line-strong bg-panel/95 shadow-lg shadow-black/30">
          <ToolBtn icon="fit" title="Fit to screen" onClick={() => fg.current?.zoomToFit(400, 50)} />
          <ToolBtn icon="tag" title={showLabels ? "Hide node labels" : "Show node labels"} active={showLabels} onClick={() => setShowLabels(!showLabels)} />
          <ToolBtn icon="link" title={showLinkLabels ? "Hide link names" : "Show link names"} active={showLinkLabels} onClick={() => setShowLinkLabels(!showLinkLabels)} />
          <ToolBtn icon="pin" title={frozen ? "Unfreeze layout" : "Freeze layout"} active={frozen} onClick={toggleFreeze} />
        </div>
      )}
    </div>
  );
}

function ToolBtn({ icon, title, onClick, active }: { icon: string; title: string; onClick: () => void; active?: boolean }) {
  return (
    <button title={title} aria-label={title} onClick={onClick}
            className={`flex h-7 w-7 items-center justify-center border-b border-line last:border-b-0 hover:bg-hover ${active ? "text-accent" : "text-muted"}`}>
      <Icon name={icon} size={14} />
    </button>
  );
}
