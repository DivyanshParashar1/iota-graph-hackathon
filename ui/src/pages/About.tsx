import { PageHeader } from "../components/ui";
import { Reveal } from "../components/motion";
import { Avatar } from "./Workspace";

export const TEAM: { name: string; role: string; school: string; note?: string; linkedin: string }[] = [
  {
    name: "Divyansh Parashar",
    role: "",
    school: "Final-year Computer Science and Design Engineering, RGIPT",
    linkedin: "https://www.linkedin.com/in/divyansh1212/",
  },
  {
    name: "Virag Tiwari",
    role: " ",
    school: "Final Year Information Technolgy Engineering, RGIPT & Co-founder, Orange Cat Technologies",
    linkedin: "https://www.linkedin.com/in/virag-tiwari-11ba0727b/",
  },
  {
    name: "Vaibhav",
    role: " ",
    school: "Final-year Electrical Engineering, RGIPT",
    linkedin: "https://www.linkedin.com/in/vaibhavrgipt/",
  },
];

/** LinkedIn's "in" mark, inline so it needs no network. */
export function LinkedInMark({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden>
      <rect width="24" height="24" rx="3" fill="#0A66C2" />
      <path
        fill="#fff"
        d="M6.94 9.5H4.1V19h2.84V9.5ZM5.52 5a1.65 1.65 0 1 0 0 3.3 1.65 1.65 0 0 0 0-3.3ZM19.9 13.6c0-2.6-1.4-4.3-3.6-4.3-1.2 0-2 .6-2.5 1.2V9.5H11V19h2.84v-5c0-1.3.6-2.1 1.7-2.1 1 0 1.5.7 1.5 2.1V19h2.84v-5.4Z"
      />
    </svg>
  );
}

export default function About() {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto">
      <PageHeader title="About us" subtitle="The team behind Ripple" />
      <div className="mx-auto w-full max-w-5xl px-6 py-8">
        <Reveal>
          <div className="micro text-muted">Team Iota</div>
          <h2 className="mt-3 max-w-2xl text-[34px] font-light leading-tight tracking-[-0.02em] text-ink">
            Three final-year students building a supply chain you can talk into existence.
          </h2>
          <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-body">
            Ripple talks to a company, builds its knowledge graph, and decides what to do when something breaks.
          </p>
        </Reveal>

        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {TEAM.map((m, i) => (
            <div key={m.name} className="rise" style={{ animationDelay: `${i * 80}ms` }}>
              <div className="flex h-full flex-col border border-line p-5 transition-colors hover:border-line-strong hover:bg-white/[0.02]">
                <Avatar name={m.name} size={56} />
                <div className="mt-4 text-[18px] font-semibold text-ink">{m.name}</div>
                <div className="mt-1 text-[13px] text-sky-300">{m.role}</div>
                <div className="mt-3 text-[13px] leading-relaxed text-body">{m.school}</div>
                <a
                  href={m.linkedin}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-5 inline-flex w-fit items-center gap-2 border border-line-strong px-3 py-1.5 text-[12.5px] text-body transition-colors hover:border-white/40 hover:text-ink"
                >
                  <LinkedInMark />
                  LinkedIn
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
