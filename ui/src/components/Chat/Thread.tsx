import { useEffect, useRef } from "react";
import type { Answer, ChatMessage, FormSpec } from "../../api";
import { agentColor, STAGE_LABELS } from "../colors";
import { Chip } from "../ui";
import InlineForm from "./InlineForm";

/** The chat thread. A `form` message renders the form it carries; an `artifact` message its summary. */
export default function Thread({
  messages,
  answers,
  openForm,
  busy,
  onSubmitted,
  onAnswers,
}: {
  messages: ChatMessage[];
  answers: Answer[];
  openForm: FormSpec | null;
  busy: boolean;
  onSubmitted: () => void;
  onAnswers: (a: Answer[]) => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, busy]);

  return (
    <div className="flex flex-col gap-3">
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
        </Bubble>
      ))}
      {busy && (
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="h-2 w-2 animate-pulse rounded-full bg-sky-500" />
          the agent is working…
        </div>
      )}
      <div ref={end} />
    </div>
  );
}

const formOf = (m: ChatMessage): FormSpec | null => (m.payload?.form as FormSpec) ?? null;

function Bubble({ m, children }: { m: ChatMessage; children?: React.ReactNode }) {
  if (m.role === "system") {
    return (
      <div className="flex items-center gap-2 text-[11px] text-slate-500">
        <span className="h-px flex-1 bg-slate-800" />
        <span>{m.text}</span>
        <span className="h-px flex-1 bg-slate-800" />
      </div>
    );
  }
  const mine = m.role === "user";
  return (
    <div className={`flex gap-2 ${mine ? "justify-end" : ""}`}>
      {!mine && (
        <div className={`mt-0.5 h-6 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium text-white ${agentColor(m.agent)}`}>
          {m.agent || "ripple"}
        </div>
      )}
      <div className={`max-w-[85%] min-w-0 ${mine ? "order-first" : ""}`}>
        <div
          className={`rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
            mine ? "bg-sky-900/50 text-sky-50" : "bg-slate-900 text-slate-100"
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
        <div className="mt-1 text-[10px] text-slate-600">
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
