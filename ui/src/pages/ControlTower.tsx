import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, fmtTime, money } from "../api";
import type { Health, IncidentRow, MapData, Scenario } from "../api";
import MapView from "../components/MapView";
import { Btn, Card, Chip, ErrorLine, statusColor } from "../components/ui";

export default function ControlTower({ tenant }: { tenant: string }) {
  const [map, setMap] = useState<MapData | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [incidents, setIncidents] = useState<IncidentRow[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [mode, setMode] = useState("scripted");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const nav = useNavigate();

  const load = useCallback(() => {
    Promise.all([api.map(), api.scenarios(), api.incidents(), api.health()])
      .then(([m, s, i, h]) => {
        setMap(m);
        setScenarios(s);
        setIncidents(i);
        setHealth(h);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
  }, [load, tenant]);

  const trigger = async (id: string) => {
    setBusy(id);
    setError(null);
    try {
      const r = await api.trigger(id, mode);
      nav(`/incidents/${r.incident_id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const disrupted = map?.ports.filter((p) => p.status === "disrupted").length ?? 0;
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-4">
        <Card
          title="Network"
          right={
            <span className="text-xs text-slate-400">
              {map?.ports.length ?? 0} ports, {map?.plants.length ?? 0} plants, {map?.suppliers.length ?? 0} suppliers,{" "}
              <span className={disrupted ? "text-rose-400" : ""}>{disrupted} disrupted</span>
            </span>
          }
        >
          <MapView data={map} />
        </Card>
        <Card title="Incidents">
          <ErrorLine error={error} />
          <table className="w-full text-sm [&_td]:px-1.5 [&_th]:px-1.5">
            <thead className="text-left text-xs text-slate-500">
              <tr>
                <th className="py-1">Incident</th>
                <th>Status</th>
                <th className="text-right">At risk (initial)</th>
                <th className="text-right">Now</th>
                <th className="text-right">Orders</th>
                <th>Opened</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((i) => (
                <tr key={i.id} className="border-t border-slate-800">
                  <td className="py-1.5">
                    <Link className="text-sky-400 hover:underline" to={`/incidents/${i.id}`}>
                      {i.title}
                    </Link>{" "}
                    <Chip>{i.id}</Chip>
                  </td>
                  <td>
                    <Chip color={statusColor(i.status)}>{i.status}</Chip>
                  </td>
                  <td className="text-right tabular-nums">{money(i.revenue_at_risk_initial)}</td>
                  <td className="text-right tabular-nums">{money(i.revenue_at_risk)}</td>
                  <td className="text-right tabular-nums">{i.orders_at_risk ?? "-"}</td>
                  <td className="text-xs text-slate-400">{fmtTime(i.opened_at)}</td>
                </tr>
              ))}
              {!incidents.length && (
                <tr>
                  <td colSpan={6} className="py-3 text-slate-500">
                    No incidents yet. Trigger a scenario.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </Card>
      </div>
      <div className="space-y-4">
        <Card
          title="Scenarios"
          right={
            <select
              className="rounded bg-slate-800 px-2 py-1 text-xs"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              title="Agent mode"
            >
              <option value="scripted">scripted agents</option>
              <option value="llm">Claude agents ({health?.agent_mode ?? "?"})</option>
            </select>
          }
        >
          <div className="space-y-3">
            {scenarios.map((s) => (
              <div key={s.id} className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-medium">{s.name}</div>
                    <div className="mt-1 text-xs text-slate-400">{s.description}</div>
                  </div>
                  <Btn kind="danger" onClick={() => trigger(s.id)} disabled={busy !== null}>
                    {busy === s.id ? "..." : "Trigger"}
                  </Btn>
                </div>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Active disruptions">
          {map?.disruptions.length ? (
            <ul className="space-y-1 text-sm">
              {map.disruptions.map((d) => (
                <li key={d.id}>
                  <Chip color="bg-rose-800">{d.type}</Chip> {d.name}{" "}
                  {d.incident_id && (
                    <Link className="text-sky-400 hover:underline" to={`/incidents/${d.incident_id}`}>
                      {d.incident_id}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-sm text-slate-500">None</div>
          )}
        </Card>
        <Card title="Graph">
          <div className="text-xs text-slate-400">
            FalkorDB {health?.db_mode} - graphs: {health?.graphs.join(", ")}
          </div>
        </Card>
      </div>
    </div>
  );
}
