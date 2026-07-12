"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LogoMark } from "@/components/Logo";
import { Reveal } from "@/components/Reveal";

const NAV_ITEMS = [
  { label: "Platform", href: "#platform" },
  { label: "Pipelines", href: "#pipelines" },
  { label: "Integrations", href: "#stack" },
  { label: "How it works", href: "#how-it-works" },
  { label: "Contact", href: "#contact" },
];

const WORK_ITEMS = [
  {
    title: "Natural Language → SQL",
    category: "Query · Self-correcting",
    tags: ["PostgreSQL", "Supabase", "Auto-retry"],
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M4 6h16M4 12h16M4 18h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    title: "Sandboxed Analysis",
    category: "pandas · run_analysis tool",
    tags: ["Correlation", "Anomaly detection", "No filesystem access"],
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M4 4l8 8-8 8M12 20h8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    title: "Insight Reports",
    category: "Autonomous analyst pipeline",
    tags: ["Self-planned questions", "Narrative output", "Downloadable"],
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <rect x="4" y="4" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="2" />
        <rect x="13" y="13" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="2" />
        <path d="M11 7.5h6M7.5 11v6" stroke="currentColor" strokeWidth="2" />
      </svg>
    ),
  },
  {
    title: "CSV / Excel Ingestion",
    category: "Upload · Per-workspace isolation",
    tags: ["Schema inference", "Column sanitization", "Auto-profiling"],
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M3 17l5-6 4 4 5-8 4 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    title: "Web Context",
    category: "Tavily · Hybrid answers",
    tags: ["Benchmarks", "Definitions", "Source labeling"],
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="2" />
        <path d="M4 12h16M12 4c2.5 2.5 2.5 13 0 16M12 4c-2.5 2.5-2.5 13 0 16" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    ),
  },
];

const STACK_TOOLS = [
  "Python",
  "FastAPI",
  "OpenRouter",
  "PostgreSQL",
  "Supabase",
  "Next.js",
  "Vercel",
  "Tavily",
  "pandas",
  "SQLAlchemy",
];

const HOW_IT_WORKS = [
  {
    step: "01",
    title: "Upload",
    desc: "Drop a CSV or Excel file. It lands in your own isolated workspace, and every table is auto-profiled — row counts, ranges, null rates.",
  },
  {
    step: "02",
    title: "Ask",
    desc: "Chat in plain language. The agent writes the SQL, runs it, self-corrects on errors, and shows you every query it executed.",
  },
  {
    step: "03",
    title: "Report",
    desc: "One click generates a narrative insight report — the agent plans its own questions, flags anomalies, and writes the recommendations.",
  },
];

const CONTACT_LINKS = [
  { label: "GitHub", href: "https://github.com/juan-elf/Database-AI-agent" },
  { label: "Live Demo", href: "/chat" },
  { label: "Eval Harness", href: "https://github.com/juan-elf/Database-AI-agent#eval-harness" },
];

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-[18px] font-mono text-xs uppercase tracking-[0.16em] text-accent">
      {children}
    </div>
  );
}

export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", onScroll);
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="min-h-screen overflow-x-hidden bg-navy text-ink">
      {/* ================= NAV ================= */}
      <nav
        className={`fixed inset-x-0 top-0 z-50 flex items-center justify-between border-b px-6 py-[18px] backdrop-blur-xl transition-colors duration-200 md:px-12 ${
          scrolled ? "border-divider bg-navy/85" : "border-transparent bg-transparent"
        }`}
      >
        <Link href="/" className="flex items-center gap-3 text-ink">
          <LogoMark size={26} />
          <span className="text-[17px] font-bold tracking-tight">
            Data<span className="font-normal text-accent">Gen</span>
          </span>
        </Link>

        <div className="hidden items-center gap-9 md:flex">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.label}
              href={item.href}
              className="text-sm font-medium text-soft transition-colors hover:text-accent"
            >
              {item.label}
            </a>
          ))}
        </div>

        <Link
          href="/upload"
          className="flex items-center gap-2 rounded-[7px] bg-accent px-5 py-2.5 text-sm font-semibold text-accent-ink transition hover:-translate-y-px hover:bg-accent2"
        >
          Get Started
        </Link>
      </nav>

      {/* ================= HERO ================= */}
      <section className="relative mx-auto flex max-w-[1180px] flex-col items-start px-6 pb-[140px] pt-[160px] md:px-12 md:pt-[200px]">
        <div className="pointer-events-none absolute -right-10 top-[120px] opacity-[0.06]">
          <span className="text-ink">
            <LogoMark size={440} />
          </span>
        </div>

        <div className="mb-7 inline-flex items-center gap-2 rounded-[20px] border border-accent/30 bg-accent/10 px-3.5 py-[7px] font-mono text-xs tracking-wider text-accent2">
          <span className="inline-block h-[7px] w-[7px] rounded-full bg-accent shadow-[0_0_8px_#22D3EE]" />
          Open source · MIT licensed
        </div>

        <h1 className="mb-7 max-w-[900px] text-5xl font-bold leading-[1.02] tracking-[-0.03em] md:text-[76px]">
          Talk to your data.
          <br />
          Get<span className="font-normal text-accent">&nbsp;real answers.</span>
        </h1>

        <p className="mb-11 max-w-[620px] text-[19px] leading-relaxed text-muted">
          DataGen is an LLM-powered agent that answers natural-language questions about your
          uploaded data — it writes the SQL, runs sandboxed analysis, and replies in plain text.
        </p>

        <div className="mb-[76px] flex items-center gap-4">
          <Link
            href="/chat"
            className="rounded-lg bg-accent px-7 py-3.5 text-[15px] font-semibold text-accent-ink transition hover:-translate-y-0.5 hover:bg-accent2"
          >
            Try the live demo →
          </Link>
          <a
            href="#stack"
            className="rounded-lg border border-edge3 px-7 py-3.5 text-[15px] font-semibold text-ink transition hover:border-accent hover:text-accent"
          >
            View the stack
          </a>
        </div>

        <div className="flex w-full max-w-[640px] gap-16 border-t border-divider pt-8">
          <div>
            <div className="text-[32px] font-bold text-accent">
              85.7<span className="text-xl">%</span>
            </div>
            <div className="mt-1 font-mono text-xs text-dim">Eval accuracy (38 cases)</div>
          </div>
          <div>
            <div className="text-[32px] font-bold text-accent">4</div>
            <div className="mt-1 font-mono text-xs text-dim">Agent tools</div>
          </div>
        </div>
      </section>

      {/* ================= PLATFORM ================= */}
      <section
        id="platform"
        className="mx-auto grid max-w-[1180px] grid-cols-1 gap-20 border-t border-edge px-6 py-[120px] md:grid-cols-[1.3fr_0.9fr] md:px-12"
      >
        <Reveal>
          <SectionLabel>Platform</SectionLabel>
          <h2 className="mb-7 text-3xl font-bold leading-[1.15] tracking-[-0.02em] md:text-[42px]">
            An agent that queries your data like a teammate would.
          </h2>
          <p className="mb-5 text-[17px] leading-[1.75] text-muted">
            Upload a <strong className="font-semibold text-ink">CSV or Excel file</strong> — no
            schema config required. On ingest it lands in your own isolated workspace, and DataGen
            auto-profiles every table, folding row counts, null rates, and semantic types straight
            into its own system prompt.
          </p>
          <p className="mb-5 text-[17px] leading-[1.75] text-muted">
            Ask a question in plain language and the agent{" "}
            <strong className="font-semibold text-ink">
              generates SQL, executes it, self-corrects on errors
            </strong>
            , and can drop into a sandboxed pandas environment for correlation, anomaly detection,
            and distribution stats — with Tavily web search for context the data doesn&apos;t have.
          </p>
          <p className="text-[17px] leading-[1.75] text-muted">
            And it&apos;s measured, not vibes — an{" "}
            <strong className="font-semibold text-ink">automated eval harness</strong> scores the
            agent against 38 ground-truth SQL cases, and every query it executes is shown in the
            chat, so you can verify exactly how each answer was produced.
          </p>
        </Reveal>

        <Reveal className="self-start rounded-[14px] border border-edge2 bg-card p-9">
          <div className="mb-6 font-mono text-[11px] uppercase tracking-[0.14em] text-dim">
            Snapshot
          </div>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <div className="mb-1.5 text-xs text-dim">Data in</div>
              <div className="text-[22px] font-bold">CSV · Excel</div>
            </div>
            <div>
              <div className="mb-1.5 text-xs text-dim">Storage</div>
              <div className="text-[22px] font-bold">Postgres</div>
            </div>
            <div>
              <div className="mb-1.5 text-xs text-dim">Eval cases</div>
              <div className="text-[22px] font-bold">38</div>
            </div>
            <div>
              <div className="mb-1.5 text-xs text-dim">License</div>
              <div className="text-[22px] font-bold">MIT</div>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ================= PIPELINES ================= */}
      <section
        id="pipelines"
        className="mx-auto max-w-[1180px] border-t border-edge px-6 py-[120px] md:px-12"
      >
        <div className="mb-14">
          <SectionLabel>What it handles</SectionLabel>
          <h2 className="text-3xl font-bold leading-[1.15] tracking-[-0.02em] md:text-[42px]">
            One agent, five jobs.
          </h2>
        </div>

        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {WORK_ITEMS.map((w) => (
            <Reveal
              key={w.title}
              className="rounded-[14px] border border-edge2 bg-card p-[30px] transition hover:-translate-y-1 hover:border-accent"
            >
              <div className="mb-[22px] flex h-[42px] w-[42px] items-center justify-center rounded-[9px] bg-accent/10 text-accent">
                {w.icon}
              </div>
              <div className="mb-2 text-lg font-semibold">{w.title}</div>
              <div className="mb-[18px] font-mono text-xs text-dim">{w.category}</div>
              <div className="flex flex-wrap gap-2">
                {w.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-[5px] bg-[#152438] px-2.5 py-[5px] font-mono text-[11px] text-muted"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ================= STACK MARQUEE ================= */}
      <section id="stack" className="overflow-hidden border-t border-edge py-[100px]">
        <div className="mx-auto max-w-[1180px] px-6 pb-14 md:px-12">
          <SectionLabel>Integrations</SectionLabel>
          <h2 className="text-3xl font-bold leading-[1.15] tracking-[-0.02em] md:text-[42px]">
            Runs on the stack you already trust.
          </h2>
        </div>
        <div className="animate-marquee flex w-max">
          {[...STACK_TOOLS, ...STACK_TOOLS].map((tool, i) => (
            <span
              key={`${tool}-${i}`}
              className="flex items-center whitespace-nowrap border-r border-divider px-9 font-mono text-xl text-ghost"
            >
              {tool}
            </span>
          ))}
        </div>
      </section>

      {/* ================= HOW IT WORKS ================= */}
      <section
        id="how-it-works"
        className="mx-auto max-w-[1180px] border-t border-edge px-6 py-[120px] md:px-12"
      >
        <div className="mb-14">
          <SectionLabel>How it works</SectionLabel>
          <h2 className="text-3xl font-bold leading-[1.15] tracking-[-0.02em] md:text-[42px]">
            From file to findings in three steps.
          </h2>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {HOW_IT_WORKS.map((s) => (
            <Reveal
              key={s.step}
              className="rounded-[14px] border border-edge2 bg-card p-[30px] transition hover:-translate-y-1 hover:border-accent"
            >
              <div className="mb-5 font-mono text-[28px] font-bold text-accent">{s.step}</div>
              <div className="mb-2.5 text-lg font-semibold text-ink">{s.title}</div>
              <div className="text-sm leading-[1.65] text-[#8497AB]">{s.desc}</div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ================= CONTACT ================= */}
      <section
        id="contact"
        className="mx-auto max-w-[1180px] border-t border-edge px-6 pb-[100px] pt-[140px] text-center md:px-12"
      >
        <div className="mb-[22px] font-mono text-xs uppercase tracking-[0.16em] text-accent">
          Contact
        </div>
        <h2 className="mb-5 text-4xl font-bold leading-[1.1] tracking-[-0.02em] md:text-[48px]">
          Upload your data. Ask a question.
        </h2>
        <p className="mx-auto mb-12 max-w-[520px] text-[17px] text-muted">
          Open source and MIT licensed — try the hosted demo or clone the repo and bring your own
          data.
        </p>

        <div className="mb-16 flex flex-wrap justify-center gap-4">
          <Link
            href="/chat"
            className="rounded-lg bg-accent px-[30px] py-3.5 text-[15px] font-semibold text-accent-ink transition hover:-translate-y-0.5"
          >
            Try the live demo →
          </Link>
          <a
            href="https://github.com/juan-elf/Database-AI-agent"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-edge3 px-[30px] py-3.5 text-[15px] font-semibold text-ink transition hover:border-accent hover:text-accent"
          >
            Read the docs
          </a>
        </div>

        <div className="flex flex-wrap justify-center gap-9 text-sm">
          {CONTACT_LINKS.map((link) =>
            link.href.startsWith("/") ? (
              <Link
                key={link.label}
                href={link.href}
                className="text-[#8497AB] transition-colors hover:text-accent"
              >
                {link.label}
              </Link>
            ) : (
              <a
                key={link.label}
                href={link.href}
                className="text-[#8497AB] transition-colors hover:text-accent"
              >
                {link.label}
              </a>
            ),
          )}
        </div>
      </section>

      <footer className="border-t border-edge px-12 py-8 text-center font-mono text-xs text-faint">
        © 2026 DataGen. All rights reserved.
      </footer>
    </div>
  );
}
