import { consumeSSE } from "./sse";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body.detail ?? response.statusText;
  } catch {
    return response.statusText;
  }
}

// ── Upload ──────────────────────────────────────────────────────────────────

export interface UploadResult {
  success: boolean;
  table: string;
  rows: number;
  columns: string[];
  column_mapping: Record<string, string>;
  warnings: string[];
  profile_preview: string;
}

export async function uploadFile(
  file: File,
  options: { tableName?: string; ifExists?: "fail" | "replace" | "append" } = {},
): Promise<UploadResult> {
  const form = new FormData();
  form.append("file", file);
  if (options.tableName) form.append("table_name", options.tableName);
  form.append("if_exists", options.ifExists ?? "fail");

  const response = await fetch(`${API_URL}/upload`, {
    method: "POST",
    credentials: "include",
    body: form,
  });

  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }
  return response.json();
}

// ── Chat ────────────────────────────────────────────────────────────────────

export type ChatEvent =
  | { type: "blocked"; reason: string }
  | { type: "iteration"; n: number }
  | { type: "tool_call"; tool: string; arguments: Record<string, unknown> }
  | { type: "tool_result"; tool: string; result: string }
  | { type: "final"; content: string }
  | { type: "error"; content: string };

export async function sendChatMessage(
  message: string,
  onEvent: (event: ChatEvent) => void,
  domain?: string,
): Promise<void> {
  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, domain }),
  });

  if (!response.ok) {
    onEvent({ type: "error", content: await parseErrorDetail(response) });
    return;
  }
  await consumeSSE<ChatEvent>(response, onEvent);
}

export async function resetChat(): Promise<void> {
  await fetch(`${API_URL}/chat/reset`, { method: "POST", credentials: "include" });
}

// ── Insight Report ────────────────────────────────────────────────────────────

export interface ReportFinding {
  question: string;
  sql: string;
  type: string;
  rows: Record<string, unknown>[];
  error: string | null;
  is_anomaly: boolean;
}

export interface ReportResult {
  title: string;
  db_label: string;
  generated_at: string;
  narrative: string;
  executive_summary: string;
  findings: ReportFinding[];
  recommendations: string;
  errors: string[];
}

export type ReportEvent =
  | { type: "progress"; step: string; detail: string }
  | { type: "result"; data: ReportResult }
  | { type: "error"; content: string };

export async function generateReport(onEvent: (event: ReportEvent) => void): Promise<void> {
  const response = await fetch(`${API_URL}/report`, {
    method: "POST",
    credentials: "include",
  });

  if (!response.ok) {
    onEvent({ type: "error", content: await parseErrorDetail(response) });
    return;
  }
  await consumeSSE<ReportEvent>(response, onEvent);
}

// ── Ad-hoc analysis ───────────────────────────────────────────────────────────

export interface AnalysisResult {
  success: boolean;
  result?: unknown;
  rows_analyzed?: number;
  columns_used?: string[];
  error?: string;
  hint?: string;
}

export async function runAnalysis(sql: string, code: string): Promise<AnalysisResult> {
  const response = await fetch(`${API_URL}/analysis`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql, code }),
  });

  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }
  return response.json();
}
