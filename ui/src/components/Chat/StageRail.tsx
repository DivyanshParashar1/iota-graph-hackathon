import type { Stage, StageProgress } from "../../api";
import { STAGE_LABELS } from "../colors";

/** The four stages plus "ready". A reached stage is clickable: that is the jump-back. */
export default function StageRail({
  stages,
  onGoto,
  disabled,
}: {
  stages: StageProgress[];
  onGoto: (s: Stage) => void;
  disabled?: boolean;
}) {
  return (
    <ol className="flex flex-wrap items-stretch gap-1">
      {stages.map((s) => {
        const tone = s.current
          ? "border-sky-600 bg-sky-950/60 text-sky-100"
          : s.reached
            ? "border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500"
            : "border-slate-900 bg-slate-950 text-slate-600";
        const stale = s.artifact?.stale;
        return (
          <li key={s.stage} className="min-w-28 flex-1">
            <button
              type="button"
              disabled={disabled || !s.reached || s.current}
              onClick={() => onGoto(s.stage)}
              title={s.reached && !s.current ? `go back to ${s.stage}` : undefined}
              className={`w-full rounded-md border px-2 py-1.5 text-left transition disabled:cursor-default ${tone}`}
            >
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] tabular-nums opacity-60">{s.index + 1}</span>
                <span className="text-xs font-medium">{STAGE_LABELS[s.stage] ?? s.stage}</span>
                {stale ? <span className="ml-auto text-[10px] text-amber-400">stale</span> : null}
              </div>
              <div className="mt-0.5 text-[10px] opacity-70">{detail(s)}</div>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function detail(s: StageProgress): string {
  const a = s.artifact ?? {};
  if (s.stage === "interview") {
    if (a.version) return `brief v${a.version}${s.open_items ? ` · ${s.open_items} open` : ""}`;
    return s.open_items ? `${s.open_items} open questions` : "not started";
  }
  if (s.stage === "data") {
    if (!a.rounds) return "not started";
    return `${a.rounds} round${a.rounds === 1 ? "" : "s"} · ${a.answers ?? 0} answers`;
  }
  if (s.stage === "ontology") return a.version ? `v${a.version} ${a.status}` : "not started";
  if (s.stage === "experts") {
    if (!a.total) return "not started";
    return `${a.approved ?? 0}/${a.total} approved`;
  }
  return s.reached ? "live" : "—";
}
