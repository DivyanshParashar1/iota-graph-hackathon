import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api, getTenant, setTenant } from "./api";
import type { Tenant, TenantInfo } from "./api";
import Actions from "./pages/Actions";
import Brain from "./pages/Brain";
import ControlTower from "./pages/ControlTower";
import Incident from "./pages/Incident";
import Memory from "./pages/Memory";
import Ontology from "./pages/Ontology";

const NAV = [
  ["/", "Control Tower"],
  ["/actions", "Action Queue"],
  ["/brain", "Company Brain"],
  ["/memory", "Memory"],
  ["/ontology", "Ontology"],
];

export default function App() {
  const [tenant, setT] = useState<Tenant>(getTenant());
  const [tenants, setTenants] = useState<TenantInfo[]>([]);
  useEffect(() => {
    api.tenants().then(setTenants).catch(() => undefined);
  }, []);
  const switchTenant = (t: Tenant) => {
    setTenant(t);
    setT(t);
  };
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="flex flex-wrap items-center gap-4 border-b border-slate-800 bg-slate-900 px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold tracking-tight text-sky-400">Ripple</span>
          <span className="hidden text-xs text-slate-500 sm:inline">supply chain control tower on FalkorDB</span>
        </div>
        <nav className="flex flex-wrap gap-1">
          {NAV.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) => `rounded px-2.5 py-1 text-sm ${isActive ? "bg-slate-700 text-white" : "text-slate-400 hover:text-white"}`}
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2 text-xs">
          <span className="text-slate-500">tenant</span>
          <select className="rounded bg-slate-800 px-2 py-1" value={tenant} onChange={(e) => switchTenant(e.target.value as Tenant)}>
            {(tenants.length ? tenants : [{ id: "dataco", name: "DataCo Global" }, { id: "nova", name: "Nova Retail" }]).map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
      </header>
      <main className="p-4" key={tenant}>
        <Routes>
          <Route path="/" element={<ControlTower tenant={tenant} />} />
          <Route path="/incidents/:id" element={<Incident />} />
          <Route path="/actions" element={<Actions tenant={tenant} />} />
          <Route path="/brain" element={<Brain tenant={tenant} />} />
          <Route path="/memory" element={<Memory tenant={tenant} />} />
          <Route path="/ontology" element={<Ontology tenant={tenant} />} />
        </Routes>
      </main>
    </div>
  );
}
