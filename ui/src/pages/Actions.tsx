import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtTime, money } from "../api";
import type { Action } from "../api";
import { Btn, Card, Chip, ErrorLine, statusColor } from "../components/ui";

export default function Actions({ tenant }: { tenant: string }) {
  const [status, setStatus] = useState("proposed");
  const [rows, setRows] = useState<Action[]>([]);
  const [open, setOpen] = useState<Action | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.actions(status || undefined).then(setRows).catch((e: Error) => setError(e.message));
  }, [status]);
  useEffect(load, [load, tenant]);

  const run = async (fn: () => Promise<{ revenue_before?: number | null; revenue_after?: number | null; status?: string }>, label: string) => {
    setError(null);
    try {
      const r = await fn();
      setNote(`${label}${r.revenue_before != null ? `: revenue at risk ${money(r.revenue_before)} -> ${money(r.revenue_after)}` : ""}`);
      load();
      if (open) setOpen(await api.action(open.id));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <Card
        title="Action queue"
        right={
          <select className="rounded bg-slate-800 px-2 py-1 text-xs" value={status} onChange={(e) => setStatus(e.target.value)}>
            {["proposed", "executed", "rejected", "undone", ""].map((s) => (
              <option key={s} value={s}>
                {s || "all"}
              </option>
            ))}
          </select>
        }
      >
        {note && <div className="mb-2 rounded bg-emerald-950 p-2 text-xs text-emerald-200">{note}</div>}
        <ErrorLine error={error} />
        <table className="w-full text-sm [&_td]:px-1.5 [&_th]:px-1.5">
          <thead className="text-left text-xs text-slate-500">
            <tr>
              <th>Action</th>
              <th>Status</th>
              <th>Incident</th>
              <th>Agent</th>
              <th>Created</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id} className="border-t border-slate-800 align-top">
                <td className="py-1.5">
                  <button className="text-left text-sky-400 hover:underline" onClick={() => api.action(a.id).then(setOpen)}>
                    {a.type}
                  </button>
                  <div className="text-xs text-slate-400">{a.summary}</div>
                </td>
                <td>
                  <Chip color={statusColor(a.status)}>{a.status}</Chip>
                </td>
                <td>
                  <Link className="font-mono text-xs text-sky-400" to={`/incidents/${a.incident_id}`}>
                    {a.incident_id}
                  </Link>
                </td>
                <td className="text-xs">{a.agent}</td>
                <td className="text-xs text-slate-400">{fmtTime(a.created_at)}</td>
                <td className="space-x-1 whitespace-nowrap">
                  {a.status === "proposed" && (
                    <>
                      <Btn kind="primary" onClick={() => run(() => api.approve(a.id), `Approved ${a.id}`)}>
                        Approve
                      </Btn>
                      <Btn kind="danger" onClick={() => run(() => api.reject(a.id), `Rejected ${a.id}`)}>
                        Reject
                      </Btn>
                    </>
                  )}
                  {a.status === "approved" && <Btn onClick={() => run(() => api.execute(a.id), `Executed ${a.id}`)}>Execute</Btn>}
                  {a.status === "executed" && !a.type.startsWith("UNDO_") && (
                    <Btn onClick={() => run(() => api.undo(a.id), `Undid ${a.id}`)}>Undo</Btn>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Evidence" right={open && <Btn kind="ghost" onClick={() => setOpen(null)}>x</Btn>}>
        {open ? (
          <div className="space-y-2 text-sm">
            <div>
              <b>{open.type}</b> <Chip>{open.id}</Chip> <Chip color={statusColor(open.status)}>{open.status}</Chip>
            </div>
            <div className="text-xs text-slate-400">{open.summary}</div>
            <div className="text-xs">
              Proposed by <b>{open.agent}</b>
              {open.approved_by && (
                <>
                  , approved by <b>{open.approved_by}</b>
                </>
              )}
            </div>
            <div className="text-xs uppercase text-slate-500">Based on (graph evidence)</div>
            <ul className="space-y-1">
              {open.evidence?.map((e) => (
                <li key={e.id} className="text-xs">
                  <Chip>{e.label}</Chip> <span className="font-mono">{e.id}</span> {e.name !== e.id && <span className="text-slate-400">{e.name}</span>}{" "}
                  <span className="text-slate-500">({e.role})</span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="text-sm text-slate-500">Select an action to see the nodes it is BASED_ON.</div>
        )}
      </Card>
    </div>
  );
}
