// A per-tenant ontology has labels we cannot know in advance, so a label's colour is derived from its name:
// stable across reloads, distinct enough to read, and overridden by the spec's own `display.color` when the
// ontology agent chose one.

const PALETTE = [
  "#38bdf8", // sky
  "#fb923c", // orange
  "#a3e635", // lime
  "#c084fc", // purple
  "#f472b6", // pink
  "#2dd4bf", // teal
  "#facc15", // yellow
  "#818cf8", // indigo
  "#f87171", // red
  "#4ade80", // green
  "#fdba74", // amber
  "#67e8f9", // cyan
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
  interviewer: "bg-sky-600",
  data_agent: "bg-amber-600",
  ontologist: "bg-violet-600",
  expert_generator: "bg-emerald-600",
  synthesize: "bg-fuchsia-700",
  attachments: "bg-slate-600",
  user: "bg-slate-700",
  ripple: "bg-slate-600",
};

export const agentColor = (agent: string): string => AGENT_COLORS[agent] ?? "bg-slate-700";

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
  synthetic: "bg-fuchsia-800",
};
