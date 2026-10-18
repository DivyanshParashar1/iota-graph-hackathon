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
    <ol className="flex flex-wrap items-stretch gap-x-3 gap-y-2">
      {stages.map((s) => {
        const tone = s.current
          ? "border-ink text-ink"
          : s.reached
            ? "border-slate-500 text-muted hover:border-slate-300 hover:text-ink"
            : "border-line text-slate-600";
        const stale = s.artifact?.stale;
        return (
          <li key={s.stage} className="min-w-28 flex-1">
            <button
              type="button"
              disabled={disabled || !s.reached || s.current}
              onClick={() => onGoto(s.stage)}
              title={s.reached && !s.current ? `go back to ${s.stage}` : undefined}
              className={`w-full border-t pt-2 text-left transition-colors disabled:cursor-default ${tone}`}
            >
              <div className="flex items-center gap-1.5">
                <span className="micro !text-[9.5px] tabular-nums opacity-60">0{s.index + 1}</span>
                <span className="micro">{STAGE_LABELS[s.stage] ?? s.stage}</span>
                {stale ? <span className="ml-auto text-[10px] text-amber-400">stale</span> : null}
              </div>
              <div className="mt-0.5 text-[11px] text-faint">{detail(s)}</div>
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
