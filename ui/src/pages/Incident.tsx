import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, eventsUrl, money } from "../api";
import type { AgentEvent, GraphNode, IncidentDetail, SubGraph } from "../api";
import { AGENT_COLORS } from "../components/colors";
import GraphView from "../components/GraphView";
import { Btn, Card, Chip, ErrorLine, Stat, statusColor } from "../components/ui";

export default function Incident() {
  const { id = "" } = useParams();
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [graph, setGraph] = useState<SubGraph>({ nodes: [], links: [] });
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [focus, setFocus] = useState<Set<string> | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const refresh = useCallback(() => {
    api.incident(id).then(setDetail).catch((e: Error) => setError(e.message));
    api.incidentGraph(id).then(setGraph).catch(() => undefined);
  }, [id]);

  useEffect(() => {
    setEvents([]);
    const es = new EventSource(eventsUrl(id));
    es.onmessage = (m) => {
      const ev = JSON.parse(m.data) as AgentEvent;
      setEvents((prev) => (prev.some((p) => p.seq === ev.seq) ? prev : [...prev, ev]));
      if (ev.kind === "tool_result" && (ev.tool === "blast_radius" || ev.tool === "propose_action")) refresh();
      if (ev.kind === "done" || ev.kind === "error") {
        es.close();
        refresh();
      }
    };
    es.onerror = () => es.close();
    refresh();
    return () => es.close();
  }, [id, refresh]);

  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }), [events.length]);

  const timeline = useMemo(() => events.filter((e) => e.kind !== "tool_call"), [events]);
  const inc = detail?.incident;
  const act = async (fn: () => Promise<{ revenue_before?: number | null; revenue_after?: number | null; status?: string }>, label: string) => {
    setError(null);
    try {
      const r = await fn();
      if (r.revenue_before != null) setNote(`${label}: revenue at risk ${money(r.revenue_before)} -> ${money(r.revenue_after)}`);
      refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(320px,1fr)_2fr_minmax(300px,1fr)]">
      <Card title="Agent timeline" right={<Chip>{events.length} events</Chip>}>
        <div className="max-h-[78vh] space-y-2 overflow-y-auto pr-1">
          {timeline.map((e) => (
            <div
              key={e.seq}
              className={`rounded-md border p-2 text-xs ${e.kind === "error" ? "border-rose-800 bg-rose-950/40" : e.kind === "handoff" ? "border-slate-700 bg-slate-900" : "border-slate-800 bg-slate-950/60"}`}
              onClick={() => e.node_ids.length && setFocus(new Set(e.node_ids))}
            >
              <div className="mb-1 flex items-center gap-1.5">
                <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase text-white ${AGENT_COLORS[e.agent] ?? "bg-slate-600"}`}>
                  {e.agent}
                </span>
                {e.tool && <Chip color="bg-indigo-900">{e.tool}</Chip>}
                {e.kind === "handoff" && <span className="text-slate-400">handoff</span>}
                {e.kind === "done" && <Chip color="bg-emerald-800">done</Chip>}
                {typeof e.data?._ms === "number" && <span className="ml-auto text-slate-500">{Math.round(e.data._ms as number)} ms</span>}
              </div>
              <div className="text-slate-300">{e.summary}</div>
            </div>
          ))}
          <div ref={bottom} />
        </div>
      </Card>
      <div className="space-y-4">
        <Card
          title={inc ? `${inc.title}` : id}
          right={
            <div className="flex items-center gap-2">
              {inc && <Chip color={statusColor(inc.status)}>{inc.status}</Chip>}
              {focus && (
                <Btn kind="ghost" onClick={() => setFocus(undefined)}>
                  clear focus
                </Btn>
              )}
            </div>
          }
        >
          <GraphView graph={graph} highlight={focus} onSelect={setSelected} height={560} />
          <div className="mt-2 text-xs text-slate-500">
            Click a timeline step to highlight the nodes it used. {graph.nodes.length} nodes, {graph.links.length} links.
          </div>
        </Card>
        {selected && (
          <Card title="Selected node" right={<Btn kind="ghost" onClick={() => setSelected(null)}>x</Btn>}>
            <div className="text-sm">
              <Chip>{selected.label}</Chip> <b>{selected.name}</b> <span className="font-mono text-xs text-slate-400">{selected.id}</span>
            </div>
          </Card>
        )}
      </div>
      <div className="space-y-4">
        <Card title="Revenue at risk">
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Before" value={money(inc?.revenue_at_risk_initial)} />
            <Stat label="Now" value={money(inc?.revenue_at_risk)} />
            <Stat label="Open orders" value={inc?.orders_at_risk ?? "-"} sub={`initially ${inc?.orders_at_risk_initial ?? "-"}`} />
            <Stat label="Customers" value={inc?.customers_affected ?? "-"} />
          </div>
          {note && <div className="mt-2 rounded bg-emerald-950 p-2 text-xs text-emerald-200">{note}</div>}
          <ErrorLine error={error} />
        </Card>
        <Card title="Actions" right={<Link className="text-xs text-sky-400" to="/actions">queue</Link>}>
          <div className="space-y-2">
            {detail?.actions.map((a) => (
              <div key={a.id} className="rounded border border-slate-800 p-2 text-xs">
                <div className="flex items-center gap-1.5">
                  <Chip color={statusColor(a.status)}>{a.status}</Chip>
                  <b>{a.type}</b>
                </div>
                <div className="mt-1 text-slate-400">{a.summary}</div>
                <div className="mt-1.5 flex gap-1.5">
                  {a.status === "proposed" && (
                    <>
                      <Btn kind="primary" onClick={() => act(() => api.approve(a.id), "Approved")}>
                        Approve
                      </Btn>
                      <Btn kind="danger" onClick={() => act(() => api.reject(a.id), "Rejected")}>
                        Reject
                      </Btn>
                    </>
                  )}
                  {a.status === "executed" && !a.type.startsWith("UNDO_") && (
                    <Btn onClick={() => act(() => api.undo(a.id), "Undone")}>Undo</Btn>
                  )}
                </div>
              </div>
            ))}
          </div>
          {inc && inc.status !== "closed" && (
            <div className="mt-3">
              <Btn kind="ghost" onClick={() => act(async () => { const r = await api.close(id); setNote(`Closed: episode ${r.data.episode.episode_id} (${r.data.episode.outcome})`); return {}; }, "Closed")}>
                Close incident and record episode
              </Btn>
            </div>
          )}
        </Card>
        <Card title="Memory">
          {detail?.recalled.slice(0, 2).map((e) => (
            <div key={e.id} className="mb-2 rounded border border-slate-800 p-2 text-xs">
              <div className="font-medium">{e.title}</div>
              <div className="text-slate-400">
                {e.disruption_type} - outcome {e.outcome} - {e.actions_taken.join(", ")}
              </div>
            </div>
          ))}
          {detail?.playbook && (
            <div className="rounded bg-slate-950 p-2 text-xs">
              Playbook <b>{detail.playbook.name}</b> ({Math.round(detail.playbook.success_rate * 100)}% over {detail.playbook.uses} uses):{" "}
              {detail.playbook.steps.join(" -> ")}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
