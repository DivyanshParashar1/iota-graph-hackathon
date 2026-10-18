import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, streamSteps } from "../api";
import type { Delegation, Employee, ExpertRole, Step, WsDashboard, WsMessage, WsThread } from "../api";
import { Icon } from "../components/icons";
import Markdown from "../components/Markdown";
import {
  Btn, Callout, EmptyState, Meter, PageHeader, Panel, Tag, TypeIcon, TypeTag, statusIntent,
} from "../components/ui";
import { human, plural } from "../ontologyText";
import { useOntology } from "../useOntology";
import { usePersona } from "../usePersona";

/** A person's workspace: pick who you are, see the dashboard scoped to your roles, and talk to the
 *  orchestrator, which deploys the expert agents to answer. */
export default function Workspace() {
  const [persona, setPersona] = usePersona();
  const [employees, setEmployees] = useState<Employee[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() =>
    api.employees().then((r) => setEmployees(r.employees)).catch((e: Error) => setError(e.message)), []);
  useEffect(() => { void load(); }, [load]);

  if (error) return <div className="p-6"><Callout intent="danger" title="Could not load the workspace">{error}</Callout></div>;
  if (!employees) return <div className="p-6 text-[12px] text-faint">Loading…</div>;
  const me = employees.find((e) => e.id === persona);
  if (!me) return <Picker employees={employees} onPick={setPersona} onChanged={load} />;
  return <Dashboard key={me.id} employee={me} onSwitch={() => setPersona("")} onChanged={load} />;
}

export function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");
}

/** A person's initials in a hairline square. */
export function Avatar({ name, size = 32 }: { name: string; size?: number }) {
  return (
    <span className="inline-flex shrink-0 items-center justify-center border border-line-strong font-medium tracking-wide text-ink"
          style={{ width: size, height: size, fontSize: size * 0.36 }}>
      {initials(name)}
    </span>
  );
}

// --------------------------------------------------------------------------- choose who you are

function Picker({ employees, onPick, onChanged }: { employees: Employee[]; onPick: (id: string) => void; onChanged: () => Promise<void> | void }) {
  const [adding, setAdding] = useState(employees.length === 0);
  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        crumbs={[{ label: "My workspace" }]}
        title="Who are you?"
        subtitle="Pick your profile to open a dashboard scoped to your roles and a chat with the agent team."
        right={<Btn kind="primary" icon="sparkle" onClick={() => setAdding((a) => !a)}>{adding ? "Close form" : "Add a person"}</Btn>}
      />
      <div className="flex flex-col gap-3 p-4">
        {adding && <EmployeeEditor onDone={async (e) => {
          if (e) await onChanged(); // refresh first, so the new person exists when we open their workspace
          setAdding(false);
          if (e) onPick(e.id);
        }} />}
        {employees.length === 0 && !adding ? (
          <EmptyState icon="users" title="No people yet">Add the people who will use Ripple and the expert roles each one works as.</EmptyState>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {employees.map((e) => (
              <button key={e.id} onClick={() => onPick(e.id)}
                      className="flex items-start gap-3 border border-line bg-panel p-4 text-left transition-colors hover:border-line-strong hover:bg-raised">
                <Avatar name={e.name} size={40} />
                <div className="min-w-0 flex-1">
                  <div className="text-[14px] font-semibold text-ink">{e.name}</div>
                  <div className="text-[12px] text-muted">{e.title || "No title"}</div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {(e.roles ?? []).map((r) => <Tag key={r.id} intent="info" icon="experts">{r.title}</Tag>)}
                    {!(e.roles ?? []).length && <span className="text-[11px] text-faint">No roles assigned</span>}
                  </div>
                </div>
                <Icon name="chevronRight" size={16} className="mt-2 text-slate-500" />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function EmployeeEditor({ employee, onDone }: { employee?: Employee; onDone: (e?: Employee) => void | Promise<void> }) {
  const [roles, setRoles] = useState<ExpertRole[]>([]);
  const [name, setName] = useState(employee?.name ?? "");
  const [title, setTitle] = useState(employee?.title ?? "");
  const [picked, setPicked] = useState<string[]>(employee?.role_ids ?? []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.experts().then((r) => setRoles(r.experts.filter((x) => x.status !== "retired"))).catch(() => setRoles([]));
  }, []);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = { name, title, role_ids: picked };
      const e = employee ? await api.editEmployee(employee.id, body) : await api.createEmployee(body);
      setSaved(true);
      await onDone(e);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title={employee ? `Edit ${employee.name}` : "Add a person"} icon="user"
           right={<Btn small kind="minimal" icon="close" onClick={() => onDone()} />}>
      <div className="flex flex-col gap-3 p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Name</span>
            <input className="field h-8 text-[13px]" value={name} onChange={(e) => setName(e.target.value)} placeholder="Maya Chen" autoFocus />
          </label>
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Job title</span>
            <input className="field h-8 text-[13px]" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Head of logistics" />
          </label>
        </div>
        <div>
          <div className="eyebrow mb-1.5">Works as (expert roles)</div>
          {roles.length === 0 ? <div className="text-[12px] text-faint">No expert roles yet: they are generated once the ontology is approved.</div> : (
            <div className="grid gap-1.5 md:grid-cols-2">
              {roles.map((r) => {
                const on = picked.includes(r.id);
                return (
                  <button key={r.id} onClick={() => setPicked(on ? picked.filter((x) => x !== r.id) : [...picked, r.id])}
                          className={`flex items-start gap-2 border px-2.5 py-2 text-left ${on ? "border-ink" : "border-line hover:border-line-strong"}`}>
                    <span className={`mt-0.5 flex h-3.5 w-3.5 shrink-0 items-center justify-center border ${on ? "border-ink bg-ink text-black" : "border-line-strong"}`}>
                      {on && <Icon name="check" size={10} className="text-black" strokeWidth={3} />}
                    </span>
                    <span className="min-w-0">
                      <span className="block text-[12.5px] font-medium text-ink">{r.title}</span>
                      <span className="line-clamp-2 text-[11px] text-faint">{r.mandate}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
        {error && <Callout intent="danger">{error}</Callout>}
        <div className="flex justify-end gap-2">
          <Btn kind="ghost" onClick={() => onDone()}>Cancel</Btn>
          <Btn kind="primary" icon="check" onClick={() => void save()} disabled={busy || !name.trim()}>{saved ? "Saved, opening…" : busy ? "Saving…" : "Save"}</Btn>
        </div>
      </div>
    </Panel>
  );
}

// --------------------------------------------------------------------------- the dashboard

function Dashboard({ employee, onSwitch, onChanged }: { employee: Employee; onSwitch: () => void; onChanged: () => void }) {
  const [dash, setDash] = useState<WsDashboard | null>(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { style } = useOntology();

  const load = useCallback(() => {
    api.dashboard(employee.id).then(setDash).catch((e: Error) => setError(e.message));
  }, [employee.id]);
  useEffect(load, [load]);

  return (
    <div className="flex h-full min-h-[680px] flex-col">
      <PageHeader
        crumbs={[{ label: "My workspace", to: "/workspace" }, { label: employee.name }]}
        icon={<Avatar name={employee.name} size={40} />}
        title={employee.name}
        subtitle={<span className="flex flex-wrap items-center gap-1.5">
          <span>{employee.title || "No title"}</span>
          {dash?.roles.map((r) => <Tag key={r.id} intent="info" icon="experts">{r.title}</Tag>)}
        </span>}
        right={<>
          <Btn kind="ghost" icon="document" onClick={() => setEditing(!editing)}>Edit profile</Btn>
          <Btn kind="ghost" icon="users" onClick={onSwitch}>Switch person</Btn>
        </>}
      />
      {editing && (
        <div className="p-3 pb-0">
          <EmployeeEditor employee={employee} onDone={(e) => { setEditing(false); if (e) { onChanged(); load(); } }} />
        </div>
      )}
      {error && <div className="p-3"><Callout intent="danger">{error}</Callout></div>}
      <div className="grid min-h-0 flex-1 gap-3 p-3 xl:grid-cols-[380px_minmax(0,1fr)]">
        <div className="flex min-h-0 flex-col gap-3 overflow-auto">
          <Panel title="Your focus" icon="layers" count={dash?.focus_types.length ?? 0} className="shrink-0">
            <div className="flex flex-col gap-1 p-2">
              {!dash?.focus_types.length && <div className="p-2 text-[12px] text-faint">No roles assigned, so nothing is in focus. Edit your profile to pick roles.</div>}
              {dash?.focus_types.map((t) => {
                const s = style(t);
                return (
                  <Link key={t} to={`/objects/${encodeURIComponent(t)}`} className="flex items-center gap-2 px-2 py-1.5 hover:bg-hover">
                    <TypeIcon label={t} color={s.color} icon={s.icon} size={22} />
                    <span className="flex-1 text-[12.5px] text-ink">{human(t)}</span>
                    <span className="text-[12px] tabular-nums text-muted">{(dash.counts[t] ?? 0).toLocaleString()}</span>
                  </Link>
                );
              })}
            </div>
          </Panel>
          <Panel title="Your hot spots" icon="alert" count={dash?.hotspots.length ?? 0} className="shrink-0">
            {!dash?.hotspots.length ? <EmptyState icon="check" title="Nothing flagged in your area" /> : (
              <ul className="divide-y divide-line">
                {dash.hotspots.slice(0, 6).map((h, i) => {
                  const label = h.kind === "status" ? h.label! : h.to!;
                  const n = h.kind === "status" ? h.count! : h.single!;
                  const ratio = n / Math.max(h.total, 1);
                  const s = style(label);
                  return (
                    <li key={i} className="flex gap-2.5 px-3 py-2.5">
                      <TypeIcon label={label} color={s.color} icon={s.icon} size={22} />
                      <div className="min-w-0 flex-1">
                        <div className="text-[12px] text-ink">
                          {h.kind === "status"
                            ? <>{n} of {h.total} {plural(label)}: {human(h.property!).replace(/_/g, " ")} <b className="text-amber-200">{h.value}</b></>
                            : <>{n} of {h.total} {plural(label)} linked to only one {human(h.from!)}</>}
                        </div>
                        <Meter value={ratio} tone={ratio >= 0.25 ? "bg-rose-500" : "bg-amber-500"} className="mt-1.5" />
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>
          <Panel title="Incidents" icon="incident" count={dash?.incidents.length ?? 0} className="shrink-0"
                 right={<Link to="/incidents" className="link text-[11.5px]">Open</Link>}>
            {!dash?.incidents.length ? <EmptyState icon="incident" title="No incidents" /> : (
              <ul className="flex flex-col gap-1.5 p-2">
                {dash.incidents.slice(0, 4).map((inc) => (
                  <li key={inc.id} className="border border-line bg-sunken px-2.5 py-2">
                    <Tag intent={statusIntent(inc.status)}>{inc.status.replace(/_/g, " ")}</Tag>
                    <div className="mt-1 text-[12px] leading-snug text-ink">{inc.summary}</div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
        {dash && <Chat employee={employee} dash={dash} onThreads={load} />}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- the orchestrator chat

function Chat({ employee, dash, onThreads }: { employee: Employee; dash: WsDashboard; onThreads: () => void }) {
  const [threads, setThreads] = useState<WsThread[]>(dash.threads);
  const [tid, setTid] = useState<string>(dash.threads[0]?.id ?? "");
  const [messages, setMessages] = useState<WsMessage[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const sentAt = useRef(0);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => setThreads(dash.threads), [dash.threads]);

  useEffect(() => {
    if (!tid) {
      setMessages([]);
      return;
    }
    api.thread(employee.id, tid).then((r) => setMessages(r.messages)).catch(() => setMessages([]));
  }, [employee.id, tid]);

  // the live trail: every workspace step tagged with the thread being answered
  useEffect(() => {
    const stop = streamSteps(0, (s) => {
      if (s.stage === "workspace" && s.ts >= sentAt.current - 1000) setSteps((prev) => [...prev.slice(-200), s]);
    });
    return stop;
  }, []);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, sending, steps.length]);

  const send = async (q = text) => {
    const t = q.trim();
    if (!t || sending) return;
    setSending(true);
    setError(null);
    setText("");
    sentAt.current = Date.now();
    setSteps([]);
    let thread = tid;
    try {
      if (!thread) {
        const th = await api.newThread(employee.id);
        thread = th.id;
        setTid(thread);
        setThreads((prev) => [th, ...prev]);
      }
      setMessages((prev) => [...prev, { id: "pending", role: "user", text: t, seq: 0, ts: Date.now(), payload: {} }]);
      await api.chat(employee.id, t, thread);
      const r = await api.thread(employee.id, thread);
      setMessages(r.messages);
      onThreads();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setMessages((prev) => prev.filter((m) => m.id !== "pending"));
      setText(t);
    } finally {
      setSending(false);
    }
  };

  const live = steps.filter((s) => (s.data as { thread?: string } | null)?.thread === tid);
  const suggestions = useMemo(() => {
    const fromRoles = dash.roles.flatMap((r) => r.playbook.slice(0, 2));
    return [...fromRoles, "What should I worry about this week, across sourcing, plants and customers?"].slice(0, 5);
  }, [dash.roles]);

  return (
    <section className="flex min-h-[560px] overflow-hidden border border-line bg-panel">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-line md:flex">
        <div className="flex h-9 items-center gap-2 border-b border-line px-3">
          <span className="eyebrow !text-muted">Chats</span>
          <Btn small kind="minimal" icon="sparkle" onClick={() => { setTid(""); setMessages([]); setSteps([]); }}>New</Btn>
        </div>
        <ul className="min-h-0 flex-1 overflow-auto p-1.5">
          {threads.map((t) => (
            <li key={t.id} className="group flex items-center">
              <button onClick={() => setTid(t.id)}
                      className={`min-w-0 flex-1 truncate px-2 py-1.5 text-left text-[12px] ${t.id === tid ? "bg-accent-soft text-ink" : "text-muted hover:bg-hover hover:text-ink"}`}>
                {t.title || "New chat"}
              </button>
              <button title="Delete chat" onClick={async () => {
                await api.deleteThread(employee.id, t.id).catch(() => undefined);
                setThreads((p) => p.filter((x) => x.id !== t.id));
                if (t.id === tid) { setTid(""); setMessages([]); }
              }} className="ml-0.5 hidden p-1 text-faint hover:bg-hover hover:text-rose-300 group-hover:block">
                <Icon name="close" size={12} />
              </button>
            </li>
          ))}
          {!threads.length && <li className="px-2 py-2 text-[11.5px] text-faint">No chats yet</li>}
        </ul>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-9 shrink-0 items-center gap-2 border-b border-line px-3">
          <Icon name="sparkle" size={14} className="text-violet-300" />
          <span className="eyebrow !text-muted">Agent team</span>
          <span className="truncate text-[11.5px] text-faint">an orchestrator that deploys {dash.experts.length} expert agents</span>
        </header>

        <div ref={scroller} className="min-h-0 flex-1 overflow-auto px-4 py-4">
          {messages.length === 0 && !sending ? (
            <div className="mx-auto flex max-w-2xl flex-col items-center gap-4 py-8 text-center">
              <Icon name="sparkle" size={22} className="text-slate-500" strokeWidth={1.3} />
              <div>
                <div className="text-[22px] font-light text-ink">Ask the agent team, {employee.name.split(" ")[0]}</div>
                <div className="mt-1 text-[12.5px] text-muted">
                  The orchestrator splits your question across the expert agents, runs them in parallel against the
                  knowledge graph, and brings back one answer with its sources.
                </div>
              </div>
              <div className="flex flex-wrap justify-center gap-1.5">
                {dash.experts.map((x) => <Tag key={x.id} icon="experts" intent={dash.roles.some((r) => r.id === x.id) ? "info" : "none"}>{x.title}</Tag>)}
              </div>
              <div className="flex w-full flex-col gap-1.5">
                {suggestions.map((s) => (
                  <button key={s} onClick={() => void send(s)}
                          className="border border-line-strong bg-raised px-3 py-2 text-left text-[12.5px] text-body hover:border-accent hover:text-ink">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-4">
              {messages.map((m) => m.role === "user" ? (
                <div key={m.id} className="flex justify-end gap-2">
                  <div className="max-w-[80%] border border-line-strong px-3.5 py-2.5 text-[13.5px] text-ink">{m.text}</div>
                  <Avatar name={employee.name} size={26} />
                </div>
              ) : (
                <AssistantMessage key={m.id} m={m} />
              ))}
              {sending && <LiveTrail steps={live} />}
            </div>
          )}
        </div>

        <div className="shrink-0 border-t border-line p-3">
          {error && <div className="mb-2"><Callout intent="danger">{error}</Callout></div>}
          <div className="flex items-end gap-2">
            <textarea
              value={text}
              rows={2}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              disabled={sending}
              placeholder={sending ? "The agent team is working…" : "Ask anything about your supply chain. Enter to send, Shift+Enter for a new line."}
              className="field min-h-[44px] flex-1 resize-none py-2 text-[13px]"
            />
            <Btn kind="primary" icon="arrowRight" onClick={() => void send()} disabled={sending || !text.trim()}>
              {sending ? "Working…" : "Send"}
            </Btn>
          </div>
        </div>
      </div>
    </section>
  );
}

function AssistantMessage({ m }: { m: WsMessage }) {
  const [open, setOpen] = useState(false);
  const del = m.payload.delegations ?? [];
  const queries = del.reduce((a, d) => a + (d.tool_calls || 0), 0);
  return (
    <div className="flex gap-2">
      <span className="mt-1 h-1.5 w-1.5 shrink-0 bg-violet-400" />
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2 text-[11px] text-faint">
          <span className="micro text-muted">Orchestrator</span>
          {m.payload.ok === false && <Tag intent="warning">incomplete</Tag>}
        </div>
        <div className="border-l border-line-strong pl-3.5 text-[13.5px] leading-relaxed text-body">
          <Markdown text={m.text || "(no answer)"} />
        </div>
        {del.length > 0 && (
          <div className="mt-1.5">
            <button onClick={() => setOpen(!open)} className="flex flex-wrap items-center gap-1.5 text-left text-[11.5px] text-muted hover:text-ink">
              <Icon name={open ? "chevronDown" : "chevronRight"} size={12} />
              <span className="whitespace-nowrap">
                Deployed {del.length} expert agent{del.length === 1 ? "" : "s"} · {queries} graph quer{queries === 1 ? "y" : "ies"}
              </span>
              {[...new Set(del.map((d) => d.title))].map((t) => <Tag key={t} intent="info">{t}</Tag>)}
            </button>
            {open && (
              <div className="mt-2 flex flex-col gap-2 border-l-2 border-violet-800 pl-3">
                {del.map((d, i) => <DelegationCard key={i} d={d} />)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function DelegationCard({ d }: { d: Delegation }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-line bg-panel">
      <button onClick={() => setOpen(!open)} className="flex w-full items-start gap-2 px-3 py-2 text-left">
        <Icon name="experts" size={14} className="mt-0.5 text-violet-300" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[12.5px] font-medium text-ink">{d.title}</span>
            {!d.ok && <Tag intent="warning">no clean answer</Tag>}
            <span className="ml-auto text-[10.5px] text-faint">{d.tool_calls} queries · {d.ids.length} objects</span>
          </div>
          <div className="mt-0.5 text-[12px] italic text-muted">“{d.question}”</div>
        </div>
        <Icon name={open ? "chevronDown" : "chevronRight"} size={12} className="mt-1 text-faint" />
      </button>
      {open && (
        <div className="border-t border-line px-3 py-2.5 text-[12.5px] text-body">
          <Markdown text={d.answer || "(no answer)"} />
          {d.ids.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{d.ids.slice(0, 16).map((id) => <Tag key={id} mono>{id}</Tag>)}</div>}
        </div>
      )}
    </div>
  );
}

function LiveTrail({ steps }: { steps: Step[] }) {
  const agents = [...new Set(steps.map((s) => s.agent).filter((a) => a !== "orchestrator"))];
  const last = steps.slice(-6);
  return (
    <div className="flex gap-2">
      <span className="mt-1 h-1.5 w-1.5 shrink-0 animate-pulse bg-violet-400" />
      <div className="min-w-0 flex-1 border-l border-line-strong pl-3.5">
        <div className="text-[12.5px] text-muted">
          {agents.length ? <>Working with {agents.length} expert agent{agents.length === 1 ? "" : "s"}: {agents.map((a) => a.replace(/_/g, " ")).join(", ")}</> : "The orchestrator is planning…"}
        </div>
        {last.length > 0 && (
          <ul className="mt-1.5 flex flex-col gap-0.5 font-mono text-[11px] text-faint">
            {last.map((s) => (
              <li key={`${s.seq}-${s.ts}`} className="truncate">
                <span className="text-violet-300">{s.agent}</span> <span className="text-muted">{s.kind}</span> {s.summary}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
