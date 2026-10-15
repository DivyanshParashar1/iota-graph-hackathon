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
  pending: { stage?: string; user_text?: string } | null;
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
  steps: (stage = "") => get<{ steps: Step[] }>(`/api/onboarding/steps?stage=${stage}`),

  saveAnswers: (formId: string, values: Record<string, unknown>, confidences: Record<string, string> = {}) =>
    post<{ saved: Answer[]; answers: Answer[] }>(`/api/onboarding/forms/${formId}/answers`, { values, confidences }),
  submitForm: (formId: string, values: Record<string, unknown>) =>
    post<{ messages: ChatMessage[]; state: SessionState }>(`/api/onboarding/forms/${formId}/submit`, { values }),
  synthesize: (formId: string) =>
    post<{ saved: Answer[]; answers: Answer[]; synthetic: boolean }>(`/api/onboarding/forms/${formId}/synthesize`),
  upload: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return req<{ attachment: Attachment; profile: TableProfile }>("/api/onboarding/attachments", { method: "POST", body });
  },

  ontology: () => get<OntologyView>("/api/ontology"),
  patchDraft: (spec: OntologySpec) => patch<OntologyView>("/api/ontology/draft", { spec }),
  approveOntology: () => post<{ nodes: number; edges: number; types: number; state: SessionState }>("/api/ontology/approve"),
  provenance: (nodeId: string) => get<Provenance>(`/api/ontology/provenance/${encodeURIComponent(nodeId)}`),

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
