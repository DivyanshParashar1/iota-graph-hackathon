import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { OntologySpec, OntologyView, PropertySpec, TypeSpec } from "../api";
import GraphView from "../components/GraphView";
import { PROPERTY_TYPES } from "../constants";
import { Btn, Card, Chip, ErrorLine, Stat } from "../components/ui";

/** Review, edit and approve the generated graph model. Approval is what loads the data. */
export default function Ontology() {
  const [view, setView] = useState<OntologyView | null>(null);
  const [draft, setDraft] = useState<OntologySpec | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState("");
  const [selected, setSelected] = useState<string>("");
  const nav = useNavigate();

  const load = useCallback(async () => {
    try {
      const v = await api.ontology();
      setView(v);
      setDraft(v.spec);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const dirty = useMemo(
    () => !!draft && !!view?.spec && JSON.stringify(draft) !== JSON.stringify(view.spec),
    [draft, view?.spec],
  );

  const save = async () => {
    if (!draft) return;
    setBusy("save");
    setError(null);
    setErrors([]);
    try {
      const v = await api.patchDraft(draft);
      setView(v);
      setDraft(v.spec);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      if (e instanceof ApiError) setErrors(e.errors);
    } finally {
      setBusy("");
    }
  };

  const approve = async () => {
    setBusy("approve");
    setError(null);
    setErrors([]);
    try {
      await api.approveOntology();
      await load();
      nav("/experts");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      if (e instanceof ApiError) setErrors(e.errors);
    } finally {
      setBusy("");
    }
  };

  if (!view) return <div className="p-6 text-sm text-slate-500">{error ?? "loading…"}</div>;
  if (!view.spec || !draft) {
    return (
      <Card title="Ontology">
        <p className="text-sm text-slate-400">
          No model yet. The ontology agent designs it once the data stage is done — go back to the chat.
        </p>
      </Card>
    );
  }

  const nodes = draft.types.map((t) => ({
    id: t.label,
    label: t.label,
    title: `${t.properties.length} properties · ${view.counts.nodes[t.label] ?? 0} nodes`,
    color: t.display?.color || "",
    size: 4 + Math.min(6, t.properties.length / 2),
  }));
  const links = draft.relationships.map((r) => ({ source: r.from, target: r.to, type: r.type }));
  const type = draft.types.find((t) => t.label === selected);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-semibold text-slate-100">Your graph model</h1>
        <Chip color="bg-slate-800">v{view.row.version}</Chip>
        <Chip color={view.row.status === "approved" ? "bg-emerald-800" : "bg-amber-800"}>{view.row.status}</Chip>
        {view.row.stale && <Chip color="bg-amber-800">stale — re-approve</Chip>}
        <div className="ml-auto flex gap-2">
          {dirty && (
            <Btn onClick={save} disabled={busy !== ""}>
              {busy === "save" ? "validating…" : "Save edits as a new version"}
            </Btn>
          )}
          <Btn kind="primary" onClick={approve} disabled={busy !== "" || dirty}>
            {busy === "approve"
              ? "applying and loading…"
              : view.row.status === "approved"
                ? "Re-approve and reload"
                : "Approve, apply and load the data"}
          </Btn>
        </div>
      </div>

      {(error || errors.length > 0) && (
        <div className="flex flex-col gap-1">
          <ErrorLine error={error} />
          {errors.map((e) => (
            <div key={e} className="rounded bg-rose-950/60 px-2 py-1 text-xs text-rose-200">
              {e}
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label="Types" value={draft.types.length} />
        <Stat label="Relationships" value={draft.relationships.length} />
        <Stat
          label="Nodes loaded"
          value={Object.values(view.counts.nodes).reduce((a, b) => a + b, 0).toLocaleString()}
        />
        <Stat
          label="Edges loaded"
          value={Object.values(view.counts.edges).reduce((a, b) => a + b, 0).toLocaleString()}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
        <Card title="Diagram" right={<span className="text-[11px] text-slate-500">click a type to edit it</span>}>
          <GraphView nodes={nodes} links={links} height={520} showLabels onSelect={(n) => setSelected(n.id)} />
        </Card>
        <div className="flex flex-col gap-4">
          {draft.rationale && (
            <Card title="Why this model">
              <p className="text-xs leading-relaxed text-slate-300">{draft.rationale}</p>
              {!!draft.coverage?.assumed?.length && (
                <div className="mt-2">
                  <div className="text-[11px] uppercase text-slate-500">assumed</div>
                  <ul className="list-disc pl-4 text-[11px] text-slate-400">
                    {draft.coverage.assumed.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}
              {!!draft.coverage?.unmapped_answers?.length && (
                <div className="mt-2">
                  <div className="text-[11px] uppercase text-slate-500">nothing in the model holds</div>
                  <ul className="list-disc pl-4 text-[11px] text-amber-300">
                    {draft.coverage.unmapped_answers.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          )}
          {type ? (
            <TypeEditor
              type={type}
              onChange={(next) =>
                setDraft({ ...draft, types: draft.types.map((t) => (t.label === type.label ? next : t)) })
              }
              onClose={() => setSelected("")}
            />
          ) : (
            <Card title="Types">
              <div className="max-h-[420px] overflow-y-auto">
                <table className="w-full text-xs">
                  <tbody>
                    {draft.types.map((t) => (
                      <tr key={t.label} className="border-t border-slate-800 align-top">
                        <td className="py-1 pr-2">
                          <button onClick={() => setSelected(t.label)} className="font-medium text-sky-300 hover:underline">
                            {t.label}
                          </button>
                          <div className="text-slate-500">{t.description}</div>
                        </td>
                        <td className="py-1 text-right tabular-nums text-slate-400">
                          {t.properties.length}p
                          <div className="text-slate-600">{view.counts.nodes[t.label] ?? 0}</div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
          <Card title="Relationships">
            <div className="max-h-[300px] overflow-y-auto">
              <table className="w-full text-xs">
                <tbody>
                  {draft.relationships.map((r) => (
                    <tr key={`${r.type}-${r.from}-${r.to}`} className="border-t border-slate-800">
                      <td className="py-1 font-mono text-[11px] text-slate-300">
                        ({r.from})-[{r.type}]-&gt;({r.to})
                        {r.description && <div className="font-sans text-slate-500">{r.description}</div>}
                      </td>
                      <td className="py-1 text-right tabular-nums text-slate-500">
                        {view.counts.edges[r.type] ?? 0}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          {view.versions.length > 1 && (
            <Card title="Version history">
              <ul className="text-[11px] text-slate-400">
                {view.versions.map((v) => (
                  <li key={v.id} className="flex items-center gap-2 border-t border-slate-800 py-1">
                    <span className="font-mono">v{v.version}</span>
                    <Chip color={v.status === "approved" ? "bg-emerald-900" : "bg-slate-800"}>{v.status}</Chip>
                    {v.stale ? <Chip color="bg-amber-900">stale</Chip> : null}
                    <span className="ml-auto text-slate-600">{v.ts ? new Date(v.ts).toLocaleString() : ""}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function TypeEditor({
  type,
  onChange,
  onClose,
}: {
  type: TypeSpec;
  onChange: (t: TypeSpec) => void;
  onClose: () => void;
}) {
  const setProp = (i: number, next: PropertySpec) =>
    onChange({ ...type, properties: type.properties.map((p, j) => (i === j ? next : p)) });
  const cell = "w-full rounded border border-slate-800 bg-slate-950 px-1 py-0.5 text-[11px] text-slate-100";
  return (
    <Card
      title={`Edit ${type.label}`}
      right={
        <Btn kind="ghost" onClick={onClose}>
          close
        </Btn>
      }
    >
      <div className="flex flex-col gap-2">
        <label className="block">
          <span className="text-[11px] text-slate-500">label</span>
          <input className={cell} value={type.label} onChange={(e) => onChange({ ...type, label: e.target.value })} />
        </label>
        <label className="block">
          <span className="text-[11px] text-slate-500">description</span>
          <input
            className={cell}
            value={type.description}
            onChange={(e) => onChange({ ...type, description: e.target.value })}
          />
        </label>
        <label className="block">
          <span className="text-[11px] text-slate-500">id pattern</span>
          <input
            className={cell}
            value={type.id_pattern}
            onChange={(e) => onChange({ ...type, id_pattern: e.target.value })}
          />
        </label>
        <div>
          <div className="mb-1 text-[11px] uppercase text-slate-500">properties</div>
          <table className="w-full">
            <thead>
              <tr className="text-left text-[10px] uppercase text-slate-600">
                <th>name</th>
                <th>type</th>
                <th>unit</th>
                <th className="w-8">req</th>
              </tr>
            </thead>
            <tbody>
              {type.properties.map((p, i) => (
                <tr key={p.name}>
                  <td className="pr-1">
                    <input className={cell} value={p.name} onChange={(e) => setProp(i, { ...p, name: e.target.value })} />
                  </td>
                  <td className="pr-1">
                    <select className={cell} value={p.type} onChange={(e) => setProp(i, { ...p, type: e.target.value })}>
                      {PROPERTY_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="pr-1">
                    <input className={cell} value={p.unit} onChange={(e) => setProp(i, { ...p, unit: e.target.value })} />
                  </td>
                  <td className="text-center">
                    <input
                      type="checkbox"
                      checked={p.required}
                      onChange={(e) => setProp(i, { ...p, required: e.target.checked })}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-slate-600">
          Prefer asking the agent in the chat for anything structural — it keeps the rationale and the
          instance mapping in step.
        </p>
      </div>
    </Card>
  );
}
