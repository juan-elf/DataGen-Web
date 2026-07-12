"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { generateReport, type ReportEvent, type ReportResult } from "@/lib/api";

export default function ReportPage() {
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const [result, setResult] = useState<ReportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    setBusy(true);
    setError(null);
    setResult(null);
    setProgress(null);

    await generateReport((event: ReportEvent) => {
      if (event.type === "progress") {
        setProgress(event.detail || event.step);
      } else if (event.type === "result") {
        setResult(event.data);
      } else if (event.type === "error") {
        setError(event.content);
      }
    });

    setBusy(false);
    setProgress(null);
  }

  function downloadMarkdown() {
    if (!result) return;
    const blob = new Blob([result.narrative], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `insight_report_${result.generated_at.replace(/[: ]/g, "-")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex-1 overflow-y-auto px-[26px] pb-10">
      <div className="mx-auto w-full max-w-[760px] pt-[4vh]">
        <div className="mb-[18px] font-mono text-xs uppercase tracking-[0.16em] text-accent">
          Autonomous analyst
        </div>
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="mb-1 text-[28px] font-bold tracking-[-0.02em]">Insight Report</h1>
            <p className="text-sm text-muted">
              The agent profiles your data, plans its own questions, runs the SQL, flags anomalies,
              and writes the narrative.
            </p>
          </div>
          <button
            onClick={handleGenerate}
            disabled={busy}
            className="cursor-pointer rounded-lg border-none bg-accent px-6 py-3 text-[15px] font-semibold text-accent-ink transition hover:bg-accent2 disabled:cursor-default disabled:opacity-40"
          >
            {busy ? "Generating…" : "Generate report"}
          </button>
        </div>

        {busy && (
          <div className="mb-6 flex items-center gap-2.5 rounded-[10px] border border-edge2 bg-card px-4 py-3.5 font-mono text-[12.5px] text-dim">
            <span className="h-[7px] w-[7px] animate-pulse rounded-full bg-accent" />
            {progress ?? "Starting…"}
          </div>
        )}

        {error && (
          <p className="rounded-[10px] border border-[#F26D6D]/40 bg-[#F26D6D]/5 px-4 py-3.5 text-sm text-[#F58C8C]">
            {error}
          </p>
        )}

        {result && (
          <div className="rounded-[14px] border border-edge2 bg-card p-8">
            <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-divider pb-5">
              <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-dim">
                {result.generated_at}
              </div>
              <button
                onClick={downloadMarkdown}
                className="cursor-pointer rounded-lg border border-edge3 bg-transparent px-3.5 py-2 text-[12.5px] font-semibold text-ink transition hover:border-accent hover:text-accent"
              >
                Download .md
              </button>
            </div>

            {result.errors.length > 0 && (
              <p className="mb-4 text-sm text-[#E8C468]">{result.errors.join(", ")}</p>
            )}

            <article className="prose prose-sm prose-invert max-w-none prose-headings:tracking-tight prose-a:text-accent prose-code:text-accent2 prose-strong:text-ink">
              <ReactMarkdown>{result.narrative}</ReactMarkdown>
            </article>

            {result.findings.some((f) => f.is_anomaly) && (
              <div className="mt-6 border-t border-divider pt-5">
                <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.14em] text-[#E8C468]">
                  ⚠ Anomalies flagged
                </div>
                <ul className="flex list-inside list-disc flex-col gap-1.5 text-sm text-muted">
                  {result.findings
                    .filter((f) => f.is_anomaly)
                    .map((f, i) => (
                      <li key={i}>{f.question}</li>
                    ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
