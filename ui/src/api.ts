// All API types and calls. The tenant is sent as X-Ripple-Tenant (and ?tenant= for EventSource).

export type Tenant = "dataco" | "nova";

const TENANT_KEY = "ripple.tenant";

export function getTenant(): Tenant {
  try {
    const t = localStorage.getItem(TENANT_KEY);
    return t === "nova" ? "nova" : "dataco";
  } catch {
    return "dataco";
  }
}

export function setTenant(t: Tenant): void {
  try {
    localStorage.setItem(TENANT_KEY, t);
  } catch {
    /* private mode: tenant just won't persist */
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Ripple-Tenant": getTenant(), ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) msg = body.detail;
    } catch {
      /* not json */
    }
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

const get = <T,>(p: string) => req<T>(p);
const post = <T,>(p: string, body?: unknown) => req<T>(p, { method: "POST", body: JSON.stringify(body ?? {}) });

// ------------------------------------------------------------------ types
export type Edge = [string, string, string];

export interface AgentEvent {
  seq: number;
  ts: number;
  incident_id: string;
  agent: string;
  kind: "tool_call" | "tool_result" | "handoff" | "message" | "action" | "done" | "error";
  tool: string | null;
  args: Record<string, unknown>;
  summary: string;
  node_ids: string[];
  edges: Edge[];
  data: Record<string, unknown> | null;
}

export interface Health {
  ok: boolean;
  db_mode: string;
  graphs: string[];
  agent_mode: string;
  default_mode: string;
}

export interface TenantInfo {
  id: Tenant;
  name: string;
  nodes: number;
  edges: number;
  memory_nodes: number;
}

export interface Scenario {
  id: string;
  name: string;
  description: string;
  event: Record<string, unknown>;
}

export interface IncidentRow {
  id: string;
  title: string;
  type: string;
  status: string;
  opened_at: number;
  closed_at: number | null;
  revenue_at_risk: number | null;
  revenue_at_risk_initial: number | null;
  orders_at_risk: number | null;
  customers_affected: number | null;
  mode: string | null;
  outcome: string | null;
}

export interface Target {
  id: string;
  label: string;
  name: string;
  country: string | null;
}

export interface Episode {
  id: string;
  incident_id: string;
  disruption_type: string;
  entity_ids: string[];
  countries: string[];
  actions_taken: string[];
  outcome: string;
  revenue_before: number;
  revenue_after: number;
  summary: string;
  ts: number;
  title: string;
  seeded: boolean;
  playbook_id: string | null;
  playbook: string | null;
  playbook_success_rate: number | null;
}

export interface Playbook {
  id: string;
  disruption_type: string;
  name: string;
  steps: string[];
  uses: number;
  successes: number;
  success_rate: number;
  episodes?: string[];
}

export interface Action {
  id: string;
  type: string;
  status: string;
  summary: string;
  incident_id: string;
  created_at: number;
  executed_at?: number;
  expected_impact?: number;
  params: Record<string, unknown>;
  agent: string | null;
  approved_by?: string | null;
  evidence?: { label: string; id: string; name: string; role: string }[];
}

export interface Handoff {
  src: string;
  dst: string;
  ts: number;
  summary: string;
}

export interface IncidentDetail {
  incident: Record<string, unknown> & {
    id: string;
    title: string;
    status: string;
    type: string;
    revenue_at_risk?: number;
    revenue_at_risk_initial?: number;
    orders_at_risk?: number;
    orders_at_risk_initial?: number;
    customers_affected?: number;
    summary?: string;
    impact_summary?: string;
    mode?: string;
  };
  disruption: Record<string, unknown> & { id: string; type: string; name: string; expected_days?: number };
  targets: Target[];
  actions: Action[];
  handoffs: Handoff[];
  recalled: Episode[];
  playbook: Playbook | null;
  running: boolean;
}

export interface GraphNode {
  id: string;
  label: string;
  name: string;
}

export interface GraphLink {
  source: string;
  target: string;
  type: string;
}

export interface SubGraph {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface Source {
  doc_id: string;
  title: string;
  uri: string;
  chunk_id: string | null;
  snippet: string;
}

export interface Answer {
  answer: string;
  sources: Source[];
  path: string[];
  edges: Edge[];
  intent: string[];
  entities: string[];
  mode: string;
  conversation_id?: string;
}

export interface MapData {
  ports: { id: string; name: string; country: string; lat: number; lon: number; status: string; risk_score: number; disruptions: string[] }[];
  plants: { id: string; name: string; country: string; lat: number; lon: number; port: string }[];
  suppliers: { id: string; name: string; tier: number; country: string; lat: number; lon: number; risk_score: number; status: string; disruptions: string[] }[];
  disruptions: { id: string; type: string; name: string; incident_id: string | null; targets: string[]; n_targets: number }[];
}

export interface Fact {
  id: string;
  subject_id: string;
  predicate: string;
  object: string;
  valid_at: number;
  invalid_at: number | null;
  source: string;
  supersedes: string | null;
}

export interface Ontology {
  labels: { label: string; graph: string; description: string; properties: Record<string, string>; count: number }[];
  relationships: { type: string; from: string; to: string; properties: string; description: string; count: number }[];
  interfaces: { label: string; on: string; description: string }[];
  totals: { nodes: number; edges: number; memory_nodes: number };
}

export interface Person {
  id: string;
  name: string;
  role: string;
  team: string;
}

export interface ApproveResult {
  action_id: string;
  status: string;
  revenue_before: number | null;
  revenue_after: number | null;
}

// ------------------------------------------------------------------ calls
export const api = {
  health: () => get<Health>("/api/health"),
  tenants: () => get<TenantInfo[]>("/api/tenants"),
  scenarios: () => get<Scenario[]>("/api/scenarios"),
  map: () => get<MapData>("/api/map"),
  ontology: () => get<Ontology>("/api/ontology"),
  incidents: () => get<IncidentRow[]>("/api/incidents"),
  incident: (id: string) => get<IncidentDetail>(`/api/incidents/${id}`),
  incidentGraph: (id: string) => get<SubGraph>(`/api/incidents/${id}/graph`),
  trigger: (scenario_id: string, mode: string) =>
    post<{ incident_id: string; mode: string }>("/api/incidents", { scenario_id, mode }),
  close: (id: string) => post<{ data: { episode: { episode_id: string; outcome: string } } }>(`/api/incidents/${id}/close`),
  actions: (status?: string) => get<Action[]>(`/api/actions${status ? `?status=${status}` : ""}`),
  action: (id: string) => get<Action>(`/api/actions/${id}`),
  approve: (id: string) => post<ApproveResult>(`/api/actions/${id}/approve`, { user: "USR-demo", user_name: "Demo user" }),
  reject: (id: string) => post<{ status: string }>(`/api/actions/${id}/reject`, { user: "USR-demo", reason: "rejected in UI" }),
  execute: (id: string) => post<ApproveResult>(`/api/actions/${id}/execute`),
  undo: (id: string) => post<ApproveResult>(`/api/actions/${id}/undo`),
  ask: (question: string, user_id: string, incident_id?: string) =>
    post<Answer>("/api/brain/ask", { question, user_id, incident_id: incident_id || null }),
  ingest: (text: string, author_id: string, channel: string) =>
    post<{ message_id: string; handover?: { supplier_id: string; to: string; from: string[] } }>("/api/brain/ingest", {
      kind: "chat",
      text,
      author_id,
      channel,
    }),
  handoverSample: () => get<{ text: string; author_id: string; channel: string }>("/api/brain/handover-sample"),
  people: () => get<Person[]>("/api/people"),
  episodes: () => get<Episode[]>("/api/memory/episodes"),
  playbooks: () => get<Playbook[]>("/api/memory/playbooks"),
  facts: (history: boolean) => get<Fact[]>(`/api/memory/facts?history=${history}`),
  conversations: () => get<{ user_id: string; id: string; started_at: number; messages: number }[]>("/api/memory/conversations"),
  spof: () => get<{ data: { chokepoints: { id: string; name: string; score: number; downstream_tier1: number; single_sourced_parts_downstream: number }[] } }>("/api/algos/spof?top_k=5"),
};

export function eventsUrl(incidentId: string): string {
  return `/api/incidents/${incidentId}/events?tenant=${getTenant()}`;
}

export const money = (x: number | null | undefined): string =>
  x == null ? "-" : x >= 1e6 ? `$${(x / 1e6).toFixed(2)}M` : x >= 1e3 ? `$${(x / 1e3).toFixed(1)}K` : `$${x.toFixed(0)}`;

export const fmtTime = (ms: number | null | undefined): string => (ms ? new Date(ms).toLocaleString() : "-");
