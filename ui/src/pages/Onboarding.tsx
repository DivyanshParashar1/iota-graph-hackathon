import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, getTenant, setTenant, streamSteps } from "../api";
import type { Answer, Brief, SessionState, Stage, Step } from "../api";
import Composer from "../components/Chat/Composer";
import StageRail from "../components/Chat/StageRail";
import StepStream from "../components/Chat/StepStream";
import Thread from "../components/Chat/Thread";
import { Btn, Card, Chip, ErrorLine } from "../components/ui";

/** The whole four-stage onboarding experience: the thread, the stage rail and the live agent trail. */
export default function Onboarding() {
  const [state, setState] = useState<SessionState | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  const lastSeq = useRef(0);
  const seenSteps = useRef(new Set<string>());

  const load = useCallback(async () => {
    try {
      const s = await api.session();
      setState(s);
      setError(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setState(null);
      else setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // A turn running on the server (started by another tab, or before a reload): poll until it replies.
  useEffect(() => {
    if (!state?.busy || busy) return;
    const t = window.setInterval(() => void load(), 3000);
    return () => window.clearInterval(t);
  }, [state?.busy, busy, load]);

  // the live step stream: it replays history on connect, so a reload rebuilds the trail. EventSource reconnects
  // on its own with the URL it was opened with, which replays that history again: skip what is already shown.
  useEffect(() => {
    if (!state?.tenant?.id) return;
    const stop = streamSteps(lastSeq.current, (s) => {
      const key = `${s.seq}:${s.ts}`;
      if (seenSteps.current.has(key)) return;
      seenSteps.current.add(key);
      lastSeq.current = Math.max(lastSeq.current, s.seq);
      if (s.stage === "workspace") return; // the workspace chat has its own trail
      setSteps((prev) => [...prev.slice(-400), s]);
    });
    return stop;
  }, [state?.tenant?.id]);

  const run = async (fn: () => Promise<{ state: SessionState }>) => {
    setBusy(true);
    setError(null);
    try {
      const out = await fn();
      setState(out.state);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      await load();
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="p-6 text-sm text-slate-500">loading…</div>;
  if (!state) return <StartCard onStarted={(s) => setState(s)} />;

  const stage = state.stage;
  const brief = state.artifacts.brief.data;

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
      <div className="flex min-w-0 flex-col gap-3">
        <StageRail
          stages={state.progress.stages}
          disabled={busy || state.busy}
          onGoto={(s: Stage) => void run(() => api.goto(s))}
        />
        <ErrorLine error={error} />
        {state.busy && !busy ? (
          <div className="micro flex items-center gap-2 py-1 text-muted">
            <span className="h-1.5 w-1.5 animate-pulse bg-violet-400" />
            The {(state.pending?.agent ?? "agent").replace(/_/g, " ")} is working. This page updates when it replies.
          </div>
        ) : state.pending && !busy && (
          <div className="flex items-center gap-3 border-l border-amber-400 py-1 pl-3 text-[12.5px] text-amber-200">
            A turn was interrupted.
            <Btn onClick={() => void run(async () => await api.resume())}>Resume it</Btn>
          </div>
        )}
        <Card>
          <Thread
            messages={state.messages}
            answers={state.answers}
            openForm={state.open_form}
            attachments={state.attachments}
            busy={busy || state.busy}
            onSubmitted={() => void load()}
            onAnswers={(a: Answer[]) => setState((s) => (s ? { ...s, answers: a } : s))}
          />
        </Card>
        {stage === "ontology" && (
          <Handoff
            text="The ontology agent has drafted your graph model."
            action="Review and approve it"
            onClick={() => nav("/ontology")}
          />
        )}
        {stage === "experts" && (
          <Handoff
            text="Your expert roles are drafted."
            action="Review and approve them"
            onClick={() => nav("/experts")}
          />
        )}
        {stage !== "ready" ? (
          <Composer
            disabled={busy || state.busy}
            onSent={async (text) => {
              setBusy(true);
              try {
                const out = await api.send(text);
                setState(out.state);
              } finally {
                setBusy(false);
              }
            }}
            onUploaded={load}
          />
        ) : (
          <div className="flex flex-wrap items-center gap-3 border-l border-emerald-400 py-1.5 pl-4 text-[13px] text-body">
            Onboarding is done — {state.tenant.name} is live.
            <Btn onClick={() => nav("/experts")}>Ask an expert</Btn>
            <Btn kind="ghost" onClick={() => void run(async () => await api.reonboard("What has changed?"))}>
              Re-onboard
            </Btn>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <Card title="Agent trail" right={<span className="text-[11px] text-slate-500">{steps.length} steps</span>}>
          <StepStream steps={steps} />
        </Card>
        {brief && <BriefCard brief={brief} version={state.artifacts.brief.version} stale={state.artifacts.brief.stale} />}
        {!!state.attachments.length && (
          <Card title="Uploads">
            <ul className="flex flex-col gap-1 text-xs">
              {state.attachments.map((a) => (
                <li key={a.id} className="flex items-center gap-2">
                  <Chip color={a.kind === "table" ? "bg-sky-900" : "bg-slate-800"}>{a.kind}</Chip>
                  <span className="truncate text-slate-300">{a.filename}</span>
                  <span className="ml-auto shrink-0 text-slate-600">{Math.round(a.bytes / 1024)} kB</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </div>
  );
}

function Handoff({ text, action, onClick }: { text: string; action: string; onClick: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-3 border-l border-ink py-1.5 pl-4 text-[13px] text-body">
      {text}
      <Btn kind="primary" onClick={onClick}>
        {action}
      </Btn>
    </div>
  );
}

function StartCard({ onStarted }: { onStarted: (s: SessionState) => void }) {
  const [company, setCompany] = useState("");
  const [industry, setIndustry] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [known, setKnown] = useState<{ id: string; name?: string; stage?: string }[]>([]);

  useEffect(() => {
    api.tenants().then(setKnown).catch(() => undefined);
  }, []);

  const start = async () => {
    if (!company.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const s = await api.start(company.trim(), industry.trim());
      if (s.tenant_id) setTenant(s.tenant_id);
      onStarted(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4 py-10">
      <div>
        <div className="micro slide-in text-sky-400">Onboarding</div>
        <h1 className="rise mt-1 text-3xl font-light tracking-tight text-slate-50">Tell Ripple about your company</h1>
        <p className="mt-1 text-sm text-slate-400">
          Four agents will interview you, ask for the data they need, design your knowledge graph and then write
          the expert agents your supply chain needs. Nothing is pre-built: the model is yours.
        </p>
      </div>
      <Card>
        <div className="flex flex-col gap-3">
          <label className="block">
            <span className="text-xs font-medium text-slate-300">Company name</span>
            <input
              autoFocus
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void start()}
              placeholder="Acme Shoes"
              className="mt-1 w-full border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-100 focus:border-sky-600 focus:outline-none"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-slate-300">Industry (optional)</span>
            <input
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void start()}
              placeholder="footwear"
              className="mt-1 w-full border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-100 focus:border-sky-600 focus:outline-none"
            />
          </label>
          <ErrorLine error={error} />
          <Btn kind="primary" onClick={start} disabled={busy || !company.trim()}>
            {busy ? "the interviewer is starting…" : "Start onboarding"}
          </Btn>
        </div>
      </Card>
      {!!known.length && (
        <Card title="Or pick up where a company left off">
          <ul className="flex flex-col gap-1 text-sm">
            {known.map((t) => (
              <li key={t.id}>
                <button
                  onClick={async () => {
                    setTenant(t.id);
                    await api.selectTenant(t.id).catch(() => undefined);
                    onStarted(await api.session());
                  }}
                  className="flex w-full items-center gap-2 px-2 py-1 text-left hover:bg-slate-800"
                >
                  <span className="text-slate-200">{t.name ?? t.id}</span>
                  <Chip color="bg-slate-800">{t.stage}</Chip>
                  <span className="ml-auto font-mono text-[11px] text-slate-600">{t.id}</span>
                </button>
              </li>
            ))}
          </ul>
          {getTenant() && <p className="mt-2 text-[11px] text-slate-600">this browser remembers {getTenant()}</p>}
        </Card>
      )}
    </div>
  );
}

function BriefCard({ brief, version, stale }: { brief: Brief; version?: number; stale?: boolean }) {
  const rows: [string, string][] = [
    ["Industry", brief.industry],
    ["Scale", brief.scale],
    ["Products", brief.products.map((p) => p.name).join(", ")],
    ["Suppliers", brief.suppliers.map((s) => s.name || s.kind).join(", ")],
    ["Sites", brief.sites.map((s) => s.name || s.kind).join(", ")],
    ["Modes", brief.transport_modes.join(", ")],
    ["Markets", brief.markets.join(", ")],
    ["Pains", brief.pains.join("; ")],
    ["Risks", brief.risks.join("; ")],
  ];
  return (
    <Card
      title="Brief"
      right={
        <span className="flex items-center gap-1 text-[11px] text-slate-500">
          {version ? `v${version}` : ""}
          {stale ? <Chip color="bg-amber-800">stale</Chip> : null}
        </span>
      }
    >
      {brief.summary && <p className="mb-2 text-xs text-slate-300">{brief.summary}</p>}
      <dl className="flex flex-col gap-1 text-[11px]">
        {rows
          .filter(([, v]) => v)
          .map(([k, v]) => (
            <div key={k} className="flex gap-2">
              <dt className="w-16 shrink-0 text-slate-500">{k}</dt>
              <dd className="min-w-0 break-words text-slate-300">{v}</dd>
            </div>
          ))}
      </dl>
    </Card>
  );
}
