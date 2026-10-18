import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api, getTenant, setTenant } from "./api";
import type { Employee, Health, TenantRow } from "./api";
import CommandPalette from "./components/CommandPalette";
import { Icon } from "./components/icons";
import { Kbd } from "./components/ui";
import Experts from "./pages/Experts";
import Graph from "./pages/Graph";
import Home from "./pages/Home";
import Incidents from "./pages/Incidents";
import Objects from "./pages/Objects";
import Onboarding from "./pages/Onboarding";
import Ontology from "./pages/Ontology";
import Workspace, { Avatar } from "./pages/Workspace";
import OntologyType from "./pages/OntologyType";
import { useOntology } from "./useOntology";
import { usePersona } from "./usePersona";

const NAV: { to: string; label: string; icon: string; group: string }[] = [
  { to: "/", label: "Overview", icon: "layers", group: "Home" },
  { to: "/workspace", label: "My workspace", icon: "users", group: "Home" },
  { to: "/onboarding", label: "Onboarding", icon: "chat", group: "Build" },
  { to: "/ontology", label: "Ontology", icon: "schema", group: "Build" },
  { to: "/objects", label: "Object explorer", icon: "table", group: "Explore" },
  { to: "/graph", label: "Graph", icon: "graph", group: "Explore" },
  { to: "/experts", label: "Experts", icon: "experts", group: "Operate" },
  { to: "/incidents", label: "Incidents", icon: "incident", group: "Operate" },
];

function readCollapsed() {
  try {
    return localStorage.getItem("ripple.rail") === "collapsed";
  } catch {
    return false;
  }
}

function Dot({ ok, label, title }: { ok: boolean | undefined; label: string; title: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[11px] text-muted" title={title}>
      <span className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-400 shadow-[0_0_6px] shadow-emerald-500/70" : ok === false ? "bg-rose-400" : "bg-slate-600"}`} />
      {label}
    </span>
  );
}

function Logo() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="2.6" fill="#4C90F0" />
      <circle cx="12" cy="12" r="6.3" stroke="#4C90F0" strokeOpacity=".75" strokeWidth="1.6" />
      <circle cx="12" cy="12" r="10" stroke="#4C90F0" strokeOpacity=".4" strokeWidth="1.6" />
    </svg>
  );
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [current, setCurrent] = useState(getTenant());
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [palette, setPalette] = useState(false);
  const { view } = useOntology();
  const [persona] = usePersona();
  const [people, setPeople] = useState<Employee[]>([]);
  const loc = useLocation();

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api.tenants().then(setTenants).catch(() => undefined);
  }, []);

  useEffect(() => {
    api.employees().then((r) => setPeople(r.employees)).catch(() => setPeople([]));
  }, [persona]);
  const me = people.find((p) => p.id === persona);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      const typing = el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
      if ((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !typing)) {
        e.preventDefault();
        setPalette(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toggleRail = () => {
    setCollapsed((c) => {
      try {
        localStorage.setItem("ripple.rail", c ? "open" : "collapsed");
      } catch {
        /* storage unavailable: the rail just won't remember */
      }
      return !c;
    });
  };

  const switchTenant = async (id: string) => {
    setTenant(id);
    setCurrent(id);
    await api.selectTenant(id).catch(() => undefined);
    window.location.reload();
  };

  const tenant = tenants.find((t) => t.id === current) ?? (tenants.length === 1 ? tenants[0] : undefined);
  const ontoStatus = view?.has_approved ? `v${view.approved_version} approved` : view?.row?.version ? `v${view.row.version} draft` : null;
  let lastGroup = "";

  return (
    <div className="flex h-full flex-col bg-canvas text-body">
      <header className="flex h-11 shrink-0 items-center gap-3 border-b border-line bg-[#15191e] px-3">
        <button onClick={toggleRail} className="rounded-[3px] p-1 text-muted hover:bg-hover hover:text-ink" title="Toggle navigation">
          <Icon name="menu" size={16} />
        </button>
        <div className="flex items-center gap-2">
          <Logo />
          <span className="text-[14px] font-semibold tracking-tight text-ink">Ripple</span>
        </div>
        <span className="h-5 w-px bg-line-strong" />
        <div className="flex min-w-0 items-center gap-2 text-[12px]">
          <Icon name="building" size={14} className="text-faint" />
          {tenants.length > 1 ? (
            <select
              className="max-w-[16rem] truncate rounded-[3px] border border-transparent bg-transparent py-0.5 pr-1 font-medium text-ink hover:border-line-strong focus:border-accent"
              value={tenant?.id ?? current}
              onChange={(e) => void switchTenant(e.target.value)}
            >
              {!tenant && <option value="">Select a company…</option>}
              {tenants.map((t) => (
                <option key={t.id} value={t.id} className="bg-panel">
                  {t.name ?? t.id}
                </option>
              ))}
            </select>
          ) : (
            <span className="truncate font-medium text-ink">{tenant?.name ?? "No company yet"}</span>
          )}
          {ontoStatus && (
            <span className={`hidden rounded-[3px] border px-1.5 py-px font-mono text-[10.5px] sm:inline ${view?.has_approved ? "border-emerald-800 bg-success-soft text-emerald-300" : "border-amber-800 bg-warning-soft text-amber-300"}`}>
              ontology {ontoStatus}
            </span>
          )}
        </div>

        <NavLink to="/workspace" title={me ? `Viewing as ${me.name}` : "Pick who you are"}
                 className="ml-auto flex h-7 items-center gap-2 rounded-[3px] border border-line px-1.5 pr-2.5 text-[12px] text-muted hover:border-line-strong hover:text-ink">
          {me ? <Avatar name={me.name} size={20} /> : <Icon name="user" size={14} />}
          <span className="hidden max-w-[10rem] truncate sm:inline">{me ? me.name : "Who are you?"}</span>
        </NavLink>
        <button
          onClick={() => setPalette(true)}
          className=" flex h-7 w-[min(360px,40vw)] items-center gap-2 rounded-[3px] border border-line bg-sunken px-2 text-left text-[12px] text-faint hover:border-line-strong"
        >
          <Icon name="search" size={13} />
          <span className="flex-1 truncate">Search objects, types…</span>
          <Kbd>/</Kbd>
        </button>

        <div className="hidden items-center gap-3 border-l border-line pl-3 lg:flex">
          <Dot ok={health?.ok} label={health ? `DB ${health.db_mode}` : "DB"} title="FalkorDB connection" />
          <Dot ok={health ? health.has_llm : undefined} label="LLM"
               title={health?.has_llm ? `${health.llm_provider} · ${health.model}` : "no LLM provider configured"} />
          <Dot ok={health ? !!health.has_jev : undefined} label="Jev"
               title={health?.has_jev ? `decision model ${health.jev_model}` : "Jev is not configured: incidents cannot be decided"} />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <nav className={`flex shrink-0 flex-col border-r border-line bg-[#15191e] py-2 transition-[width] duration-150 ${collapsed ? "w-12" : "w-52"}`}>
          {NAV.map((n) => {
            const header = !collapsed && n.group !== lastGroup ? n.group : null;
            lastGroup = n.group;
            return (
              <div key={n.to}>
                {header && <div className="eyebrow px-4 pb-1 pt-3 first:pt-1">{header}</div>}
                <NavLink
                  to={n.to}
                  end={n.to === "/"}
                  title={collapsed ? n.label : undefined}
                  className={({ isActive }) =>
                    `mx-1.5 my-px flex h-8 items-center gap-2.5 rounded-[3px] px-2.5 text-[13px] transition-colors ${isActive
                      ? "bg-accent-soft font-medium text-ink shadow-[inset_2px_0_0] shadow-accent"
                      : "text-muted hover:bg-hover hover:text-ink"}`
                  }
                >
                  <Icon name={n.icon} size={16} />
                  {!collapsed && <span className="truncate">{n.label}</span>}
                </NavLink>
              </div>
            );
          })}
          <div className="mt-auto px-3 pt-2 text-[10.5px] text-slate-600">
            {!collapsed && <span>Supply-chain knowledge graph · FalkorDB</span>}
          </div>
        </nav>

        <main key={loc.pathname.split("/")[1]} className="min-w-0 flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/onboarding" element={<Padded><Onboarding /></Padded>} />
            <Route path="/ontology" element={<Ontology />} />
            <Route path="/ontology/types/:label" element={<OntologyType />} />
            <Route path="/objects" element={<Objects />} />
            <Route path="/objects/:label" element={<Objects />} />
            <Route path="/objects/:label/:id" element={<Objects />} />
            <Route path="/graph" element={<Graph />} />
            <Route path="/workspace" element={<Workspace />} />
            <Route path="/experts" element={<Experts />} />
            <Route path="/incidents" element={<Incidents />} />
          </Routes>
        </main>
      </div>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </div>
  );
}

function Padded({ children }: { children: ReactNode }) {
  return <div className="p-5">{children}</div>;
}
