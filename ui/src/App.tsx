import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api, getTenant, setTenant } from "./api";
import type { Health, TenantRow } from "./api";
import Experts from "./pages/Experts";
import Graph from "./pages/Graph";
import Onboarding from "./pages/Onboarding";
import Ontology from "./pages/Ontology";

const NAV = [
  ["/", "Onboarding"],
  ["/ontology", "Ontology"],
  ["/experts", "Experts"],
  ["/graph", "Graph"],
];

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [current, setCurrent] = useState(getTenant());

  useEffect(() => {
    api.health().then(setHealth).catch(() => undefined);
    api.tenants().then(setTenants).catch(() => undefined);
  }, []);

  const switchTenant = async (id: string) => {
    setTenant(id);
    setCurrent(id);
    await api.selectTenant(id).catch(() => undefined);
    window.location.reload();
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="flex flex-wrap items-center gap-4 border-b border-slate-800 bg-slate-900 px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold tracking-tight text-sky-400">Ripple</span>
          <span className="hidden text-xs text-slate-500 sm:inline">
            it interviews your company and builds the graph
          </span>
        </div>
        <nav className="flex flex-wrap gap-1">
          {NAV.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `rounded px-2.5 py-1 text-sm ${isActive ? "bg-slate-700 text-white" : "text-slate-400 hover:text-white"}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-xs">
          {health && (
            <span
              className={health.has_llm ? "text-slate-500" : "text-rose-400"}
              title={health.has_llm ? `provider ${health.llm_provider}` : "no LLM provider configured"}
            >
              {health.has_llm ? `${health.llm_provider} · ${health.model}` : "no LLM provider"}
            </span>
          )}
          {tenants.length > 1 && (
            <select
              className="rounded bg-slate-800 px-2 py-1"
              value={current}
              onChange={(e) => void switchTenant(e.target.value)}
            >
              {tenants.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name ?? t.id}
                </option>
              ))}
            </select>
          )}
        </div>
      </header>
      <main className="p-4">
        <Routes>
          <Route path="/" element={<Onboarding />} />
          <Route path="/ontology" element={<Ontology />} />
          <Route path="/experts" element={<Experts />} />
          <Route path="/graph" element={<Graph />} />
        </Routes>
      </main>
    </div>
  );
}
