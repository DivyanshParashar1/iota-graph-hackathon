import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { AskResult, ExpertRole } from "../api";
import { Btn, Card, Chip, ErrorLine } from "../components/ui";

const EMPTY: Partial<ExpertRole> = {
  name: "",
  title: "",
  mandate: "",
  justification: "",
  focus_types: [],
  focus_relationships: [],
  playbook: [],
  tools: [],
  system_prompt: "",
};

/** Review, approve, edit and run the generated expert roles. Full CRUD after onboarding. */
export default function Experts() {
  const [roles, setRoles] = useState<ExpertRole[]>([]);
  const [types, setTypes] = useState<string[]>([]);
  const [counts, setCounts] = useState({ pending: 0, approved: 0 });
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [open, setOpen] = useState<string>("");
  const [editing, setEditing] = useState<Partial<ExpertRole> | null>(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    try {
      const out = await api.experts();
      setRoles(out.experts);
      setTypes(out.ontology_types);
      setCounts({ pending: out.pending, approved: out.approved });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setError(null);
    setErrors([]);
    try {
      await fn();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      if (e instanceof ApiError) setErrors(e.errors);
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-semibold text-slate-100">Expert roles</h1>
        <Chip color="bg-emerald-900">{counts.approved} approved</Chip>
        {counts.pending > 0 && <Chip color="bg-amber-900">{counts.pending} awaiting you</Chip>}
        <div className="ml-auto flex gap-2">
          <Btn kind="ghost" onClick={() => setEditing({ ...EMPTY })}>
            + new role
          </Btn>
          <Btn kind="ghost" onClick={() => void act("export", api.exportExperts)}>
            {busy === "export" ? "writing…" : "Export to markdown"}
          </Btn>
          <Btn kind="ghost" onClick={() => void act("import", api.importExperts)}>
            {busy === "import" ? "reading…" : "Import from markdown"}
          </Btn>
          {counts.approved > 0 && (
            <Btn kind="primary" onClick={() => void act("finish", api.finishOnboarding)}>
              {busy === "finish" ? "finishing…" : "Finish onboarding"}
            </Btn>
          )}
        </div>
      </div>

      <ErrorLine error={error} />
      {errors.map((e) => (
        <div key={e} className="rounded bg-rose-950/60 px-2 py-1 text-xs text-rose-200">
          {e}
        </div>
      ))}

      {editing && (
        <RoleEditor
          role={editing}
          types={types}
          onCancel={() => setEditing(null)}
          onSave={async (r) => {
            await act("save", () => (r.id ? api.editExpert(r.id, r) : api.createExpert(r)));
            setEditing(null);
          }}
        />
      )}

      {!roles.length && (
        <Card>
          <p className="text-sm text-slate-400">
            No roles yet. The expert generator writes them once the ontology is approved.
          </p>
        </Card>
      )}

      <div className="grid gap-3 lg:grid-cols-2">
        {roles.map((r) => (
          <RoleCard
            key={r.id}
            role={r}
            open={open === r.id}
            busy={busy}
            onToggle={() => setOpen(open === r.id ? "" : r.id)}
            onEdit={() => setEditing(r)}
            onApprove={() => void act(`approve-${r.id}`, () => api.approveExpert(r.id))}
            onRetire={() => void act(`retire-${r.id}`, () => api.retireExpert(r.id))}
            onDelete={() => void act(`delete-${r.id}`, () => api.deleteExpert(r.id))}
          />
        ))}
      </div>
    </div>
  );
}

function RoleCard({
  role: r,
  open,
  busy,
  onToggle,
  onEdit,
  onApprove,
  onRetire,
  onDelete,
}: {
  role: ExpertRole;
  open: boolean;
  busy: string;
  onToggle: () => void;
  onEdit: () => void;
  onApprove: () => void;
  onRetire: () => void;
  onDelete: () => void;
}) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskResult | null>(null);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);

  const ask = async () => {
    if (!question.trim()) return;
    setAsking(true);
    setAskError(null);
    setAnswer(null);
    try {
      setAnswer(await api.askExpert(r.id, question.trim()));
    } catch (e) {
      setAskError(e instanceof Error ? e.message : String(e));
    } finally {
      setAsking(false);
    }
  };

  const tone =
    r.status === "approved" ? "bg-emerald-800" : r.status === "retired" ? "bg-slate-700" : "bg-amber-800";
  return (
    <Card
      title={r.title || r.name}
      right={
        <span className="flex items-center gap-1">
          <Chip color={tone}>{r.status}</Chip>
          {r.stale && <Chip color="bg-amber-900">stale</Chip>}
          <Chip color="bg-slate-800">{r.origin}</Chip>
          <Chip color="bg-slate-800">v{r.version}</Chip>
        </span>
      }
    >
      <div className="flex flex-col gap-2 text-xs">
        <p className="text-slate-200">{r.mandate}</p>
        <p className="text-slate-400">
          <span className="text-slate-500">why: </span>
          {r.justification}
        </p>
        <div className="flex flex-wrap gap-1">
          {r.focus_types.map((t) => (
            <Chip key={t} color="bg-sky-900">
              {t}
            </Chip>
          ))}
          {r.focus_relationships.map((t) => (
            <Chip key={t} color="bg-indigo-900">
              {t}
            </Chip>
          ))}
        </div>
        {!!r.playbook.length && (
          <ul className="list-disc pl-4 text-slate-400">
            {r.playbook.slice(0, open ? 99 : 2).map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap gap-1">
          <Btn kind="ghost" onClick={onToggle}>
            {open ? "hide prompt" : "show prompt"}
          </Btn>
          <Btn kind="ghost" onClick={onEdit}>
            edit
          </Btn>
          {r.status !== "approved" && (
            <Btn kind="primary" onClick={onApprove} disabled={busy !== ""}>
              approve
            </Btn>
          )}
          {r.status === "approved" && (
            <Btn onClick={onRetire} disabled={busy !== ""}>
              retire
            </Btn>
          )}
          <Btn kind="danger" onClick={onDelete} disabled={busy !== ""}>
            delete
          </Btn>
        </div>
        {open && (
          <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded bg-slate-950 p-2 text-[11px] text-slate-300">
            {r.system_prompt}
          </pre>
        )}
        <div className="mt-1 border-t border-slate-800 pt-2">
          <div className="flex gap-1">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void ask()}
              placeholder={r.playbook[0]?.split("?")[0] ? `${r.playbook[0].split("?")[0]}?` : "Ask this expert…"}
              className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-100 focus:border-sky-600 focus:outline-none"
            />
            <Btn onClick={ask} disabled={asking || !question.trim()}>
              {asking ? "…" : "ask"}
            </Btn>
          </div>
          <ErrorLine error={askError} />
          {answer && (
            <div className="mt-2 rounded bg-slate-950 p-2">
              <p className="whitespace-pre-wrap text-xs text-slate-200">{answer.text || answer.reason}</p>
              <div className="mt-1 flex flex-wrap gap-1 text-[10px] text-slate-500">
                <span>{answer.turns} turns</span>
                {answer.steps
                  .filter((s) => s.kind === "tool_call")
                  .map((s, i) => (
                    <Chip key={i} color="bg-slate-800">
                      {s.tool}
                    </Chip>
                  ))}
                {answer.ids.slice(0, 8).map((id) => (
                  <Chip key={id} color="bg-slate-800">
                    {id}
                  </Chip>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function RoleEditor({
  role,
  types,
  onSave,
  onCancel,
}: {
  role: Partial<ExpertRole>;
  types: string[];
  onSave: (r: Partial<ExpertRole>) => Promise<void>;
  onCancel: () => void;
}) {
  const [r, setR] = useState<Partial<ExpertRole>>(role);
  const cell = "w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-xs text-slate-100";
  const set = (k: keyof ExpertRole, v: unknown) => setR((p) => ({ ...p, [k]: v }));
  return (
    <Card title={r.id ? `Edit ${r.name}` : "New role"}>
      <div className="flex flex-col gap-2">
        <div className="grid gap-2 sm:grid-cols-2">
          <label>
            <span className="text-[11px] text-slate-500">name (snake_case)</span>
            <input className={cell} value={r.name ?? ""} onChange={(e) => set("name", e.target.value)} />
          </label>
          <label>
            <span className="text-[11px] text-slate-500">title</span>
            <input className={cell} value={r.title ?? ""} onChange={(e) => set("title", e.target.value)} />
          </label>
        </div>
        <label>
          <span className="text-[11px] text-slate-500">mandate</span>
          <input className={cell} value={r.mandate ?? ""} onChange={(e) => set("mandate", e.target.value)} />
        </label>
        <label>
          <span className="text-[11px] text-slate-500">justification (must name an ontology type)</span>
          <textarea
            rows={2}
            className={cell}
            value={r.justification ?? ""}
            onChange={(e) => set("justification", e.target.value)}
          />
        </label>
        <div>
          <span className="text-[11px] text-slate-500">focus types</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {types.map((t) => {
              const on = (r.focus_types ?? []).includes(t);
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() =>
                    set("focus_types", on ? (r.focus_types ?? []).filter((x) => x !== t) : [...(r.focus_types ?? []), t])
                  }
                  className={`rounded px-2 py-0.5 text-xs ${on ? "bg-sky-700 text-white" : "bg-slate-800 text-slate-300"}`}
                >
                  {t}
                </button>
              );
            })}
          </div>
        </div>
        <label>
          <span className="text-[11px] text-slate-500">playbook (one question per line)</span>
          <textarea
            rows={3}
            className={cell}
            value={(r.playbook ?? []).join("\n")}
            onChange={(e) => set("playbook", e.target.value.split("\n").filter(Boolean))}
          />
        </label>
        <label>
          <span className="text-[11px] text-slate-500">system prompt (executed as-is)</span>
          <textarea
            rows={10}
            className={`${cell} font-mono`}
            value={r.system_prompt ?? ""}
            onChange={(e) => set("system_prompt", e.target.value)}
          />
        </label>
        <div className="flex gap-2">
          <Btn kind="primary" onClick={() => void onSave(r)}>
            save
          </Btn>
          <Btn kind="ghost" onClick={onCancel}>
            cancel
          </Btn>
        </div>
      </div>
    </Card>
  );
}
