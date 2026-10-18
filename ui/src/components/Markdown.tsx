import type { ReactNode } from "react";

// A deliberately small Markdown renderer for agent answers: paragraphs, bullet and numbered lists, **bold**,
// `code` and object ids. It builds React elements (no innerHTML), so model text can never inject markup.

const ID_RE = /\b([A-Z]{2,5}-[A-Z0-9]{2,12})\b/g;

function inline(text: string, key: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  const pushIds = (s: string) => {
    let l = 0;
    let mm: RegExpExecArray | null;
    ID_RE.lastIndex = 0;
    while ((mm = ID_RE.exec(s))) {
      if (mm.index > l) out.push(s.slice(l, mm.index));
      out.push(<span key={`${key}-id-${i++}`} className="rounded-[3px] bg-raised px-1 font-mono text-[11.5px] text-sky-200">{mm[1]}</span>);
      l = mm.index + mm[0].length;
    }
    if (l < s.length) out.push(s.slice(l));
  };
  while ((m = re.exec(text))) {
    if (m.index > last) pushIds(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<strong key={`${key}-b-${i++}`} className="font-semibold text-ink">{tok.slice(2, -2)}</strong>);
    else out.push(<code key={`${key}-c-${i++}`} className="rounded-[3px] bg-raised px-1 font-mono text-[11.5px]">{tok.slice(1, -1)}</code>);
    last = m.index + tok.length;
  }
  if (last < text.length) pushIds(text.slice(last));
  return out;
}

export default function Markdown({ text, className = "" }: { text: string; className?: string }) {
  const blocks: ReactNode[] = [];
  const lines = text.replace(/\r/g, "").split("\n");
  let list: { ordered: boolean; items: string[] } | null = null;
  let para: string[] = [];
  let n = 0;
  const flushPara = () => {
    if (para.length) blocks.push(<p key={`p${n++}`}>{inline(para.join(" "), `p${n}`)}</p>);
    para = [];
  };
  const flushList = () => {
    if (!list) return;
    const items = list.items.map((it, i) => <li key={i}>{inline(it, `l${n}-${i}`)}</li>);
    blocks.push(list.ordered
      ? <ol key={`o${n++}`} className="list-decimal space-y-1 pl-5">{items}</ol>
      : <ul key={`u${n++}`} className="list-disc space-y-1 pl-5">{items}</ul>);
    list = null;
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line);
    const num = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const head = /^#{1,4}\s+(.*)$/.exec(line);
    if (!line.trim()) {
      flushPara();
      flushList();
    } else if (head) {
      flushPara();
      flushList();
      blocks.push(<div key={`h${n++}`} className="pt-1 text-[12.5px] font-semibold uppercase tracking-wide text-muted">{inline(head[1], `h${n}`)}</div>);
    } else if (bullet || num) {
      flushPara();
      const ordered = !!num;
      if (list && list.ordered !== ordered) flushList();
      if (!list) list = { ordered, items: [] };
      list.items.push((bullet ?? num)![1]);
    } else if (list && /^\s{2,}/.test(raw)) {
      list.items[list.items.length - 1] += ` ${line.trim()}`;
    } else {
      flushList();
      para.push(line.trim());
    }
  }
  flushPara();
  flushList();
  return <div className={`space-y-2.5 leading-relaxed ${className}`}>{blocks}</div>;
}
