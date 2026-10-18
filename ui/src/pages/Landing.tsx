import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import { Reveal, mapRange, useInView, useScrollProgress } from "../components/motion";

// The public landing page: a scroll-driven globe hero, then the pitch, the build and decide stages, the SOP from
// interview to decided incident, and what you get. It sits outside the app shell; every other page uses the same language at working scale (components/ui).

// ---------------------------------------------------------------------------- globe
interface Pt {
  lat: number;
  lon: number;
  hot: 0 | 1 | 2 | 3; // 0 plain, 1 yellow, 2 red, 3 teal
}

const rand = (() => {
  let s = 7;
  return () => ((s = (s * 16807) % 2147483647) - 1) / 2147483646;
})();

function buildPoints(): Pt[] {
  const pts: Pt[] = [];
  const N = 2400;
  for (let i = 0; i < N; i++) {
    const lat = Math.asin(1 - (2 * (i + 0.5)) / N);
    const lon = (i * Math.PI * (3 - Math.sqrt(5))) % (Math.PI * 2);
    // pseudo-continents: keep points where a sum of sines is high
    const m = Math.sin(lon * 2 + lat * 3) + Math.sin(lon * 3.3 - lat * 2) * 0.8 + Math.cos(lat * 4 + lon);
    if (m > 0.35) pts.push({ lat, lon, hot: 0 });
  }
  for (let i = 0; i < 150; i++) {
    const lat = Math.asin(rand() * 1.4 - 0.7);
    const lon = rand() * Math.PI * 2;
    const r = rand();
    pts.push({ lat, lon, hot: r < 0.5 ? 1 : r < 0.78 ? 2 : 3 });
  }
  return pts;
}

function Globe() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current;
    const ctx = cv?.getContext("2d");
    if (!cv || !ctx) return;
    const pts = buildPoints();
    const hot = pts.filter((p) => p.hot);
    const lanes = Array.from({ length: 9 }, () => [hot[(rand() * hot.length) | 0], hot[(rand() * hot.length) | 0]] as const);
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const tilt = -0.42;
    let w = 0;
    let h = 0;
    let raf = 0;
    let rot = 1.2;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = cv.clientWidth;
      h = cv.clientHeight;
      cv.width = w * dpr;
      cv.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const proj = (p: Pt, R: number, cx: number, cy: number, lift = 1) => {
      const l = p.lon + rot;
      const x = Math.cos(p.lat) * Math.sin(l);
      const y = Math.sin(p.lat);
      const z = Math.cos(p.lat) * Math.cos(l);
      const y2 = y * Math.cos(tilt) - z * Math.sin(tilt);
      const z2 = y * Math.sin(tilt) + z * Math.cos(tilt);
      return { x: cx + x * R * lift, y: cy - y2 * R * lift, z: z2 };
    };
    const colors = ["", "#e8d44d", "#ef4444", "#2dd4bf"];

    const draw = (t: number) => {
      ctx.clearRect(0, 0, w, h);
      const R = Math.max(w * 0.62, h * 0.9);
      const cx = w / 2;
      const cy = h * 0.58 + R;
      // atmosphere rim
      const g = ctx.createRadialGradient(cx, cy, R * 0.97, cx, cy, R * 1.04);
      g.addColorStop(0, "rgba(120,170,255,0.0)");
      g.addColorStop(0.55, "rgba(150,195,255,0.55)");
      g.addColorStop(1, "rgba(120,170,255,0)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(cx, cy, R * 1.04, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#05070a";
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.fill();

      for (const p of pts) {
        const q = proj(p, R, cx, cy);
        if (q.z <= 0 || q.y > h + 10) continue;
        if (p.hot) {
          ctx.fillStyle = colors[p.hot];
          ctx.globalAlpha = 0.5 + 0.5 * q.z;
          ctx.beginPath();
          ctx.arc(q.x, q.y, 2.2 + (p.hot === 2 ? Math.sin(t / 400 + p.lon * 9) * 0.8 : 0), 0, Math.PI * 2);
          ctx.fill();
        } else {
          ctx.fillStyle = "#8a93a0";
          ctx.globalAlpha = 0.2 + 0.5 * q.z;
          ctx.fillRect(q.x, q.y, 1.7, 1.7);
        }
      }
      // lanes: arcs lifted off the surface, with a travelling pulse
      ctx.globalAlpha = 1;
      lanes.forEach(([a, b], i) => {
        const A = proj(a, R, cx, cy);
        const B = proj(b, R, cx, cy);
        if (A.z <= 0 || B.z <= 0) return;
        const M = proj({ lat: (a.lat + b.lat) / 2, lon: (a.lon + b.lon) / 2, hot: 0 }, R, cx, cy, 1.18);
        ctx.strokeStyle = "rgba(120,180,255,0.35)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(A.x, A.y);
        ctx.quadraticCurveTo(M.x, M.y, B.x, B.y);
        ctx.stroke();
        const u = ((t / 2600 + i * 0.37) % 1);
        const x = (1 - u) * (1 - u) * A.x + 2 * (1 - u) * u * M.x + u * u * B.x;
        const y = (1 - u) * (1 - u) * A.y + 2 * (1 - u) * u * M.y + u * u * B.y;
        ctx.fillStyle = "#bfe0ff";
        ctx.beginPath();
        ctx.arc(x, y, 2, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1;
    };
    const loop = (t: number) => {
      rot += 0.0009;
      draw(t);
      raf = requestAnimationFrame(loop);
    };
    resize();
    draw(0);
    if (!still) raf = requestAnimationFrame(loop);
    const onVis = () => {
      cancelAnimationFrame(raf);
      if (!document.hidden && !still) raf = requestAnimationFrame(loop);
    };
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", onVis);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);
  return <canvas ref={ref} className="h-full w-full" />;
}


// ---------------------------------------------------------------------------- left "board" panel
const BOARD = [
  { kind: "Vessel", name: "MSC Aurora", note: "Port closure · Ningbo", tag: "REROUTE", p: "P1" },
  { kind: "Supplier", name: "Shenzhen Volt Components", note: "Single source · Li-ion pack", tag: "BACKUP?", p: "P1" },
  { kind: "Lane", name: "Shanghai → Rotterdam", note: "+9 days transit", tag: "TRACK", p: "P2" },
  { kind: "Plant", name: "Da Nang Cutting", note: "Capacity 82%", tag: "WATCH", p: "P2" },
  { kind: "Contract", name: "Wholesale SLA · 2%/day", note: "Penalty exposure $41k", tag: "ENGAGE", p: "P1" },
  { kind: "Vessel", name: "Maersk Elba", note: "ETA slipped 3d", tag: "FIX", p: "P3" },
];

const ease = "cubic-bezier(0.22, 1, 0.36, 1)";
const enter = (name: string, dur: number, delay = 0): CSSProperties => ({ animation: `${name} ${dur}s ${ease} ${delay}s both` });

function Board() {
  return (
    <div className="w-[22rem] border border-white/10 bg-black/50 backdrop-blur-sm">
      <div className="micro flex items-center justify-between border-b border-white/10 px-3 py-2 text-slate-400">
        <span>Risk board</span>
        <span className="text-slate-600">Illustrative</span>
      </div>
      <ul>
        {BOARD.map((b, i) => (
          <li key={b.name} style={enter("slide-in", 0.5, 1.1 + i * 0.12)} className="border-b border-white/5 px-3 py-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[13px] text-slate-200">{b.name}</span>
              <span className={`micro ${b.p === "P1" ? "text-rose-400" : "text-slate-500"}`}>{b.p}</span>
            </div>
            <div className="mt-0.5 flex items-center justify-between text-[11px] text-slate-500">
              <span>
                {b.kind} · {b.note}
              </span>
              <span className="micro text-sky-400/80">{b.tag}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------- content
// The two halves of the product: onboarding builds a company's graph and experts once; incidents run on it daily.
const PHASES = [
  {
    kicker: "Build the brain",
    note: "Onboarding: four agents, one conversation",
    stages: [
      ["Interview", "A product-manager agent learns your business by conversation and attached files, then writes the Supply Chain Brief."],
      ["Data", "Forms appear inside the chat for the exact numbers needed. Unknowns become labelled ballparks, never inventions."],
      ["Ontology", "A graph model designed for your company, reviewed as a diagram and a table, then loaded into FalkorDB on approval."],
      ["Experts", "Expert agents invented for your chain, each justified against the ontology, each with a prompt you can edit."],
    ],
  },
  {
    kicker: "Run the decisions",
    note: "Incidents: the agents generate, Jev decides",
    stages: [
      ["Event", "Anything that happens to your chain arrives by webhook as plain text. Jev picks which experts to consult."],
      ["Evidence", "The orchestrator questions those experts against the graph, round by round, until Jev judges the evidence enough."],
      ["Options", "An analyst sizes the impact and a comms agent drafts messages, in parallel. A planner lays out options, unranked."],
      ["Decision", "Jev, TypeSafe's decision model, scores every option and the event's priority. You approve; only critical acts alone."],
    ],
  },
] as const;

const CAPS = [
  ["Conversation first", "No config screens. The first run is a chat that goes as deep as your business is complicated."],
  ["Provenance on every value", "Each number links back to the form answer or file it came from. The graph can answer where it came from."],
  ["One tenant, one graph", "Your ontology, data and experts live in an isolated FalkorDB graph, versioned and never overwritten."],
  ["Only Jev decides", "LLM agents gather evidence, draft and propose. Whom to ask, when to stop and which option wins are Jev's calibrated probabilities."],
  ["Evidence you can check", "Every claim in an incident report is numbered and sourced to graph objects, and a validator rejects ids the tools never returned."],
  ["A workspace per person", "Each person gets a dashboard for their roles and a chat with the agent team. It answers questions; it never approves or acts."],
] as const;

const SOP = [
  { t: "Interview", who: "Interviewer agent + you", inp: "A short conversation, any files you attach", out: "Supply Chain Brief", gate: "You confirm the brief", note: "Starts with a handful of questions and goes deeper only where your answers warrant it." },
  { t: "Request the data", who: "Data agent", inp: "The brief", out: "Forms rendered in the chat", gate: "You fill, upload or give a ballpark", note: "Iterative: a submitted form can bring a sharper round. Stops when the ontology has what it needs." },
  { t: "Design and load the ontology", who: "Ontology agent", inp: "Brief + collected data", out: "Types and relationships, then nodes and edges in FalkorDB", gate: "You approve, edit or ask for a change", note: "Reviewed as a diagram and an editable table. The graph is loaded only after approval, every value with its trail." },
  { t: "Generate experts", who: "Expert generator", inp: "Ontology + brief", out: "Expert roles with prompts", gate: "You accept, edit, reject or ask for another", note: "Each role must justify itself against the ontology. Unjustified roles are rejected and merged." },
  { t: "An event arrives", who: "Jev + orchestrator + experts", inp: "A webhook with a free-text summary", out: "A numbered, sourced evidence report", gate: "Jev judges when the evidence is enough", note: "Jev chooses which experts are relevant. The orchestrator questions them in rounds; they answer from the graph in parallel." },
  { t: "Analyse, draft, plan", who: "Analyst and comms, then planner", inp: "The evidence report", out: "Impact metrics, message drafts, option groups", gate: "A validator checks every id and evidence ref", note: "Analyst and comms work in parallel. The planner proposes exclusive and independent options and never ranks them." },
  { t: "Decide", who: "Jev, then you", inp: "The decision packet", out: "A probability per option, a priority for the event", gate: "You approve; only critical auto-approves", note: "Fixed policy thresholds, no model. Each approved option shows its live impact on the graph; rejecting an auto-approval undoes it." },
  { t: "Ask and revisit", who: "Anyone, any time", inp: "A question, or a changed fact", out: "Sourced answers, or re-look flags and new versions", gate: "You review what changed", note: "Ask the agent team from your workspace. Say “we also ship by rail” at any stage and downstream work is flagged, never silently rewritten." },
] as const;

// Where each step belongs: the two halves of the product, then what is open at any time.
const PARTS = [
  ["[A]", "Build the brain", "01-04"],
  ["[B]", "Run the decisions", "05-07"],
  ["[ ]", "Any time", "08"],
] as const;

/** A step number that lights up while its step crosses the middle of the viewport. */
function StepNum({ n }: { n: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const lit = useInView(ref, { once: false, margin: "-45% 0px -45% 0px" });
  return (
    <span
      ref={ref}
      className={`micro absolute left-0 top-0 flex h-6 w-6 items-center justify-center border border-sky-400 text-[10px] text-white transition-colors duration-300 ${lit ? "bg-sky-400" : "bg-black"}`}
    >
      {n}
    </span>
  );
}

/** A hairline that draws itself across once it scrolls into view. */
function DrawnRule({ className }: { className: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref);
  return (
    <span
      ref={ref}
      aria-hidden
      style={{ transform: `scaleX(${inView ? 1 : 0})`, transformOrigin: "left", transition: "transform 1.4s ease-out 0.3s" }}
      className={className}
    />
  );
}

function Workflow() {
  const ref = useRef<HTMLDivElement>(null);
  const { progress } = useScrollProgress(ref, 0.7, 0.6);
  return (
    <section className="mx-auto max-w-6xl px-6 pb-32">
      <div className="grid gap-12 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <div className="md:sticky md:top-28 md:self-start">
          <div className="micro text-sky-400">Workflow &amp; SOP</div>
          <h2 className="mt-3 text-4xl font-light leading-tight tracking-tight text-white">One standard procedure, every company.</h2>
          <p className="mt-4 text-sm leading-relaxed text-slate-400">Eight steps from first question to a decided incident. Each names who acts, what goes in, what comes out, and who has to approve.</p>
          <ul className="mt-6 space-y-2 border-t border-white/10 pt-4">
            {PARTS.map(([mark, name, steps]) => (
              <li key={name} className="flex items-baseline gap-3 text-sm">
                <span className="micro w-6 text-slate-600">{mark}</span>
                <span className="text-slate-200">{name}</span>
                <span className="ml-auto font-mono text-xs tabular-nums text-slate-500">{steps}</span>
              </li>
            ))}
          </ul>
        </div>
        <div ref={ref} className="relative">
          <div className="absolute bottom-2 left-[11px] top-2 w-px bg-white/10" />
          <div style={{ transform: `scaleY(${progress})`, transformOrigin: "top" }} className="absolute bottom-2 left-[11px] top-2 w-px bg-sky-400 shadow-[0_0_8px_#5b9bf3]" />
          <ol className="space-y-8">
            {SOP.map((st, i) => (
              <Reveal as="li" key={st.t} from="translateX(30px)" margin="0px 0px -12% 0px" className="relative pl-10">
                <StepNum n={i + 1} />
                <div className="text-2xl font-light text-white">{st.t}</div>
                <p className="mt-1 max-w-xl text-sm text-slate-400">{st.note}</p>
                <dl className="mt-3 grid gap-px border border-white/10 bg-white/10 text-xs sm:grid-cols-2">
                  {[
                    ["Owner", st.who],
                    ["Input", st.inp],
                    ["Output", st.out],
                    ["Approval gate", st.gate],
                  ].map(([k, v]) => (
                    <div key={k} className="bg-black px-3 py-2">
                      <dt className={`micro ${k === "Approval gate" ? "text-amber-400" : "text-slate-500"}`}>{k}</dt>
                      <dd className="mt-0.5 text-slate-200">{v}</dd>
                    </div>
                  ))}
                </dl>
              </Reveal>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

const MENU: [string, string][] = [
  ["/overview", "Overview"],
  ["/workspace", "My workspace"],
  ["/onboarding", "Onboarding"],
  ["/ontology", "Ontology"],
  ["/objects", "Object explorer"],
  ["/graph", "Graph"],
  ["/experts", "Experts"],
  ["/incidents", "Incidents"],
];

function Menu({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="menu-in fixed inset-0 z-[2000] overflow-auto bg-black/95 px-8 py-24 backdrop-blur" role="dialog" aria-label="Menu">
      <button onClick={onClose} className="micro absolute right-6 top-6 border border-white/20 px-3 py-2 text-white hover:bg-white/10">
        Close
      </button>
      <ul className="mx-auto max-w-3xl">
        {MENU.map(([to, label], i) => (
          <li key={to} style={enter("rise", 0.5, 0.2 + i * 0.05)}>
            <Link to={to} className="group flex items-baseline gap-4 border-b border-white/10 py-3 text-4xl font-light text-slate-300 hover:text-white">
              <span className="micro text-slate-600 group-hover:text-sky-400">0{i + 1}</span>
              {label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Landing() {
  const hero = useRef<HTMLDivElement>(null);
  const [menu, setMenu] = useState(false);
  const [clock, setClock] = useState("");
  const { progress: p, scrollY } = useScrollProgress(hero, 0, 1);
  const past = scrollY > 40;

  useEffect(() => {
    const tick = () => setClock(new Date().toISOString().slice(11, 19) + " UTC");
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const wordScale = mapRange(p, 0, 1, 1, 1.5);
  const wordY = mapRange(p, 0, 1, 0, -14);
  const wordOp = mapRange(p, 0.1, 0.65, 1, 0);
  const globeScale = mapRange(p, 0, 1, 1, 1.45);
  const globeY = mapRange(p, 0, 1, 0, 12);
  const sideX = mapRange(p, 0, 0.4, 0, -120);
  const sideOp = mapRange(p, 0, 0.35, 1, 0);
  const hintOp = mapRange(p, 0, 0.12, 1, 0);
  const fade = mapRange(p, 0.7, 1, 0, 1);

  return (
    <div className="min-h-full bg-black text-slate-200">
      {/* top bar */}
      <header className={`fixed inset-x-0 top-0 z-[1500] flex items-center justify-between px-5 py-4 transition-colors ${past ? "bg-black/70 backdrop-blur" : ""}`}>
        <Link to="/" className="flex items-center gap-3">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.5" aria-hidden>
            <circle cx="12" cy="12" r="2.5" />
            <circle cx="12" cy="12" r="6.5" opacity=".7" />
            <circle cx="12" cy="12" r="10.5" opacity=".4" />
          </svg>
          <span className="text-xl font-medium tracking-tight text-white">Ripple</span>
        </Link>
        <div className="flex items-center gap-3">
          <Link to="/onboarding" className="border border-white/70 bg-black/40 px-8 py-2.5 text-[15px] text-white transition-colors hover:bg-white hover:text-black">
            Get Started
          </Link>
          <button onClick={() => setMenu(true)} aria-label="Menu" className="flex h-[42px] w-[42px] flex-col items-center justify-center gap-1.5 border border-white/40 hover:bg-white/10">
            <span className="h-px w-5 bg-white" />
            <span className="h-px w-5 bg-white" />
            <span className="h-px w-5 bg-white" />
          </button>
        </div>
      </header>
      <Menu open={menu} onClose={() => setMenu(false)} />

      {/* hero: tall scroll runway, sticky stage */}
      <div ref={hero} className="relative h-[180vh]">
        <div className="sticky top-0 h-screen overflow-hidden">
          <div style={{ transform: `translateY(${globeY}%) scale(${globeScale})` }} className="absolute inset-0 origin-bottom">
            <div style={{ animation: "fade 1.6s ease both" }} className="h-full w-full">
              <Globe />
            </div>
          </div>

          <div style={{ transform: `translateX(${sideX}px)`, opacity: sideOp }} className="absolute left-0 top-24 hidden md:block">
            <div className="[mask-image:linear-gradient(to_bottom,black_55%,transparent)]">
              <Board />
            </div>
          </div>

          {/* caption columns */}
          <div style={{ opacity: wordOp }} className="micro absolute inset-x-5 bottom-[34vh] hidden grid-cols-4 gap-6 text-[10.5px] leading-relaxed text-slate-300 md:grid md:pl-[10%]">
            {[
              ["You are", "now entering"],
              ["Time: " + clock, "Scroll", "to explore"],
              ["The operating", "system for supply chain", "decision making"],
              ["Copyright ©2026", "Ripple", "on FalkorDB"],
            ].map((c, i) => (
              <div key={i} style={enter("rise", 0.4, 0.8 + i * 0.12)} className="border-l border-white/40 pl-3">
                {c.map((l) => (
                  <div key={l}>{l}</div>
                ))}
              </div>
            ))}
          </div>

          {/* wordmark */}
          <h1
            style={{ transform: `translateY(${wordY}vh) scale(${wordScale})`, opacity: wordOp }}
            className="pointer-events-none absolute inset-x-0 bottom-[-2vw] origin-bottom select-none text-center font-light leading-[0.8] tracking-[-0.05em] text-slate-200/95"
          >
            <span style={enter("word-in", 1.2)} className="block text-[min(34vw,46vh)]">
              Ripple
            </span>
          </h1>

          <div style={{ opacity: hintOp }} className="micro absolute bottom-6 left-1/2 flex -translate-x-1/2 flex-col items-center gap-2 text-slate-400">
            Scroll
            <span style={{ animation: "bob 1.6s ease-in-out infinite" }} className="block h-6 w-px bg-slate-400" />
          </div>

          <div style={{ opacity: fade }} className="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent to-black" />
        </div>
      </div>

      {/* statement */}
      <section className="mx-auto max-w-5xl px-6 py-32">
        <Reveal from="none" className="micro mb-6 text-sky-400">
          The shift
        </Reveal>
        <h2 className="text-4xl font-light leading-tight tracking-tight text-white md:text-6xl">
          {"Interviews any company. Builds its supply chain brain. Then helps it decide.".split(" ").map((w, i) => (
            <Reveal as="span" key={i} delay={i * 0.05} margin="0px 0px -10% 0px" className="mr-[0.25em] inline-block">
              {w}
            </Reveal>
          ))}
        </h2>
        <Reveal as="p" from="none" delay={0.5} className="mt-8 max-w-2xl text-lg text-slate-400">
          Their ontology, their data, their expert agents, all in FalkorDB. When something breaks, the agents gather the evidence and lay out the options, and Jev, a decision model rather than an LLM, scores them.
        </Reveal>
      </section>

      {/* pipeline */}
      <section className="mx-auto flex max-w-6xl flex-col gap-16 px-6 pb-32">
        {PHASES.map((ph, p) => (
          <div key={ph.kicker}>
            <div className="mb-5 flex flex-wrap items-baseline justify-between gap-2">
              <div className="flex items-baseline gap-4">
                <span className="micro text-slate-600">[{String.fromCharCode(65 + p)}]</span>
                <span className="text-2xl font-light text-white">{ph.kicker}</span>
              </div>
              <span className="micro text-slate-500">{ph.note}</span>
            </div>
            <div className="relative grid gap-px border border-white/10 bg-white/10 md:grid-cols-4">
              {ph.stages.map(([t, d], i) => (
                <Reveal key={t} delay={i * 0.12} from="translateY(40px)" className="bg-black p-6 hover:bg-[#0b1424]">
                  <div className="micro text-sky-400">Stage 0{p * 4 + i + 1}</div>
                  <div className="mt-3 text-2xl font-light text-white">{t}</div>
                  <p className="mt-3 text-sm leading-relaxed text-slate-400">{d}</p>
                </Reveal>
              ))}
              <DrawnRule className="absolute -top-px left-0 h-px w-full bg-sky-400" />
            </div>
          </div>
        ))}
      </section>

      <Workflow />

      {/* capabilities */}
      <section className="mx-auto max-w-6xl px-6 pb-32">
        <div className="micro mb-8 text-sky-400">What you get</div>
        <div className="grid gap-x-10 gap-y-12 md:grid-cols-3">
          {CAPS.map(([t, d], i) => (
            <Reveal key={t} delay={(i % 3) * 0.1} className="border-t border-white/15 pt-5">
              <div className="text-xl font-light text-white">{t}</div>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{d}</p>
            </Reveal>
          ))}
        </div>
      </section>

      {/* enter */}
      <section className="relative overflow-hidden border-t border-white/10 py-40 text-center">
        <div className="absolute left-1/2 top-1/2 h-[60vw] w-[60vw] -translate-x-1/2 -translate-y-1/2">
          <Reveal from="scale(0.6)" className="relative h-full w-full rounded-full border border-sky-400/20">
            <span className="absolute inset-[12%] rounded-full border border-sky-400/20" />
            <span className="absolute inset-[26%] rounded-full border border-sky-400/20" />
          </Reveal>
        </div>
        <div className="relative">
          <Reveal as="h2" className="text-5xl font-light tracking-tight text-white md:text-7xl">
            Enter Ripple
          </Reveal>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link to="/onboarding" className="border border-sky-400 bg-sky-500/10 px-10 py-3 text-[15px] text-white transition-colors hover:bg-sky-400 hover:text-black">
              Start onboarding
            </Link>
            <Link to="/overview" className="border border-white/30 px-10 py-3 text-[15px] text-slate-200 transition-colors hover:bg-white/10">
              Open the overview
            </Link>
            <Link to="/incidents" className="border border-white/30 px-10 py-3 text-[15px] text-slate-200 transition-colors hover:bg-white/10">
              See incidents
            </Link>
          </div>
        </div>
      </section>
      <footer className="micro border-t border-white/10 px-6 py-6 text-slate-600">Ripple · Supply chain operating system · Built on FalkorDB</footer>
    </div>
  );
}
