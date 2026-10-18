import type { Step } from "../../api";
import { agentColor } from "../colors";

const KIND_TONE: Record<string, string> = {
  llm: "text-sky-300",
  write: "text-emerald-300",
  tool_call: "text-amber-300",
  tool_result: "text-amber-200",
  stage: "text-violet-300",
  decision: "text-violet-300",
  error: "text-rose-300",
};

/** The live trail: what the agents are thinking, calling and writing, as it happens. */
export default function StepStream({ steps, height = 420 }: { steps: Step[]; height?: number }) {
  const recent = steps.slice(-200).reverse();
  return (
    <div className="overflow-y-auto font-mono text-[11px] leading-relaxed" style={{ maxHeight: height }}>
      {!recent.length && <div className="text-slate-600">no agent activity yet</div>}
      {recent.map((s) => (
        <div key={`${s.seq}-${s.ts}`} className="flex gap-1.5 border-b border-slate-900 py-1">
          <span className="w-12 shrink-0 text-slate-600">{new Date(s.ts).toLocaleTimeString().slice(0, 8)}</span>
          <span className={`h-4 shrink-0 rounded px-1 text-[10px] text-white ${agentColor(s.agent)}`}>{s.agent}</span>
          <span className={`shrink-0 ${KIND_TONE[s.kind] ?? "text-slate-400"}`}>{s.kind}</span>
          <span className="min-w-0 break-words text-slate-300">{s.summary}</span>
        </div>
      ))}
    </div>
  );
}
