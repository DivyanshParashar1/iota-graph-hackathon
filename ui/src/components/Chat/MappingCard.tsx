import { useState } from "react";
import { api } from "../../api";
import type { Answer, Attachment, FileMapping, FormField, FormSpec, TableProfile } from "../../api";
import { Btn, Chip, ErrorLine } from "../ui";

/** The data agent proposes "this field is answered by that column"; this is where the user confirms it.
 *
 * A single field takes one column. A repeating group takes one column per group column, which is how an
 * uploaded supplier master fills a whole table without anyone retyping it. */
export default function MappingCard({
  mappings,
  form,
  attachments,
  onAnswers,
}: {
  mappings: FileMapping[];
  form: FormSpec | null;
  attachments: Attachment[];
  onAnswers: (a: Answer[]) => void;
}) {
  if (!form || !mappings.length) return null;
  const byId = new Map(form.fields.map((f) => [f.id, f]));
  const usable = mappings.filter((m) => byId.has(m.field_id) && attachments.some((a) => a.id === m.attachment_id));
  if (!usable.length) return null;
  return (
    <div className="border border-line-strong border-t-sky-400 p-4">
      <div className="mb-2 text-xs font-semibold text-sky-200">Answer these from a file you uploaded?</div>
      <div className="flex flex-col gap-2">
        {usable.map((m) => (
          <Row
            key={`${m.field_id}-${m.attachment_id}`}
            mapping={m}
            field={byId.get(m.field_id)!}
            attachment={attachments.find((a) => a.id === m.attachment_id)!}
            formId={form.id}
            onAnswers={onAnswers}
          />
        ))}
      </div>
    </div>
  );
}

function columnsOf(a: Attachment): string[] {
  const p = a.profile as TableProfile | undefined;
  return p?.columns?.map((c) => c.name) ?? [];
}

function Row({
  mapping,
  field,
  attachment,
  formId,
  onAnswers,
}: {
  mapping: FileMapping;
  field: FormField;
  attachment: Attachment;
  formId: string;
  onAnswers: (a: Answer[]) => void;
}) {
  const cols = columnsOf(attachment);
  const guess = (want: string) =>
    cols.find((c) => c.toLowerCase().replace(/[^a-z]/g, "") === want.toLowerCase().replace(/[^a-z]/g, "")) ??
    cols.find((c) => c.toLowerCase().includes(want.toLowerCase().split("_")[0])) ??
    "";
  const [column, setColumn] = useState(mapping.column && cols.includes(mapping.column) ? mapping.column : guess(field.id));
  const [groupCols, setGroupCols] = useState<Record<string, string>>(
    Object.fromEntries(field.fields.map((c) => [c.id, guess(c.id)])),
  );
  const [state, setState] = useState<"" | "busy" | "done">("");
  const [error, setError] = useState<string | null>(null);
  const select = "border border-slate-700 bg-slate-950 px-1 py-0.5 text-[11px] text-slate-100";

  const apply = async () => {
    setState("busy");
    setError(null);
    try {
      const out = await api.mapColumn(formId, {
        field_id: field.id,
        attachment_id: attachment.id,
        ...(field.type === "group" ? { columns: groupCols } : { column }),
      });
      onAnswers(out.answers);
      setState("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setState("");
    }
  };

  return (
    <div className="bg-slate-950/60 p-2">
      <div className="mb-1 flex flex-wrap items-center gap-1.5 text-xs">
        <span className="text-slate-200">{field.label}</span>
        <span className="text-slate-600">from</span>
        <Chip color="bg-slate-800">{attachment.filename}</Chip>
        {mapping.note && <span className="text-[11px] text-slate-500">{mapping.note}</span>}
      </div>
      {field.type === "group" ? (
        <div className="flex flex-wrap gap-2">
          {field.fields.map((c) => (
            <label key={c.id} className="text-[11px] text-slate-400">
              {c.label}{" "}
              <select
                className={select}
                value={groupCols[c.id] ?? ""}
                onChange={(e) => setGroupCols((p) => ({ ...p, [c.id]: e.target.value }))}
              >
                <option value="">—</option>
                {cols.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      ) : (
        <select className={select} value={column} onChange={(e) => setColumn(e.target.value)}>
          <option value="">pick a column…</option>
          {cols.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      )}
      <div className="mt-1.5 flex items-center gap-2">
        <Btn
          kind={state === "done" ? "default" : "primary"}
          onClick={apply}
          disabled={state === "busy" || (field.type === "group" ? !Object.values(groupCols).some(Boolean) : !column)}
        >
          {state === "busy" ? "reading…" : state === "done" ? "applied" : "Use this column"}
        </Btn>
        {state === "done" && <span className="text-[11px] text-emerald-400">saved as a file answer</span>}
      </div>
      <ErrorLine error={error} />
    </div>
  );
}
