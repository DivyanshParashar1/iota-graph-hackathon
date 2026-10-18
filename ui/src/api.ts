// Every API type and call. The tenant travels in a cookie the server sets on /api/onboarding/start; a header
// is sent too so a browser with several tenants open still hits the right one.

const TENANT_KEY = "ripple.tenant";

export function getTenant(): string {
  try {
    return localStorage.getItem(TENANT_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setTenant(t: string): void {
  try {
    if (t) localStorage.setItem(TENANT_KEY, t);
    else localStorage.removeItem(TENANT_KEY);
  } catch {
    /* private mode: the cookie still carries it */
  }
  window.dispatchEvent(new Event("ripple:tenant"));
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public errors: string[] = [],
  ) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const tenant = getTenant();
  const res = await fetch(path, {
    credentials: "include",
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(tenant ? { "X-Ripple-Tenant": tenant } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    let errors: string[] = [];
    try {
      const body = (await res.json()) as { detail?: string | { message?: string; errors?: string[] } };
      if (typeof body.detail === "string") msg = body.detail;
      else if (body.detail) {
        msg = body.detail.message ?? msg;
        errors = body.detail.errors ?? [];
      }
    } catch {
      /* not json */
    }
    throw new ApiError(msg, res.status, errors);
  }
  return (await res.json()) as T;
}

const get = <T,>(p: string) => req<T>(p);
const post = <T,>(p: string, body?: unknown) => req<T>(p, { method: "POST", body: JSON.stringify(body ?? {}) });
const patch = <T,>(p: string, body?: unknown) => req<T>(p, { method: "PATCH", body: JSON.stringify(body ?? {}) });
const del = <T,>(p: string) => req<T>(p, { method: "DELETE" });

// ------------------------------------------------------------------ types
export type Stage = "interview" | "data" | "ontology" | "experts" | "ready";

export interface Step {
  seq: number;
  ts: number;
  tenant: string;
  stage: string;
  agent: string;
  kind: string;
  summary: string;
  node_ids: string[];
  data: Record<string, unknown> | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "agent" | "system";
  agent: string;
  stage: Stage;
  kind: "text" | "form" | "attachment" | "system" | "artifact";
  text: string;
  payload: Record<string, unknown>;
  ts: number;
  seq: number;
}

export type FieldType =
  | "text"
  | "longtext"
  | "number"
  | "integer"
  | "currency"
  | "percent"
  | "date"
  | "daterange"
  | "select"
  | "multiselect"
  | "boolean"
  | "geo"
  | "file"
  | "group";

/** A column of a repeating group. Columns hold scalars: a group cannot contain another group. */
export interface FormColumn {
  id: string;
  label: string;
  type: Exclude<FieldType, "group">;
  help: string;
  placeholder: string;
  unit: string;
  required: boolean;
  example: string;
  options: string[];
  maps_to: string;
}

export interface FormField {
  id: string;
  label: string;
  type: FieldType;
  help: string;
  placeholder: string;
  unit: string;
  required: boolean;
  example: string;
  options: string[];
  show_if: { field?: string; equals?: unknown };
  fields: FormColumn[];
  min_rows: number;
  max_rows: number;
  maps_to: string;
}

export interface FormSpec {
  id: string;
  round: number;
  title: string;
  intro: string;
  fields: FormField[];
  status: "open" | "submitted";
  ts: number;
}

export interface Answer {
  id: string;
  form_id: string;
  field_id: string;
  value: unknown;
  source: "user" | "file" | "synthetic" | "agent";
  confidence: "exact" | "ballpark" | "unknown" | "synthetic";
  ts: number;
}

/** The data agent's proposal that a field is answered by a column of an upload; the user confirms it. */
export interface FileMapping {
  field_id: string;
  attachment_id: string;
  column: string;
  note: string;
  confirmed: boolean;
}

export interface Attachment {
  id: string;
  filename: string;
  mime: string;
  bytes: number;
  kind: "table" | "document";
  summary: string;
  profile?: TableProfile | { chars: number; lines: number };
}

export interface TableProfile {
  rows: number;
  columns: { name: string; dtype: string; nulls: number; distinct: number; min?: number; max?: number; examples?: string[] }[];
  sample: Record<string, unknown>[];
}

export interface PropertySpec {
  name: string;
  type: string;
  unit: string;
  required: boolean;
  description: string;
  options: string[];
}

export interface TypeSpec {
  label: string;
  description: string;
  id_pattern: string;
  properties: PropertySpec[];
  tags: string[];
  display: { icon: string; color: string; title_property: string };
}

export interface RelationshipSpec {
  type: string;
  from: string;
  to: string;
  cardinality: string;
  properties: PropertySpec[];
  description: string;
}

export interface OntologySpec {
  version: number;
  types: TypeSpec[];
  relationships: RelationshipSpec[];
  indexes: { label: string; property: string }[];
  rationale: string;
  coverage: { unmapped_answers: string[]; assumed: string[] };
}

export interface ExpertRole {
  id: string;
  name: string;
  title: string;
  mandate: string;
  justification: string;
  focus_types: string[];
  focus_relationships: string[];
  playbook: string[];
  tools: string[];
  system_prompt: string;
  status: "draft" | "approved" | "retired";
  version: number;
  origin: "generated" | "user";
  stale: boolean;
  ts: number;
}

export interface StageProgress {
  stage: Stage;
  index: number;
  reached: boolean;
  current: boolean;
  open_items: number;
  resolved_items: number;
  artifact: Record<string, unknown>;
}

export interface SessionState {
  tenant: { id?: string; name?: string; stage?: string; status?: string; has_synthetic?: boolean; stages: Stage[] };
  session: { id?: string; provider?: string; model?: string };
  stage: Stage;
  busy: boolean;
  pending: { stage?: string; user_text?: string; agent?: string } | null;
  messages: ChatMessage[];
  open_form: FormSpec | null;
  answers: Answer[];
  attachments: Attachment[];
  artifacts: {
    brief: { version?: number; stale?: boolean; approved?: boolean; data: Brief | null; versions: ArtifactVersion[] };
    ontology: { version?: number; status?: string; stale?: boolean; data: OntologySpec | null; versions: ArtifactVersion[] };
    experts: ExpertRole[];
  };
  counts: { nodes: Record<string, number>; edges: Record<string, number> };
  progress: { stages: StageProgress[]; stage: Stage; steps: number };
  tenant_id?: string;
}

export interface ArtifactVersion {
  id: string;
  version: number;
  status?: string;
  approved?: boolean;
  stale?: boolean;
  created_at?: number;
  ts?: number;
}

export interface Brief {
  company: string;
  industry: string;
  summary: string;
  products: { name: string; description: string; components: string[]; volume: string; markets: string[] }[];
  components: string[];
  suppliers: { kind: string; name: string; country: string; notes: string }[];
  sites: { kind: string; name: string; location: string; notes: string }[];
  manufacturing: string;
  transport_modes: string[];
  warehousing: string;
  distribution: string;
  customers: string[];
  markets: string[];
  commercial: string;
  constraints: string[];
  risks: string[];
  pains: string[];
  vocabulary: Record<string, string>;
  unknowns: string[];
  scale: string;
}

export interface OntologyView {
  spec: OntologySpec | null;
  row: { id?: string; version?: number; status?: string; stale?: boolean; rationale?: string };
  approved_version: number | null;
  errors: string[];
  diagram: { nodes: DiagramNode[]; links: DiagramLink[] };
  versions: ArtifactVersion[];
  counts: { nodes: Record<string, number>; edges: Record<string, number> };
  has_approved: boolean;
}

export interface DiagramNode {
  id: string;
  label: string;
  description: string;
  properties: number;
  color: string;
  icon: string;
  tags: string[];
}

export interface DiagramLink {
  source: string;
  target: string;
  type: string;
  cardinality: string;
}

export interface AskResult {
  ok: boolean;
  text: string;
  reason: string;
  turns: number;
  ids: string[];
  steps: { kind: string; tool?: string; summary?: string; args?: Record<string, unknown> }[];
  tools: string[];
  role: string;
}

export interface Health {
  ok: boolean;
  db_mode: string;
  graphs: string[];
  llm_provider: string | null;
  model: string;
  has_llm: boolean;
  has_jev?: boolean;
  jev_model?: string;
  stages: Stage[];
}

export interface TenantRow {
  id: string;
  name?: string;
  stage?: string;
  status?: string;
  nodes?: number;
  edges?: number;
  created_at?: number;
}

export interface GraphSample {
  nodes: { id: string; label: string; title: string }[];
  edges: { source: string; type: string; target: string }[];
}

export interface Provenance {
  id: string;
  sources: {
    node_id: string;
    source_label: string;
    source_id: string;
    source_ref: string;
    source_value: string;
    source: string;
    confidence: string;
  }[];
}

// ------------------------------------------------------------------ object explorer
export interface ObjectRow {
  id: string;
  title: string;
  properties: Record<string, unknown>;
}

export interface ObjectPage {
  label: string;
  title_property: string;
  total: number;
  skip: number;
  objects: ObjectRow[];
}

export interface ObjectLinkGroup {
  type: string;
  direction: "in" | "out";
  label: string;
  objects: { id: string; label: string; title: string }[];
}

export interface ObjectDetail extends ObjectRow {
  label: string;
  links: ObjectLinkGroup[];
  provenance: Provenance["sources"];
}

export interface ObjectHit extends ObjectRow {
  label: string;
}

// ------------------------------------------------------------------ overview (home page)
export interface Hotspot {
  kind: "status" | "concentration";
  label?: string;
  property?: string;
  value?: string;
  count?: number;
  rel?: string;
  from?: string;
  to?: string;
  single?: number;
  total: number;
  description: string;
  sample: { id: string; title: string }[];
}

export interface Overview {
  tenant: { id: string; name?: string; industry?: string; stage?: string; status?: string; has_synthetic?: boolean; seeded_from?: string };
  stage: Stage;
  busy: boolean;
  has_ontology: boolean;
  version: number | null;
  counts: { nodes: Record<string, number>; edges: Record<string, number> };
  types: number;
  relationships: number;
  hotspots: Hotspot[];
  incidents: { total: number; by_status: Record<string, number>; needs_you: number; recent: IncidentRow[] };
  experts: { id: string; name: string; title: string; mandate: string; status: string; focus_types: string[]; playbook: string[] }[];
}

// ------------------------------------------------------------------ workspace (employees + orchestrator chat)
export interface Employee {
  id: string;
  name: string;
  title: string;
  role_ids: string[];
  ts: number;
  roles?: { id: string; title: string; name: string }[];
}

export interface Delegation {
  expert: string;
  title: string;
  question: string;
  ok: boolean;
  answer: string;
  ids: string[];
  tool_calls: number;
}

export interface WsMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  seq: number;
  ts: number;
  payload: { ok?: boolean; delegations?: Delegation[]; ids?: string[]; turns?: number };
}

export interface WsThread {
  id: string;
  title?: string;
  ts?: number;
  updated_at?: number;
}

export interface WsDashboard {
  employee: Employee;
  roles: { id: string; name: string; title: string; mandate: string; status: string; focus_types: string[]; focus_relationships: string[]; playbook: string[] }[];
  focus_types: string[];
  counts: Record<string, number>;
  hotspots: Hotspot[];
  incidents: IncidentRow[];
  experts: { id: string; name: string; title: string }[];
  threads: WsThread[];
}

// ------------------------------------------------------------------ incidents (M8)
export interface IncidentRow {
  id: string;
  kind: string;
  summary: string;
  source: string;
  status: string;
  priority?: string;
  auto?: boolean;
  received_at: string;
  error?: string;
  ts: number;
  updated_at: number;
}

export interface Evidence {
  id: string;
  from_agent: string;
  claim: string;
  node_ids: string[];
  confidence: string;
}

export interface Metric {
  name: string;
  value: number | string;
  unit: string;
  basis_evidence_ids: string[];
}

export interface CommsDraft {
  id: string;
  recipient_role: string;
  recipient_node_id: string | null;
  channel: string;
  subject: string;
  body: string;
  purpose: string;
  required_by_option_ids: string[];
}

export interface Exchange {
  round: number;
  expert: string;
  question: string;
  why: string;
  answer: string;
  ok: boolean;
  node_ids: string[];
}

export interface IncidentOption {
  id: string;
  title: string;
  action_kind: string;
  steps: string[];
  reversible: boolean;
  time_to_effect_hours: number | null;
  cost_estimate: string;
  risk: string;
  evidence_ids: string[];
  alternative_to: string | null;
  comms_ids: string[];
  is_wait: boolean;
  probability: number | null;
  rank: number | null;
  status: string | null;
  reason: string | null;
}

export interface IncidentGroup {
  id: string;
  question: string;
  mode: "exclusive" | "independent";
  options: IncidentOption[];
}

export interface Incident extends IncidentRow {
  raw: Record<string, unknown>;
  relevant: { name: string; title: string; p: number; consulted: boolean }[] | null;
  exchanges: Exchange[] | null;
  report: { situation: string; evidence: Evidence[]; open_questions: string[] } | null;
  analysis: {
    impact_summary: string;
    metrics: Metric[];
    time_to_impact_hours: number | null;
    affected_node_ids: string[];
    assumptions: string[];
  } | null;
  comms: { drafts: CommsDraft[]; notes: string } | null;
  outcome: {
    priority: string;
    priority_probabilities: Record<string, number>;
    auto: boolean;
    reason: string;
    precedents: string[];
  } | null;
}

export interface JevCall {
  id: string;
  purpose: string;
  model: string;
  ms: number;
  ts: number;
  answers: Record<string, { type: string; probabilities: Record<string, number>; top: string; confidence: number | null }>;
  questions: Record<string, { type: string; instructions: string }>;
  state_chars: number;
}

export interface Impact {
  option_id: string;
  title: string;
  status: string;
  nodes: { label: string; id: string; title: string }[];
  metrics: Metric[];
  messages: CommsDraft[];
  takes_effect_in_hours: number | null;
  effective_at: string | null;
  reversible: boolean;
}

export interface IncidentDetail {
  incident: Incident;
  groups: IncidentGroup[];
  jev: JevCall[];
  approvals: { id: string; option_id: string; actor: string; action: string; note: string; ts: number }[];
  impact: Impact[];
}

// ------------------------------------------------------------------ calls
export const api = {
  health: () => get<Health>("/api/health"),
  config: () => get<{ llm_provider: string | null; model: string; has_llm: boolean; max_upload_mb: number }>("/api/config"),
  tenants: () => get<TenantRow[]>("/api/tenants"),
  tenant: () => get<TenantRow & { counts: SessionState["counts"]; progress: SessionState["progress"] }>("/api/tenant"),
  selectTenant: (id: string) => post<TenantRow>(`/api/tenant/select/${id}`),
  graph: (limit = 400) => get<GraphSample>(`/api/graph?limit=${limit}`),

  start: (company: string, industry: string) => post<SessionState>("/api/onboarding/start", { company, industry }),
  session: () => get<SessionState>("/api/onboarding/session"),
  send: (text: string) => post<{ messages: ChatMessage[]; state: SessionState }>("/api/onboarding/message", { text }),
  resume: () => post<{ messages: ChatMessage[]; state: SessionState }>("/api/onboarding/resume"),
  goto: (stage: Stage, note = "") => post<{ stage: Stage; stale_flagged: number; state: SessionState }>("/api/onboarding/goto", { stage, note }),
  reonboard: (note = "") => post<{ stage: Stage; state: SessionState }>("/api/onboarding/reonboard", { stage: "interview", note }),
  autofill: () => post<{ text: string; note: string; synthetic: boolean }>("/api/onboarding/autofill"),
  steps: (stage = "") => get<{ steps: Step[] }>(`/api/onboarding/steps?stage=${stage}`),

  saveAnswers: (formId: string, values: Record<string, unknown>, confidences: Record<string, string> = {}) =>
    post<{ saved: Answer[]; answers: Answer[] }>(`/api/onboarding/forms/${formId}/answers`, { values, confidences }),
  submitForm: (formId: string, values: Record<string, unknown>) =>
    post<{ messages: ChatMessage[]; state: SessionState }>(`/api/onboarding/forms/${formId}/submit`, { values }),
  mapColumn: (formId: string, m: { field_id: string; attachment_id: string; column?: string; columns?: Record<string, string> }) =>
    post<{ saved: Answer[]; answers: Answer[] }>(`/api/onboarding/forms/${formId}/map`, m),
  synthesize: (formId: string) =>
    post<{ saved: Answer[]; answers: Answer[]; synthetic: boolean }>(`/api/onboarding/forms/${formId}/synthesize`),
  upload: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return req<{ attachment: Attachment; profile: TableProfile }>("/api/onboarding/attachments", { method: "POST", body });
  },

  overview: () => get<Overview>("/api/overview"),
  employees: () => get<{ employees: Employee[] }>("/api/workspace/employees"),
  createEmployee: (e: { name: string; title: string; role_ids: string[] }) => post<Employee>("/api/workspace/employees", e),
  editEmployee: (id: string, e: { name: string; title: string; role_ids: string[] }) => patch<Employee>(`/api/workspace/employees/${id}`, e),
  deleteEmployee: (id: string) => del<{ deleted: string }>(`/api/workspace/employees/${id}`),
  dashboard: (id: string) => get<WsDashboard>(`/api/workspace/employees/${id}/dashboard`),
  threads: (id: string) => get<{ threads: WsThread[] }>(`/api/workspace/employees/${id}/threads`),
  newThread: (id: string) => post<WsThread>(`/api/workspace/employees/${id}/threads`, {}),
  thread: (id: string, tid: string) => get<{ thread: WsThread; messages: WsMessage[]; running: boolean }>(`/api/workspace/employees/${id}/threads/${tid}`),
  deleteThread: (id: string, tid: string) => del<{ deleted: string }>(`/api/workspace/employees/${id}/threads/${tid}`),
  chat: (id: string, text: string, threadId: string) =>
    post<{ thread: WsThread; messages: WsMessage[] }>(`/api/workspace/employees/${id}/chat`, { text, thread_id: threadId }),
  ontology: () => get<OntologyView>("/api/ontology"),
  patchDraft: (spec: OntologySpec) => patch<OntologyView>("/api/ontology/draft", { spec }),
  approveOntology: () => post<{ nodes: number; edges: number; types: number; state: SessionState }>("/api/ontology/approve"),
  provenance: (nodeId: string) => get<Provenance>(`/api/ontology/provenance/${encodeURIComponent(nodeId)}`),

  objects: (label: string, opts: { q?: string; limit?: number; skip?: number } = {}) =>
    get<ObjectPage>(`/api/objects/${encodeURIComponent(label)}?q=${encodeURIComponent(opts.q ?? "")}&limit=${opts.limit ?? 50}&skip=${opts.skip ?? 0}`),
  object: (label: string, id: string) =>
    get<ObjectDetail>(`/api/objects/${encodeURIComponent(label)}/${encodeURIComponent(id)}`),
  searchObjects: (q: string, limit = 5) =>
    get<{ q: string; hits: ObjectHit[] }>(`/api/objects/search?q=${encodeURIComponent(q)}&limit=${limit}`),

  experts: () => get<{ experts: ExpertRole[]; ontology_types: string[]; pending: number; approved: number }>("/api/experts"),
  createExpert: (role: Partial<ExpertRole>) => post<ExpertRole>("/api/experts", { role }),
  editExpert: (id: string, role: Partial<ExpertRole>) => patch<ExpertRole>(`/api/experts/${id}`, { role }),
  approveExpert: (id: string) => post<{ experts: ExpertRole[] }>(`/api/experts/${id}/approve`),
  retireExpert: (id: string) => post<{ experts: ExpertRole[] }>(`/api/experts/${id}/retire`),
  deleteExpert: (id: string) => del<{ experts: ExpertRole[] }>(`/api/experts/${id}`),
  exportExperts: () => post<{ files: string[] }>("/api/experts/export"),
  importExperts: () => post<{ imported: ExpertRole[] }>("/api/experts/import"),
  askExpert: (id: string, question: string) => post<AskResult>(`/api/experts/${id}/ask`, { question }),
  finishOnboarding: () => post<{ state: SessionState }>("/api/experts/finish"),

  incidents: () => get<{ incidents: IncidentRow[] }>("/api/incidents"),
  incident: (id: string) => get<IncidentDetail>(`/api/incidents/${encodeURIComponent(id)}`),
  reportEvent: (event: { summary: string; kind?: string; source?: string }) =>
    post<{ incident_id: string; status: string }>("/api/incidents", event),
  approveOption: (id: string, optionId: string, note = "") =>
    post<IncidentDetail>(`/api/incidents/${encodeURIComponent(id)}/options/${encodeURIComponent(optionId)}/approve`, { note }),
  rejectOption: (id: string, optionId: string, note = "") =>
    post<IncidentDetail>(`/api/incidents/${encodeURIComponent(id)}/options/${encodeURIComponent(optionId)}/reject`, { note }),
  rerunIncident: (id: string) => post<{ incident_id: string; status: string }>(`/api/incidents/${encodeURIComponent(id)}/rerun`),
};

/** Subscribe to the agent step stream. EventSource cannot send headers, so the tenant goes in the query. */
export function streamSteps(after: number, onStep: (s: Step) => void): () => void {
  const tenant = getTenant();
  const url = `/api/onboarding/stream?after=${after}${tenant ? `&tenant=${encodeURIComponent(tenant)}` : ""}`;
  const es = new EventSource(url, { withCredentials: true });
  es.addEventListener("step", (e) => {
    try {
      onStep(JSON.parse((e as MessageEvent).data) as Step);
    } catch {
      /* ignore a malformed frame */
    }
  });
  return () => es.close();
}
