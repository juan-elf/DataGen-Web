"use client";

import { useState } from "react";
import Link from "next/link";
import { loadSampleData, uploadFile, type UploadResult } from "@/lib/api";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [tableName, setTableName] = useState("");
  const [ifExists, setIfExists] = useState<"fail" | "replace" | "append">("fail");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await uploadFile(file, { tableName: tableName || undefined, ifExists });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleSample() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await loadSampleData());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto px-[26px] pb-10">
      <div className="mx-auto w-full max-w-[680px] pt-[4vh]">
        <div className="mb-[18px] font-mono text-xs uppercase tracking-[0.16em] text-accent">
          Ingest
        </div>
        <h1 className="mb-2 text-[28px] font-bold tracking-[-0.02em]">Upload your data</h1>
        <p className="mb-8 text-sm leading-relaxed text-muted">
          CSV or Excel. It lands as a new table in your own isolated workspace — then head to{" "}
          <Link href="/chat" className="text-accent hover:text-accent2">
            Chat
          </Link>{" "}
          to ask questions, or{" "}
          <Link href="/report" className="text-accent hover:text-accent2">
            Insight Report
          </Link>{" "}
          for an autonomous analysis.
        </p>

        {/* Try-before-you-upload: removes the trust barrier for first-time visitors. */}
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-[14px] border border-accent/30 bg-accent/5 px-5 py-4">
          <div>
            <div className="text-sm font-semibold text-ink">Don&apos;t want to upload anything yet?</div>
            <div className="mt-0.5 text-[12.5px] text-muted">
              Load a sample e-commerce dataset (420 orders) and try the full flow.
            </div>
          </div>
          <button
            onClick={handleSample}
            disabled={busy}
            className="cursor-pointer rounded-lg border border-accent bg-transparent px-4 py-2 text-[13px] font-semibold text-accent transition hover:bg-accent hover:text-accent-ink disabled:cursor-default disabled:opacity-40"
          >
            {busy ? "Loading…" : "Try with sample data"}
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-5 rounded-[14px] border border-edge2 bg-card p-7"
        >
          <label className="flex cursor-pointer flex-col items-center justify-center gap-3 rounded-[10px] border border-dashed border-[#24374C] px-6 py-10 text-center transition hover:border-accent">
            <span className="text-accent">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
                <path d="M12 16V4M7 9l5-5 5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M4 20h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </span>
            <span className="text-sm text-soft">
              {file ? file.name : "Choose a .csv, .xlsx, or .xls file"}
            </span>
            <span className="font-mono text-[11px] text-dim">max 15MB · 500k rows · 200 columns</span>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="hidden"
            />
          </label>

          <label className="flex flex-col gap-1.5 text-[13px] text-muted">
            Table name{" "}
            <span className="font-mono text-[11px] text-dim">
              optional — derived from filename if blank
            </span>
            <input
              type="text"
              value={tableName}
              onChange={(e) => setTableName(e.target.value)}
              placeholder="e.g. sales_2024"
              className="rounded-lg border border-edge2 bg-panel px-3.5 py-2.5 text-sm text-ink outline-none transition placeholder:text-dim focus:border-accent"
            />
          </label>

          <label className="flex flex-col gap-1.5 text-[13px] text-muted">
            If the table already exists
            <select
              value={ifExists}
              onChange={(e) => setIfExists(e.target.value as typeof ifExists)}
              className="cursor-pointer rounded-lg border border-edge2 bg-panel px-3.5 py-2.5 text-sm text-ink outline-none transition focus:border-accent"
            >
              <option value="fail">Fail (default — safest)</option>
              <option value="replace">Replace</option>
              <option value="append">Append</option>
            </select>
          </label>

          <button
            type="submit"
            disabled={!file || busy}
            className="cursor-pointer rounded-lg border-none bg-accent px-6 py-3 text-[15px] font-semibold text-accent-ink transition hover:bg-accent2 disabled:cursor-default disabled:opacity-40"
          >
            {busy ? "Uploading…" : "Upload"}
          </button>
        </form>

        {/* Honest data-handling note. Deliberately states that data reaches the LLM
            provider — overclaiming privacy would be worse than saying nothing. */}
        <div className="mt-5 rounded-[14px] border border-edge2 bg-panel p-5">
          <div className="mb-2.5 font-mono text-[10px] uppercase tracking-[0.14em] text-dim">
            What happens to your data
          </div>
          <ul className="flex flex-col gap-1.5 text-[12.5px] leading-relaxed text-muted">
            <li>· Loaded into an isolated Postgres schema that only your session can query.</li>
            <li>· Automatically deleted after 7 days of inactivity — or instantly, via Delete my data in the sidebar.</li>
            <li>· Questions are answered with read-only SQL; the agent can never write to your tables.</li>
            <li>
              · To answer a question, your table structure and small result excerpts are sent to
              the LLM provider (OpenRouter).{" "}
              <span className="text-soft">Please don&apos;t upload sensitive or personal data.</span>
            </li>
          </ul>
        </div>

        {error && (
          <p className="mt-5 rounded-[10px] border border-[#F26D6D]/40 bg-[#F26D6D]/5 px-4 py-3.5 text-sm text-[#F58C8C]">
            {error}
          </p>
        )}

        {result && (
          <div className="mt-5 rounded-[14px] border border-edge2 bg-card p-6 text-sm">
            <p className="font-semibold text-ink">
              ✅ {result.rows.toLocaleString()} rows loaded into{" "}
              <code className="font-mono text-accent2">{result.table}</code>
            </p>
            <p className="mt-1.5 text-muted">Columns: {result.columns.join(", ")}</p>
            {result.warnings.length > 0 && (
              <ul className="mt-2.5 list-inside list-disc text-[#E8C468]">
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
            <pre className="mt-4 max-h-64 overflow-auto whitespace-pre-wrap rounded-[10px] border border-edge2 bg-panel px-4 py-3.5 font-mono text-xs leading-relaxed text-muted">
              {result.profile_preview}
            </pre>
            <Link
              href="/chat"
              className="mt-4 inline-block rounded-lg bg-accent px-5 py-2.5 text-sm font-semibold text-accent-ink no-underline transition hover:bg-accent2"
            >
              Start asking questions →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
