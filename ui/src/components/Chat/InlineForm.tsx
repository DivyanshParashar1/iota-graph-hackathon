import { useEffect, useMemo, useState } from "react";
import type { Answer, FormField, FormSpec } from "../../api";
import { api, ApiError } from "../../api";
import { Btn, Chip, ErrorLine } from "../ui";
import { CONFIDENCE_COLORS } from "../colors";

type Values = Record<string, unknown>;

const visible = (f: FormField, values: Values): boolean =>
  !f.show_if?.field || values[f.show_if.field] === f.show_if.equals;

const input =
  "w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100 placeholder:text-slate-600 focus:border-sky-600 focus:outline-none";

/** One form round, rendered inside the chat thread. Every field autosaves as it loses focus. */
export default function InlineForm({
  form,
  answers,
  onSubmitted,
  onAnswers,
  readOnly = false,
}: {
  form: FormSpec;
  answers: Answer[];
  onSubmitted: () => void;
  onAnswers?: (a: Answer[]) => void;
  readOnly?: boolean;
}) {
  const saved = useMemo(() => {
    const out: Values = {};
    for (const a of answers.filter((x) => x.form_id === form.id)) out[a.field_id] = a.value;
    return out;
  }, [answers, form.id]);
  const sources = useMemo(() => {
    const out: Record<string, string> = {};
    for (const a of answers.filter((x) => x.form_id === form.id)) out[a.field_id] = a.confidence;
    return out;
  }, [answers, form.id]);

  const [values, setValues] = useState<Values>(saved);
  const [ballpark, setBallpark] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"" | "save" | "submit" | "synth">("");

  useEffect(() => setValues((v) => ({ ...saved, ...v })), [saved]);

  const set = (id: string, v: unknown) => setValues((prev) => ({ ...prev, [id]: v }));

  const save = async (id: string) => {
    if (readOnly) return;
    setError(null);
    setBusy("save");
    try {
      const out = await api.saveAnswers(form.id, { [id]: values[id] ?? null },
        ballpark[id] ? { [id]: "ballpark" } : {});
      onAnswers?.(out.answers);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  };

  const submit = async () => {
    setError(null);
    setBusy("submit");
    try {
      await api.submitForm(form.id, values);
      onSubmitted();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy("");
    }
  };

  const synthesize = async () => {
    setError(null);
    setBusy("synth");
    try {
      const out = await api.synthesize(form.id);
      const next: Values = {};
      for (const a of out.answers) next[a.field_id] = a.value;
      setValues(next);
      onAnswers?.(out.answers);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="rounded-lg border border-amber-900/60 bg-amber-950/10 p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-amber-200">{form.title}</span>
        <Chip color="bg-amber-900">round {form.round}</Chip>
        {form.status === "submitted" && <Chip color="bg-slate-700">submitted</Chip>}
        <div className="ml-auto flex gap-1">
          {!readOnly && (
            <Btn kind="ghost" onClick={synthesize} disabled={busy !== ""}>
              {busy === "synth" ? "inventing…" : "Synthesize (demo)"}
            </Btn>
          )}
        </div>
      </div>
      {form.intro && <p className="mb-3 text-xs text-slate-400">{form.intro}</p>}
      <div className="grid gap-3">
        {form.fields.filter((f) => visible(f, values)).map((f) => (
          <Field
            key={f.id}
            field={f}
            value={values[f.id]}
            source={sources[f.id]}
            ballpark={!!ballpark[f.id]}
            readOnly={readOnly}
            onBallpark={(b) => setBallpark((p) => ({ ...p, [f.id]: b }))}
            onChange={(v) => set(f.id, v)}
            onBlur={() => save(f.id)}
          />
        ))}
      </div>
      <ErrorLine error={error} />
      {!readOnly && (
        <div className="mt-3 flex items-center gap-2">
          <Btn kind="primary" onClick={submit} disabled={busy !== ""}>
            {busy === "submit" ? "sending…" : "Submit"}
          </Btn>
          <span className="text-[11px] text-slate-500">
            {busy === "save" ? "saving…" : "answers save as you go — you can come back later"}
          </span>
        </div>
      )}
    </div>
  );
}

function Field({
  field,
  value,
  source,
  ballpark,
  readOnly,
  onChange,
  onBlur,
  onBallpark,
}: {
  field: FormField;
  value: unknown;
  source?: string;
  ballpark: boolean;
  readOnly: boolean;
  onChange: (v: unknown) => void;
  onBlur: () => void;
  onBallpark: (b: boolean) => void;
}) {
  const f = field;
  return (
    <label className="block">
      <div className="mb-1 flex flex-wrap items-center gap-1.5">
        <span className="text-xs font-medium text-slate-200">{f.label}</span>
        {f.required && <span className="text-xs text-rose-400">*</span>}
        {f.unit && <Chip color="bg-slate-800">{f.unit}</Chip>}
        {f.maps_to && <Chip color="bg-slate-800" title="the ontology concept this becomes">{f.maps_to}</Chip>}
        {source && source !== "exact" && (
          <Chip color={CONFIDENCE_COLORS[source] ?? "bg-slate-800"}>{source}</Chip>
        )}
        {!readOnly && f.type !== "group" && (
          <button
            type="button"
            onClick={() => onBallpark(!ballpark)}
            className={`ml-auto rounded px-1.5 py-0.5 text-[11px] ${ballpark ? "bg-amber-800 text-amber-100" : "bg-slate-800 text-slate-400"}`}
            title="mark this answer as a ballpark rather than an exact figure"
          >
            ballpark
          </button>
        )}
      </div>
      {f.help && <p className="mb-1 text-[11px] text-slate-500">{f.help}</p>}
      <Control field={f} value={value} readOnly={readOnly} onChange={onChange} onBlur={onBlur} />
      {f.example && !value && <p className="mt-1 text-[11px] text-slate-600">e.g. {f.example}</p>}
    </label>
  );
}

function Control({
  field: f,
  value,
  readOnly,
  onChange,
  onBlur,
}: {
  field: FormField;
  value: unknown;
  readOnly: boolean;
  onChange: (v: unknown) => void;
  onBlur: () => void;
}) {
  const common = { disabled: readOnly, onBlur, className: input };
  switch (f.type) {
    case "group":
      return <GroupTable field={f} rows={(value as Record<string, unknown>[]) ?? []} readOnly={readOnly} onChange={onChange} onBlur={onBlur} />;
    case "longtext":
      return <textarea {...common} rows={3} value={(value as string) ?? ""} placeholder={f.placeholder} onChange={(e) => onChange(e.target.value)} />;
    case "boolean":
      return (
        <select {...common} value={value === true ? "yes" : value === false ? "no" : ""} onChange={(e) => onChange(e.target.value === "" ? null : e.target.value === "yes")}>
          <option value="">—</option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </select>
      );
    case "select":
      return (
        <select {...common} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)}>
          <option value="">—</option>
          {f.options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      );
    case "multiselect":
      return (
        <div className="flex flex-wrap gap-1">
          {f.options.map((o) => {
            const list = Array.isArray(value) ? (value as string[]) : [];
            const on = list.includes(o);
            return (
              <button
                key={o}
                type="button"
                disabled={readOnly}
                onClick={() => {
                  onChange(on ? list.filter((x) => x !== o) : [...list, o]);
                  setTimeout(onBlur, 0);
                }}
                className={`rounded px-2 py-0.5 text-xs ${on ? "bg-sky-700 text-white" : "bg-slate-800 text-slate-300"}`}
              >
                {o}
              </button>
            );
          })}
        </div>
      );
    case "daterange": {
      const v = (value as { from?: string; to?: string }) ?? {};
      return (
        <div className="flex gap-2">
          <input {...common} type="date" value={v.from ?? ""} onChange={(e) => onChange({ ...v, from: e.target.value })} />
          <input {...common} type="date" value={v.to ?? ""} onChange={(e) => onChange({ ...v, to: e.target.value })} />
        </div>
      );
    }
    case "geo": {
      const v = (value as { lat?: number; lon?: number }) ?? {};
      return (
        <div className="flex gap-2">
          <input {...common} placeholder="lat" value={v.lat ?? ""} onChange={(e) => onChange({ ...v, lat: Number(e.target.value) })} />
          <input {...common} placeholder="lon" value={v.lon ?? ""} onChange={(e) => onChange({ ...v, lon: Number(e.target.value) })} />
        </div>
      );
    }
    case "date":
      return <input {...common} type="date" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />;
    case "number":
    case "integer":
    case "currency":
    case "percent":
      return (
        <input
          {...common}
          inputMode="decimal"
          value={value === null || value === undefined ? "" : String(value)}
          placeholder={f.placeholder || (f.type === "percent" ? "0-100" : "")}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case "file":
      return <p className="text-xs text-slate-500">Upload the file in the chat below and the agent will map it.</p>;
    default:
      return <input {...common} value={(value as string) ?? ""} placeholder={f.placeholder} onChange={(e) => onChange(e.target.value)} />;
  }
}

/** A repeating group: the group's fields are the columns and the user adds rows. */
function GroupTable({
  field: f,
  rows,
  readOnly,
  onChange,
  onBlur,
}: {
  field: FormField;
  rows: Record<string, unknown>[];
  readOnly: boolean;
  onChange: (v: unknown) => void;
  onBlur: () => void;
}) {
  const cols = f.fields;
  const setCell = (i: number, id: string, v: unknown) => {
    const next = rows.map((r, j) => (i === j ? { ...r, [id]: v } : r));
    onChange(next);
  };
  const addRow = () => onChange([...rows, {}]);
  const dropRow = (i: number) => {
    onChange(rows.filter((_, j) => j !== i));
    setTimeout(onBlur, 0);
  };
  return (
    <div className="overflow-x-auto rounded border border-slate-800">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-slate-900/80 text-left text-slate-400">
            {cols.map((c) => (
              <th key={c.id} className="px-2 py-1 font-medium">
                {c.label}
                {c.unit ? <span className="ml-1 text-slate-600">({c.unit})</span> : null}
              </th>
            ))}
            <th className="w-8" />
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-slate-800">
              {cols.map((c) => (
                <td key={c.id} className="px-1 py-1">
                  <input
                    disabled={readOnly}
                    onBlur={onBlur}
                    className="w-full min-w-24 rounded border border-slate-800 bg-slate-950 px-1.5 py-0.5 text-xs text-slate-100 focus:border-sky-600 focus:outline-none"
                    value={r[c.id] === undefined || r[c.id] === null ? "" : String(r[c.id])}
                    placeholder={c.placeholder || c.example}
                    onChange={(e) => setCell(i, c.id, e.target.value)}
                  />
                </td>
              ))}
              <td className="px-1 text-center">
                {!readOnly && (
                  <button type="button" onClick={() => dropRow(i)} className="text-slate-500 hover:text-rose-400">
                    ×
                  </button>
                )}
              </td>
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan={cols.length + 1} className="px-2 py-2 text-center text-slate-600">
                no rows yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {!readOnly && (
        <div className="border-t border-slate-800 p-1">
          <Btn kind="ghost" onClick={addRow} disabled={rows.length >= (f.max_rows || 50)}>
            + add row
          </Btn>
        </div>
      )}
    </div>
  );
}
