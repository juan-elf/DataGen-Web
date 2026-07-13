"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogoMark } from "@/components/Logo";
import { resetChat } from "@/lib/api";
import { useSessions } from "@/lib/sessions";

const RAIL_ITEMS = [
  {
    label: "Chat",
    href: "/chat",
    icon: (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none">
        <path d="M4 5h16v11H9l-4 4V5z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    label: "Report",
    href: "/report",
    icon: (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none">
        <path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" stroke="currentColor" strokeWidth="1.6" />
      </svg>
    ),
  },
  {
    label: "Upload",
    href: "/upload",
    icon: (
      <svg width="19" height="19" viewBox="0 0 24 24" fill="none">
        <path d="M12 16V4M7 9l5-5 5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M4 20h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    ),
  },
];

function SessionList() {
  const router = useRouter();
  const { sessions, activeId, selectSession, deleteSession } = useSessions();

  function open(id: string) {
    selectSession(id);
    router.push("/chat");
  }

  if (sessions.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3.5 text-center text-dim">
        <span className="flex h-[42px] w-[42px] items-center justify-center rounded-[10px] border border-dashed border-[#24374C] text-ghost">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M12 8v8M8 12h8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <rect x="3" y="4" width="18" height="16" rx="2" stroke="currentColor" strokeWidth="1.6" />
          </svg>
        </span>
        <div className="max-w-[150px] text-[12.5px] leading-normal">
          No sessions yet.
          <br />
          Ask your first question.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-1 overflow-y-auto">
      {sessions.map((s) => {
        const active = s.id === activeId;
        return (
          <div
            key={s.id}
            onClick={() => open(s.id)}
            className={`group flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-[12.5px] transition-colors ${
              active ? "bg-accent/10 text-ink" : "text-soft hover:bg-card-hover"
            }`}
          >
            <span className="inline-flex flex-shrink-0 text-dim">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                <path d="M4 5h16v11H9l-4 4V5z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
              </svg>
            </span>
            <span className="flex-1 truncate">{s.title}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                deleteSession(s.id);
              }}
              aria-label="Delete session"
              className="flex-shrink-0 text-dim opacity-0 transition hover:text-[#F26D6D] group-hover:opacity-100"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        );
      })}
    </div>
  );
}

function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { newSession } = useSessions();

  async function handleNewChat() {
    newSession();
    await resetChat();
    router.push("/chat");
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-navy font-sans text-ink">
      {/* ================= SIDEBAR ================= */}
      <aside className="flex w-[280px] flex-shrink-0 flex-col border-r border-edge bg-panel max-md:hidden">
        {/* brand row */}
        <div className="flex items-center justify-between px-[18px] pb-3.5 pt-[18px]">
          <Link href="/" className="flex items-center gap-2.5 text-ink no-underline">
            <LogoMark size={22} />
            <span className="text-base font-bold tracking-tight">
              Data<span className="font-normal text-accent">Gen</span>
            </span>
          </Link>
        </div>

        {/* new chat */}
        <div className="flex items-center gap-2.5 px-3.5 pb-4 pt-1.5">
          <button
            onClick={handleNewChat}
            className="flex-1 cursor-pointer rounded-lg border border-edge2 bg-card px-3.5 py-[9px] text-[13px] font-semibold text-ink transition hover:border-accent hover:bg-card-hover"
          >
            + New chat
          </button>
        </div>

        {/* nav rail + sessions */}
        <div className="flex min-h-0 flex-1">
          <div className="flex w-[70px] flex-shrink-0 flex-col items-center gap-1 pt-1.5">
            {RAIL_ITEMS.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex w-12 flex-col items-center gap-[5px] rounded-[10px] py-2.5 no-underline transition-colors hover:text-accent ${
                    active ? "bg-accent/10 text-accent" : "text-[#8FA3B5]"
                  }`}
                >
                  {item.icon}
                  <span className="text-[9.5px]">{item.label}</span>
                </Link>
              );
            })}
          </div>

          {/* session list */}
          <div className="flex min-w-0 flex-1 flex-col border-l border-edge p-4 px-3">
            <div className="mb-3 px-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-faint">
              Sessions
            </div>
            <SessionList />
          </div>
        </div>

        {/* BYO data card */}
        <Link
          href="/upload"
          className="m-3.5 block rounded-[10px] border border-edge2 bg-card p-3.5 no-underline transition hover:border-accent"
        >
          <div className="flex items-center gap-2.5">
            <span className="inline-flex text-accent">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <ellipse cx="12" cy="6" rx="8" ry="3" stroke="currentColor" strokeWidth="1.8" />
                <path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6" stroke="currentColor" strokeWidth="1.8" />
                <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" stroke="currentColor" strokeWidth="1.8" />
              </svg>
            </span>
            <div>
              <div className="text-[12.5px] font-semibold text-ink">Bring your own data</div>
              <div className="mt-0.5 text-[11px] text-dim">Upload a CSV or Excel to get started</div>
            </div>
          </div>
        </Link>

        {/* footer */}
        <div className="flex items-center justify-around border-t border-edge px-[18px] pb-4 pt-3 text-faint">
          <Link href="/" className="inline-flex text-inherit transition-colors hover:text-accent">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M3 11l9-7 9 7M5 10v9h14v-9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </Link>
          <a
            href="https://github.com/juan-elf/Database-AI-agent"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex text-inherit transition-colors hover:text-accent"
          >
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
              <path d="M4 4l7 8-7 8M13 4l7 8-7 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </a>
        </div>
      </aside>

      {/* ================= MAIN ================= */}
      <main className="relative flex min-w-0 flex-1 flex-col">
        <div className="flex flex-shrink-0 items-center justify-between px-[26px] py-4">
          <div className="flex items-center gap-[9px] font-mono text-xs text-dim">
            <span className="h-[7px] w-[7px] rounded-full bg-accent shadow-[0_0_8px_#22D3EE]" />
            Connected · <span className="text-muted">your workspace</span>
          </div>
        </div>
        {children}
      </main>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
