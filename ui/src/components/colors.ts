// A per-tenant ontology has labels we cannot know in advance, so a label's colour is derived from its name:
// stable across reloads, distinct enough to read, and overridden by the spec's own `display.color` when the
// ontology agent chose one.

// Blueprint's extended palette at the weight that reads on a dark canvas.
export const PALETTE = [
  "#5B9BF3", // blue
  "#32A467", // green
  "#EC9A3C", // orange
  "#BD6BBD", // violet
  "#13C9BA", // turquoise
  "#F0B726", // gold
  "#F5498B", // rose
  "#9881F3", // indigo
  "#AF855A", // sepia
  "#B6D94C", // lime
  "#EB6847", // vermilion
  "#68C1EE", // cerulean
];

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export const colorFor = (label: string, override = ""): string =>
  override || PALETTE[hash(label) % PALETTE.length];

/** Colours for a known set of labels, assigned by position so two types never collide.
 *  `colorFor` alone hashes, which is stable but can give two of a tenant's types the same colour. */
export function paletteFor(labels: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  [...new Set(labels)].sort().forEach((label, i) => {
    out[label] = PALETTE[i % PALETTE.length];
  });
  return out;
}

export const AGENT_COLORS: Record<string, string> = {
  interviewer: "bg-sky-400",
  data_agent: "bg-amber-400",
  ontologist: "bg-violet-400",
  expert_generator: "bg-emerald-400",
  synthesize: "bg-violet-400",
  attachments: "bg-slate-500",
  user: "bg-slate-500",
  ripple: "bg-slate-500",
};

export const agentColor = (agent: string): string => AGENT_COLORS[agent] ?? "bg-slate-500";

export const STAGE_LABELS: Record<string, string> = {
  interview: "Interview",
  data: "Data",
  ontology: "Ontology",
  experts: "Experts",
  ready: "Ready",
};

export const CONFIDENCE_COLORS: Record<string, string> = {
  exact: "bg-slate-700",
  ballpark: "bg-amber-800",
  unknown: "bg-slate-800",
  synthetic: "bg-violet-800",
};
