import { useEffect, useRef } from "react";
import type { Answer, Attachment, ChatMessage, FileMapping, FormSpec } from "../../api";
import { agentColor, STAGE_LABELS } from "../colors";
import { Chip } from "../ui";
import InlineForm from "./InlineForm";
import MappingCard from "./MappingCard";

/** The chat thread. A `form` message renders the form it carries; an `artifact` message its summary. */
export default function Thread({
  messages,
  answers,
  openForm,
  attachments,
  busy,
  onSubmitted,
  onAnswers,
}: {
  messages: ChatMessage[];
  answers: Answer[];
  openForm: FormSpec | null;
  attachments: Attachment[];
  busy: boolean;
  onSubmitted: () => void;
  onAnswers: (a: Answer[]) => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, busy]);

  return (
    <div className="flex flex-col gap-6">
      {messages.map((m) => (
        <Bubble key={m.id} m={m}>
          {m.kind === "form" && formOf(m) ? (
            <InlineForm
              form={openForm && openForm.id === formOf(m)!.id ? openForm : formOf(m)!}
              answers={answers}
              readOnly={!openForm || openForm.id !== formOf(m)!.id}
              onSubmitted={onSubmitted}
              onAnswers={onAnswers}
            />
          ) : null}
          {m.kind === "artifact" ? <ArtifactNote m={m} /> : null}
          {mappingsOf(m).length ? (
            <MappingCard
              mappings={mappingsOf(m)}
              form={openForm}
              attachments={attachments}
              onAnswers={onAnswers}
            />
          ) : null}
        </Bubble>
      ))}
      {busy && (
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="h-2 w-2 animate-pulse bg-sky-500" />
          the agent is working…
        </div>
      )}
      <div ref={end} />
    </div>
  );
}

const formOf = (m: ChatMessage): FormSpec | null => (m.payload?.form as FormSpec) ?? null;
const mappingsOf = (m: ChatMessage): FileMapping[] => (m.payload?.file_mappings as FileMapping[]) ?? [];

function Bubble({ m, children }: { m: ChatMessage; children?: React.ReactNode }) {
  if (m.role === "system") {
    return (
      <div className="flex items-center gap-2 text-[11px] text-slate-500">
        <span className="h-px flex-1 bg-line" />
        <span className="micro">{m.text}</span>
        <span className="h-px flex-1 bg-slate-800" />
      </div>
    );
  }
  const mine = m.role === "user";
  return (
    <div className={`flex ${mine ? "justify-end" : ""}`}>
      <div className={`min-w-0 ${mine ? "max-w-[80%]" : "max-w-[92%]"}`}>
        {!mine && (
          <div className="micro mb-1.5 flex items-center gap-1.5 text-muted">
            <span className={`h-1.5 w-1.5 ${agentColor(m.agent)}`} />
            {(m.agent || "ripple").replace(/_/g, " ")}
          </div>
        )}
        <div
          className={`whitespace-pre-wrap text-[13.5px] leading-relaxed ${
            mine ? "border border-line-strong px-3.5 py-2.5 text-ink" : "border-l border-line-strong pl-3.5 text-body"
          }`}
        >
          {m.kind === "attachment" ? (
            <span className="flex items-center gap-2">
              <span className="text-slate-400">uploaded</span>
              <Chip color="bg-slate-800">{m.text}</Chip>
            </span>
          ) : (
            m.text
          )}
        </div>
        {children && <div className="mt-2">{children}</div>}
        <div className={`mt-1.5 text-[10.5px] text-faint ${mine ? "text-right" : "pl-3.5"}`}>
          {STAGE_LABELS[m.stage] ?? m.stage} · {new Date(m.ts).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

function ArtifactNote({ m }: { m: ChatMessage }) {
  const p = m.payload ?? {};
  const bits: string[] = [];
  if (p.types) bits.push(`${p.types} types`);
  if (p.relationships) bits.push(`${p.relationships} relationships`);
  const roles = p.roles as { name: string }[] | undefined;
  if (roles?.length) bits.push(`${roles.length} roles`);
  const questions = p.questions as string[] | undefined;
  if (!bits.length && !questions?.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {bits.map((b) => (
        <Chip key={b} color="bg-violet-900">
          {b}
        </Chip>
      ))}
      {roles?.map((r) => (
        <Chip key={r.name} color="bg-emerald-900">
          {r.name}
        </Chip>
      ))}
    </div>
  );
}
