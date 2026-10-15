import { useEffect, useState } from "react";
import { api } from "../api";
import type { Answer, Person, Source } from "../api";
import { Btn, Card, Chip, ErrorLine } from "../components/ui";

const DEMO = [
  "Who owns our relationship with Shenzhen Volt Components, and who backs them up?",
  "Why did we dual-source the Li-ion battery pack?",
  "What does the contract with Shenzhen Volt Components say about delay penalties, and are we owed anything for this incident?",
  "Who on the team has handled a port closure before?",
  "What changed in our sourcing policy since the 2024 typhoon?",
];

interface Turn {
  q: string;
  a: Answer | null;
  error?: string;
}

export default function Brain({ tenant }: { tenant: string }) {
  const [q, setQ] = useState("");
  const [incident, setIncident] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [source, setSource] = useState<Source | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [msg, setMsg] = useState("");
  const [author, setAuthor] = useState("");
  const [channel, setChannel] = useState("#sourcing-electronics");
  const [ingested, setIngested] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.people().then((p) => {
      setPeople(p);
      setAuthor(p[0]?.id ?? "");
    });
    api.handoverSample().then((s) => {
      if (s.text) {
        setMsg(s.text);
        setAuthor(s.author_id);
        setChannel(s.channel);
      }
    }).catch(() => undefined);
    setTurns([]);
  }, [tenant]);

  const ask = async (question: string) => {
    if (!question.trim()) return;
    setQ("");
    setTurns((t) => [...t, { q: question, a: null }]);
    try {
      const a = await api.ask(question, "USR-demo", incident.trim() || undefined);
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, a } : x)));
    } catch (e) {
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: (e as Error).message } : x)));
    }
  };

  const post = async () => {
    setError(null);
    try {
      const r = await api.ingest(msg, author, channel);
      setIngested(r.handover ? `Ingested ${r.message_id}: ${r.handover.supplier_id} is now owned by ${r.handover.to}` : `Ingested ${r.message_id}`);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <Card title="Ask the company brain">
        <div className="mb-3 flex flex-wrap gap-1.5">
          {DEMO.map((d) => (
            <button key={d} onClick={() => ask(d)} className="rounded bg-slate-800 px-2 py-1 text-left text-xs hover:bg-slate-700">
              {d}
            </button>
          ))}
        </div>
        <div className="max-h-[60vh] space-y-3 overflow-y-auto">
          {turns.map((t, i) => (
            <div key={i} className="space-y-1">
              <div className="text-sm font-medium text-sky-300">{t.q}</div>
              {t.error && <ErrorLine error={t.error} />}
              {!t.a && !t.error && <div className="text-xs text-slate-500">thinking over the graph...</div>}
              {t.a && (
                <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3 text-sm">
                  <div className="mb-2 whitespace-pre-wrap text-slate-200">{t.a.answer}</div>
                  <div className="flex flex-wrap items-center gap-1">
                    <span className="text-xs text-slate-500">intent</span>
                    {t.a.intent.map((x) => (
                      <Chip key={x} color="bg-indigo-900">{x}</Chip>
                    ))}
                    <span className="ml-2 text-xs text-slate-500">sources</span>
                    {t.a.sources.map((s) => (
                      <Chip key={s.doc_id} color="bg-amber-800" onClick={() => setSource(s)} title={s.title}>
                        {s.doc_id}
                      </Chip>
                    ))}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    <span className="text-xs text-slate-500">path</span>
                    {t.a.path.slice(0, 18).map((p) => (
                      <Chip key={p}>{p}</Chip>
                    ))}
                    {t.a.path.length > 18 && <span className="text-xs text-slate-500">+{t.a.path.length - 18}</span>}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <input
            className="flex-1 rounded bg-slate-800 px-3 py-2 text-sm outline-none"
            placeholder="Ask about owners, contracts, decisions, expertise, policy changes..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask(q)}
          />
          <input
            className="w-40 rounded bg-slate-800 px-2 py-2 font-mono text-xs outline-none"
            placeholder="incident id (optional)"
            value={incident}
            onChange={(e) => setIncident(e.target.value)}
          />
          <Btn kind="primary" onClick={() => ask(q)}>
            Ask
          </Btn>
        </div>
      </Card>
      <div className="space-y-4">
        <Card title="Source" right={source && <Btn kind="ghost" onClick={() => setSource(null)}>x</Btn>}>
          {source ? (
            <div className="space-y-1 text-sm">
              <div className="font-medium">{source.title}</div>
              <div className="font-mono text-xs text-slate-400">
                {source.doc_id}
                {source.chunk_id ? ` / ${source.chunk_id}` : ""}
              </div>
              <div className="font-mono text-xs text-slate-500">{source.uri}</div>
              <div className="whitespace-pre-wrap rounded bg-slate-950 p-2 text-xs text-slate-300">{source.snippet}</div>
            </div>
          ) : (
            <div className="text-sm text-slate-500">Click a source chip to see the chunk.</div>
          )}
        </Card>
        <Card title="Post chat message (live ingest)">
          <div className="space-y-2">
            <select className="w-full rounded bg-slate-800 px-2 py-1 text-xs" value={author} onChange={(e) => setAuthor(e.target.value)}>
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.id}, {p.team})
                </option>
              ))}
            </select>
            <input className="w-full rounded bg-slate-800 px-2 py-1 text-xs" value={channel} onChange={(e) => setChannel(e.target.value)} />
            <textarea className="h-28 w-full rounded bg-slate-800 p-2 text-xs" value={msg} onChange={(e) => setMsg(e.target.value)} />
            <Btn kind="primary" onClick={post}>
              Post
            </Btn>
            {ingested && <div className="rounded bg-emerald-950 p-2 text-xs text-emerald-200">{ingested}</div>}
            <ErrorLine error={error} />
            <div className="text-xs text-slate-500">Then ask the owner question again: the answer changes.</div>
          </div>
        </Card>
      </div>
    </div>
  );
}
