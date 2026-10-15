export const LABEL_COLORS: Record<string, string> = {
  Disruption: "#ef4444",
  Incident: "#f97316",
  Port: "#38bdf8",
  Lane: "#818cf8",
  Order: "#facc15",
  Customer: "#a3e635",
  Product: "#f472b6",
  Part: "#c084fc",
  Supplier: "#fb923c",
  Plant: "#2dd4bf",
  Action: "#22c55e",
  Employee: "#e2e8f0",
  Team: "#94a3b8",
  Document: "#fde68a",
  Chunk: "#fef3c7",
  Contract: "#fcd34d",
  Decision: "#f0abfc",
  ChatMessage: "#cbd5e1",
};

export const AGENT_COLORS: Record<string, string> = {
  sentinel: "bg-rose-600",
  analyst: "bg-sky-600",
  planner: "bg-emerald-600",
  comms: "bg-amber-500",
  orchestrator: "bg-slate-600",
};

export const colorFor = (label: string): string => LABEL_COLORS[label] ?? "#64748b";
