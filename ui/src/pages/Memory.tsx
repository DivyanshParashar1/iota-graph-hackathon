import { useEffect, useState } from "react";
import { api, fmtTime, money } from "../api";
import type { Episode, Fact, Playbook } from "../api";
import { Card, Chip } from "../components/ui";

export default function Memory({ tenant }: { tenant: string }) {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [facts, setFacts] = useState<Fact[]>([]);
  const [history, setHistory] = useState(true);
  const [convs, setConvs] = useState<{ user_id: string; id: string; started_at: number; messages: number }[]>([]);

  useEffect(() => {
    api.episodes().then(setEpisodes);
    api.playbooks().then(setPlaybooks);
    api.conversations().then(setConvs);
  }, [tenant]);
  useEffect(() => {
    api.facts(history).then(setFacts);
  }, [history, tenant]);

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Episodic memory: past incidents">
        <table className="w-full text-xs [&_td]:px-1.5 [&_th]:px-1.5">
          <thead className="text-left text-slate-500">
            <tr>
              <th>Episode</th>
              <th>Type</th>
              <th>Outcome</th>
              <th className="text-right">Before / after</th>
              <th>Playbook</th>
            </tr>
          </thead>
          <tbody>
            {episodes.map((e) => (
              <tr key={e.id} className="border-t border-slate-800 align-top">
                <td className="py-1">
                  <div className="font-medium">{e.title}</div>
                  <div className="font-mono text-slate-500">{e.id}</div>
                </td>
                <td>{e.disruption_type}</td>
                <td>
                  <Chip color={e.outcome === "resolved" ? "bg-emerald-800" : e.outcome === "partial" ? "bg-amber-800" : "bg-rose-800"}>{e.outcome}</Chip>
                </td>
                <td className="text-right tabular-nums">
                  {money(e.revenue_before)} / {money(e.revenue_after)}
                </td>
                <td className="font-mono">{e.playbook_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Procedural memory: playbooks">
        <div className="space-y-2">
          {playbooks.map((p) => (
            <div key={p.id} className="rounded border border-slate-800 p-2 text-xs">
              <div className="flex items-center justify-between">
                <div>
                  <b>{p.name}</b> <span className="font-mono text-slate-500">{p.id}</span>
                </div>
                <div className="tabular-nums">
                  {Math.round(p.success_rate * 100)}% ({p.successes}/{p.uses})
                </div>
              </div>
              <div className="mt-1 h-1.5 rounded bg-slate-800">
                <div className="h-1.5 rounded bg-emerald-500" style={{ width: `${Math.round(p.success_rate * 100)}%` }} />
              </div>
              <div className="mt-1 text-slate-400">
                {p.disruption_type}: {p.steps.join(" -> ")}
              </div>
            </div>
          ))}
        </div>
      </Card>
      <Card
        title="Semantic memory: facts with validity windows"
        right={
          <label className="text-xs text-slate-400">
            <input type="checkbox" checked={history} onChange={(e) => setHistory(e.target.checked)} /> history
          </label>
        }
      >
        <table className="w-full text-xs [&_td]:px-1.5 [&_th]:px-1.5">
          <thead className="text-left text-slate-500">
            <tr>
              <th>Subject</th>
              <th>Fact</th>
              <th>Valid from</th>
              <th>Valid to</th>
            </tr>
          </thead>
          <tbody>
            {facts.map((f) => (
              <tr key={f.id} className={`border-t border-slate-800 ${f.invalid_at ? "text-slate-500 line-through" : ""}`}>
                <td className="py-1 font-mono">{f.subject_id}</td>
                <td>
                  {f.predicate} = {f.object}
                </td>
                <td>{fmtTime(f.valid_at)}</td>
                <td>{f.invalid_at ? fmtTime(f.invalid_at) : "current"}</td>
              </tr>
            ))}
            {!facts.length && (
              <tr>
                <td colSpan={4} className="py-2 text-slate-500">
                  No facts yet: close an incident or post a handover message.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>
      <Card title="Conversation memory">
        <ul className="space-y-1 text-xs">
          {convs.map((c) => (
            <li key={c.id}>
              <span className="font-mono">{c.user_id}</span> - <span className="font-mono text-slate-400">{c.id}</span> - {c.messages} messages -{" "}
              {fmtTime(c.started_at)}
            </li>
          ))}
          {!convs.length && <li className="text-slate-500">Ask the brain something.</li>}
        </ul>
      </Card>
    </div>
  );
}
