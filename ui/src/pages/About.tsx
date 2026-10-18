import { PageHeader } from "../components/ui";
import { Reveal } from "../components/motion";
import { Avatar } from "./Workspace";

export const TEAM: { name: string; role: string; school: string; note?: string; linkedin: string; github: string }[] = [
  {
    name: "Divyansh Parashar",
    role: "",
    school: "Final-year Computer Science and Design Engineering, RGIPT",
    linkedin: "https://www.linkedin.com/in/divyansh1212/",
    github: "https://github.com/DivyanshParashar1",
  },
  {
    name: "Virag Tiwari",
    role: " ",
    school: "Final Year Information Technolgy Engineering, RGIPT & Co-founder, Orange Cat Technologies",
    linkedin: "https://www.linkedin.com/in/virag-tiwari-11ba0727b/",
    github: "https://github.com/viragtiwari2004",
  },
  {
    name: "Vaibhav",
    role: " ",
    school: "Final-year Electrical Engineering, RGIPT",
    linkedin: "https://www.linkedin.com/in/vaibhavrgipt/",
    github: "https://github.com/regardsvaibhav",
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

/** GitHub's mark (octicon), inline so it needs no network. */
export function GitHubMark({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
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
                <div className="mt-5 flex flex-wrap gap-2">
                  <a
                    href={m.linkedin}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex w-fit items-center gap-2 border border-line-strong px-3 py-1.5 text-[12.5px] text-body transition-colors hover:border-white/40 hover:text-ink"
                  >
                    <LinkedInMark />
                    LinkedIn
                  </a>
                  <a
                    href={m.github}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex w-fit items-center gap-2 border border-line-strong px-3 py-1.5 text-[12.5px] text-body transition-colors hover:border-white/40 hover:text-ink"
                  >
                    <GitHubMark />
                    GitHub
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
