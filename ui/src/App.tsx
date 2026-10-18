import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, getTenant, setTenant } from "./api";
import type { Employee, Health, TenantRow } from "./api";
import CommandPalette from "./components/CommandPalette";
import { Icon } from "./components/icons";
import { Kbd } from "./components/ui";
import About from "./pages/About";
import Experts from "./pages/Experts";
import Graph from "./pages/Graph";
import Home from "./pages/Home";
import Landing from "./pages/Landing";
import Incidents from "./pages/Incidents";
import Objects from "./pages/Objects";
import Onboarding from "./pages/Onboarding";
import Ontology from "./pages/Ontology";
import Workspace, { Avatar } from "./pages/Workspace";
import OntologyType from "./pages/OntologyType";
import { useOntology } from "./useOntology";
import { usePersona } from "./usePersona";

const NAV: { to: string; label: string; icon: string; group: string }[] = [
  { to: "/overview", label: "Overview", icon: "layers", group: "Home" },
  { to: "/workspace", label: "My workspace", icon: "users", group: "Home" },
  { to: "/onboarding", label: "Onboarding", icon: "chat", group: "Build" },
  { to: "/ontology", label: "Ontology", icon: "schema", group: "Build" },
  { to: "/objects", label: "Object explorer", icon: "table", group: "Explore" },
  { to: "/graph", label: "Graph", icon: "graph", group: "Explore" },
  { to: "/experts", label: "Experts", icon: "experts", group: "Operate" },
  { to: "/incidents", label: "Incidents", icon: "incident", group: "Operate" },
  { to: "/about", label: "About us", icon: "users", group: "Project" },
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
    <span className="micro flex items-center gap-1.5 text-faint" title={title}>
      <span className={`h-1.5 w-1.5 ${ok ? "bg-emerald-400" : ok === false ? "bg-rose-400" : "bg-slate-600"}`} />
      {label}
    </span>
  );
}

function Logo() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.5" aria-hidden>
      <circle cx="12" cy="12" r="2.5" />
      <circle cx="12" cy="12" r="6.5" opacity=".7" />
      <circle cx="12" cy="12" r="10.5" opacity=".4" />
    </svg>
  );
}

/** The landing page stands on its own; every other route lives inside the app shell. */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="*" element={<Shell />} />
    </Routes>
  );
}

function Shell() {
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

  // onboarding (or anything else) changed the active company: pick it up and refresh the list
  useEffect(() => {
    const sync = () => {
      setCurrent(getTenant());
      api.tenants().then(setTenants).catch(() => undefined);
    };
    window.addEventListener("ripple:tenant", sync);
    return () => window.removeEventListener("ripple:tenant", sync);
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

  // the server removes both graphs and the tenant's files; if it was the active company, fall back to another
  const deleteTenant = async (id: string) => {
    await api.deleteTenant(id);
    const rest = tenants.filter((t) => t.id !== id);
    if (id === getTenant()) {
      const next = rest[0]?.id ?? "";
      setTenant(next);
      if (next) await api.selectTenant(next).catch(() => undefined);
      window.location.reload();
    } else {
      setTenants(rest);
    }
  };

  const tenant = tenants.find((t) => t.id === current) ?? (tenants.length === 1 ? tenants[0] : undefined);
  const ontoStatus = view?.has_approved ? `v${view.approved_version} approved` : view?.row?.version ? `v${view.row.version} draft` : null;
  let lastGroup = "";

  return (
    <div className="flex h-full flex-col bg-canvas text-body">
      <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-[#0b0c0e] px-3">
        <button onClick={toggleRail} className="p-1 text-faint hover:text-ink" title="Toggle navigation">
          <Icon name="menu" size={16} />
        </button>
        <NavLink to="/" title="Ripple home" className="flex items-center gap-2">
          <Logo />
          <span className="text-[15px] font-medium tracking-tight text-white">Ripple</span>
        </NavLink>
        <span className="h-5 w-px bg-line-strong" />
        <div className="flex min-w-0 items-center gap-3 text-[12.5px]">
          <CompanyMenu
            tenants={tenants}
            current={tenant?.id ?? current}
            onPick={(id) => void switchTenant(id)}
            onDelete={deleteTenant}
          />
          {ontoStatus && (
            <span className="micro hidden items-center gap-1.5 whitespace-nowrap text-faint md:flex">
              <span className={`h-1.5 w-1.5 ${view?.has_approved ? "bg-emerald-400" : "bg-amber-400"}`} />
              ontology {ontoStatus}
            </span>
          )}
        </div>

        <NavLink to="/workspace" title={me ? `Viewing as ${me.name}` : "Pick who you are"}
                 className="ml-auto flex h-8 items-center gap-2 px-1.5 text-[12.5px] text-muted hover:text-ink">
          {me ? <Avatar name={me.name} size={20} /> : <Icon name="user" size={14} />}
          <span className="hidden max-w-[10rem] truncate sm:inline">{me ? me.name : "Who are you?"}</span>
        </NavLink>
        <button
          onClick={() => setPalette(true)}
          className="flex h-8 w-[min(340px,38vw)] items-center gap-2 border border-line-strong px-2.5 text-left text-[12.5px] text-faint hover:border-white/40"
        >
          <Icon name="search" size={13} />
          <span className="flex-1 truncate">Search objects, types…</span>
          <Kbd>/</Kbd>
        </button>

        <div className="hidden items-center gap-4 border-l border-line pl-4 lg:flex">
          <Dot ok={health?.ok} label={health ? `DB ${health.db_mode}` : "DB"} title="FalkorDB connection" />
          <Dot ok={health ? health.has_llm : undefined} label="LLM"
               title={health?.has_llm ? `${health.llm_provider} · ${health.model}` : "no LLM provider configured"} />
          <Dot ok={health ? !!health.has_jev : undefined} label="Jev"
               title={health?.has_jev ? `decision model ${health.jev_model}` : "Jev is not configured: incidents cannot be decided"} />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <nav className={`flex shrink-0 flex-col border-r border-line bg-[#0b0c0e] py-2 transition-[width] duration-150 ${collapsed ? "w-12" : "w-52"}`}>
          {NAV.map((n) => {
            const header = !collapsed && n.group !== lastGroup ? n.group : null;
            lastGroup = n.group;
            return (
              <div key={n.to}>
                {header && <div className="eyebrow px-5 pb-1.5 pt-4 first:pt-2">{header}</div>}
                <NavLink
                  to={n.to}
                  end={n.to === "/"}
                  title={collapsed ? n.label : undefined}
                  className={({ isActive }) =>
                    `flex h-8 items-center gap-3 border-l px-[18px] text-[13px] transition-colors ${isActive
                      ? "border-ink text-ink"
                      : "border-transparent text-faint hover:text-body"}`
                  }
                >
                  <Icon name={n.icon} size={15} strokeWidth={1.5} />
                  {!collapsed && <span className="truncate">{n.label}</span>}
                </NavLink>
              </div>
            );
          })}
          <div className="micro mt-auto px-5 pt-2 !text-[9.5px] leading-relaxed text-slate-600">
            {!collapsed && <span>Supply-chain knowledge graph · FalkorDB</span>}
          </div>
        </nav>

        <main key={loc.pathname.split("/")[1]} className="min-w-0 flex-1 overflow-auto">
          <Routes>
            <Route path="/overview" element={<Home />} />
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
            <Route path="/about" element={<About />} />
          </Routes>
        </main>
      </div>
      <CommandPalette open={palette} onClose={() => setPalette(false)} />
    </div>
  );
}

function CompanyMenu({
  tenants,
  current,
  onPick,
  onDelete,
}: {
  tenants: TenantRow[];
  current: string;
  onPick: (id: string) => void;
  onDelete: (id: string) => Promise<void>;
}) {
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const close = () => {
    setOpen(false);
    setConfirming(null);
    setError("");
  };
  const remove = async (id: string) => {
    setBusy(true);
    setError("");
    try {
      await onDelete(id);
      setConfirming(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  };
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) close();
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  const active = tenants.find((t) => t.id === current);
  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => (open ? close() : setOpen(true))}
        className="flex max-w-[16rem] items-center gap-1.5 border border-line-strong px-2 py-0.5 text-ink hover:border-white/40"
        title="Switch company"
      >
        <span className="truncate">{active ? active.name ?? active.id : tenants.length ? "Select a company…" : "No company yet"}</span>
        <Icon name="chevronDown" size={12} />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 max-h-72 min-w-full w-64 overflow-auto border border-line-strong bg-panel py-1 shadow-lg">
          {tenants.length === 0 && <div className="px-3 py-2 text-faint">No companies yet</div>}
          {tenants.map((t) =>
            confirming === t.id ? (
              <div key={t.id} className="border-y border-red-500/40 bg-red-500/5 px-3 py-2">
                <div className="text-ink">Delete {t.name ?? t.id}?</div>
                <div className="mt-0.5 text-faint">
                  This permanently removes its graph
                  {t.nodes != null ? ` (${t.nodes} nodes, ${t.edges ?? 0} edges)` : ""}, experts and uploaded files. It cannot be undone.
                </div>
                {error && <div className="mt-1 text-red-400">{error}</div>}
                <div className="mt-2 flex justify-end gap-2">
                  <button
                    disabled={busy}
                    onClick={() => {
                      setConfirming(null);
                      setError("");
                    }}
                    className="border border-line-strong px-2 py-0.5 text-muted hover:text-ink disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => void remove(t.id)}
                    className="border border-red-500/60 bg-red-500/10 px-2 py-0.5 text-red-300 hover:bg-red-500/20 disabled:opacity-50"
                  >
                    {busy ? "Deleting…" : "Delete"}
                  </button>
                </div>
              </div>
            ) : (
              <div key={t.id} className={`group flex items-center hover:bg-white/5 ${t.id === current ? "text-ink" : "text-muted"}`}>
                <button
                  onClick={() => {
                    close();
                    if (t.id !== current) onPick(t.id);
                  }}
                  className="flex min-w-0 flex-1 items-center justify-between gap-2 px-3 py-1.5 text-left"
                >
                  <span className="truncate">{t.name ?? t.id}</span>
                  {t.id === current && <span className="h-1.5 w-1.5 shrink-0 bg-emerald-400" />}
                </button>
                <button
                  onClick={() => {
                    setError("");
                    setConfirming(t.id);
                  }}
                  title={`Delete ${t.name ?? t.id}`}
                  aria-label={`Delete ${t.name ?? t.id}`}
                  className="px-2 py-1.5 text-faint opacity-0 hover:text-red-400 focus:opacity-100 group-hover:opacity-100"
                >
                  <Icon name="trash" size={13} />
                </button>
              </div>
            ),
          )}
          <button
            onClick={() => {
              close();
              nav("/onboarding?new=1");
            }}
            className="flex w-full items-center gap-2 border-t border-line-strong px-3 py-1.5 text-left text-sky-400 hover:bg-white/5"
          >
            <span className="text-base leading-none">+</span> New company
          </button>
        </div>
      )}
    </div>
  );
}

function Padded({ children }: { children: ReactNode }) {
  return <div className="p-5">{children}</div>;
}
