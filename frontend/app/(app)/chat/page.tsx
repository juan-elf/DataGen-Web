"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import { LogoMark } from "@/components/Logo";
import { sendChatMessage, type ChatEvent } from "@/lib/api";

interface Message {
  role: "user" | "assistant" | "system";
  text: string;
  sql?: string;
}

const CATEGORIES = ["Trending", "Schema", "Aggregations", "Anomalies", "Time-series", "Web context"];

const EXAMPLE_QUESTIONS = [
  "Which battery cells are closest to end-of-life?",
  "What is the average state-of-health by cycle count?",
  "Show total revenue by product category last quarter.",
  "Are there anomalies in the temperature readings this month?",
  "Is our 85% average SOH normal for Li-ion cells?",
];

const DOMAINS = [
  { value: "", label: "No Datagen Skill" },
  { value: "battery", label: "Battery Analyst" },
  { value: "ecommerce", label: "E-commerce Analyst" },
];

const TOOL_LABELS: Record<string, string> = {
  execute_sql: "Running SQL…",
  get_distinct_values: "Inspecting column values…",
  run_analysis: "Running pandas analysis…",
  web_search: "Searching the web…",
};

function Composer({
  input,
  onInput,
  onSend,
  busy,
  placeholder,
  compact = false,
}: {
  input: string;
  onInput: (v: string) => void;
  onSend: () => void;
  busy: boolean;
  placeholder: string;
  compact?: boolean;
}) {
  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  }

  return (
    <div
      className={`flex items-end gap-3 rounded-2xl border border-edge2 bg-card ${
        compact ? "px-3.5 py-3" : "px-5 pb-3.5 pt-[18px]"
      }`}
    >
      <textarea
        value={input}
        onChange={(e) => onInput(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        rows={compact ? 1 : 2}
        disabled={busy}
        className="flex-1 resize-none bg-transparent font-sans text-[15px] leading-normal text-ink outline-none placeholder:text-dim"
      />
      <button
        onClick={onSend}
        disabled={busy || !input.trim()}
        aria-label="Send"
        className={`flex h-9 w-9 flex-shrink-0 cursor-pointer items-center justify-center rounded-[9px] border-none text-accent-ink transition-colors ${
          input.trim() && !busy ? "bg-accent" : "bg-[#1B3A44]"
        }`}
      >
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
          <path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
    </div>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [activeCat, setActiveCat] = useState("Trending");
  const [domain, setDomain] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const clear = () => setMessages([]);
    window.addEventListener("datagen:new-chat", clear);
    return () => window.removeEventListener("datagen:new-chat", clear);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, activeTool]);

  async function send() {
    const q = input.trim();
    if (!q || busy) return;

    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setInput("");
    setBusy(true);

    const sqls: string[] = [];
    await sendChatMessage(
      q,
      (event: ChatEvent) => {
        switch (event.type) {
          case "tool_call":
            setActiveTool(event.tool);
            if (event.tool === "execute_sql" && typeof event.arguments.sql === "string") {
              sqls.push(event.arguments.sql);
            }
            break;
          case "final":
            setMessages((prev) => [
              ...prev,
              { role: "assistant", text: event.content, sql: sqls.at(-1) },
            ]);
            break;
          case "blocked":
            setMessages((prev) => [...prev, { role: "system", text: event.reason }]);
            break;
          case "error":
            setMessages((prev) => [...prev, { role: "system", text: event.content }]);
            break;
        }
      },
      domain || undefined,
    );

    setActiveTool(null);
    setBusy(false);
  }

  const hasMessages = messages.length > 0;

  return (
    <>
      {hasMessages ? (
        <>
          {/* ── conversation ── */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto pb-5 pt-3">
            <div className="mx-auto flex max-w-[760px] flex-col gap-[22px] px-[26px]">
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div className="dg-bubble max-w-[82%]">
                    <div
                      className={`mb-[7px] font-mono text-[10px] uppercase tracking-[0.1em] ${
                        m.role === "user"
                          ? "text-dim"
                          : m.role === "system"
                            ? "text-[#F26D6D]"
                            : "text-accent"
                      }`}
                    >
                      {m.role === "user" ? "You" : m.role === "system" ? "Notice" : "DataGen"}
                    </div>
                    <div
                      className={`rounded-xl border px-4 py-3.5 text-[14.5px] leading-relaxed text-ink ${
                        m.role === "user"
                          ? "border-[#22344A] bg-card-hover"
                          : m.role === "system"
                            ? "border-[#F26D6D]/40 bg-[#F26D6D]/5"
                            : "border-edge2 bg-card"
                      }`}
                    >
                      {m.role === "assistant" ? (
                        <div className="prose prose-sm prose-invert max-w-none prose-a:text-accent prose-code:text-accent2 prose-strong:text-ink">
                          <ReactMarkdown>{m.text}</ReactMarkdown>
                        </div>
                      ) : (
                        m.text
                      )}
                    </div>
                    {m.sql && (
                      <pre className="mt-2.5 overflow-x-auto rounded-[10px] border border-edge2 bg-panel px-4 py-3.5 font-mono text-[12.5px] leading-relaxed text-accent2">
                        {m.sql}
                      </pre>
                    )}
                  </div>
                </div>
              ))}

              {busy && (
                <div className="flex justify-start">
                  <div className="dg-bubble max-w-[82%]">
                    <div className="mb-[7px] font-mono text-[10px] uppercase tracking-[0.1em] text-accent">
                      DataGen
                    </div>
                    <div className="flex items-center gap-2.5 rounded-xl border border-edge2 bg-card px-4 py-3.5 font-mono text-[12.5px] text-dim">
                      <span className="h-[7px] w-[7px] animate-pulse rounded-full bg-accent" />
                      {activeTool ? (TOOL_LABELS[activeTool] ?? `${activeTool}…`) : "Thinking…"}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ── pinned composer ── */}
          <div className="flex-shrink-0 border-t border-edge px-[26px] pb-[22px] pt-3.5">
            <div className="mx-auto max-w-[760px]">
              <Composer
                input={input}
                onInput={setInput}
                onSend={send}
                busy={busy}
                placeholder="Ask a follow-up…"
                compact
              />
            </div>
          </div>
        </>
      ) : (
        /* ── empty state ── */
        <div className="flex flex-1 flex-col items-center overflow-y-auto px-[26px]">
          <div className="mt-[9vh] w-full max-w-[880px]">
            <div className="mb-[26px] flex justify-center">
              <label className="flex cursor-pointer items-center gap-2 rounded-[9px] border border-edge2 bg-card px-3.5 py-2 text-[13px] text-muted transition hover:border-accent">
                <span className="inline-flex text-accent">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                    <path d="M4 7h16M4 12h16M4 17h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </span>
                <select
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  className="cursor-pointer appearance-none bg-transparent text-muted outline-none"
                >
                  {DOMAINS.map((d) => (
                    <option key={d.value} value={d.value} className="bg-card text-ink">
                      {d.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mb-10 flex items-center justify-center gap-4">
              <span className="text-ink">
                <LogoMark size={40} />
              </span>
              <h1 className="text-[28px] font-bold tracking-[-0.02em] md:text-[38px]">
                What should we query today?
              </h1>
            </div>

            <div className="mb-[26px]">
              <Composer
                input={input}
                onInput={setInput}
                onSend={send}
                busy={busy}
                placeholder="Ask anything about your data — SQL, trends, anomalies."
              />
              <div className="mt-3 flex items-center gap-2">
                <Link
                  href="/report"
                  className="flex items-center gap-1.5 rounded-lg border border-edge2 px-[11px] py-1.5 text-[12.5px] text-muted no-underline transition hover:border-accent hover:text-ink"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                    <rect x="4" y="4" width="16" height="16" rx="2" stroke="currentColor" strokeWidth="1.8" />
                    <path d="M8 9h8M8 13h5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                  </svg>
                  Insight Report
                </Link>
                <Link
                  href="/upload"
                  className="flex items-center gap-1.5 rounded-lg border border-edge2 px-[11px] py-1.5 text-[12.5px] text-muted no-underline transition hover:border-accent hover:text-ink"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                    <path d="M12 16V4M7 9l5-5 5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    <path d="M4 20h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                  </svg>
                  Upload data
                </Link>
              </div>
            </div>

            {/* category chips */}
            <div className="mb-7 flex flex-wrap justify-center gap-2.5">
              {CATEGORIES.map((cat) => {
                const active = cat === activeCat;
                return (
                  <button
                    key={cat}
                    onClick={() => setActiveCat(cat)}
                    className={`cursor-pointer rounded-[20px] border px-[15px] py-2 text-[13px] transition ${
                      active
                        ? "border-accent bg-accent/10 text-ink"
                        : "border-edge2 bg-transparent text-[#8FA3B5] hover:border-accent hover:text-ink"
                    }`}
                  >
                    {cat}
                  </button>
                );
              })}
            </div>

            {/* example questions */}
            <div className="mb-10 flex flex-col overflow-hidden rounded-[14px] border border-edge2 bg-card">
              {EXAMPLE_QUESTIONS.map((q, i) => (
                <button
                  key={q}
                  onClick={() => setInput(q)}
                  className={`flex cursor-pointer items-center justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-card-hover ${
                    i === 0 ? "" : "border-t border-divider"
                  }`}
                >
                  <span className="text-[14.5px] text-soft">{q}</span>
                  <span className="inline-flex flex-shrink-0 text-ghost">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                      <path d="M7 17L17 7M8 7h9v9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
