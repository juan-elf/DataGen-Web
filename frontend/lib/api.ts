import { consumeSSE } from "./sse";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Workspace identity ──────────────────────────────────────────────────────
// The backend and frontend live on different domains (Render vs Vercel), so a
// cookie can't carry workspace identity cross-site. Instead the backend hands
// back a signed token in the `X-Workspace-Id` response header; we persist it in
// localStorage (first-party — unaffected by third-party cookie blocking) and
// echo it on every request. See backend/db/context.py.
const WORKSPACE_KEY = "datagen_workspace_id";
const WORKSPACE_HEADER = "X-Workspace-Id";

function loadWorkspaceId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(WORKSPACE_KEY);
}

function captureWorkspaceId(response: Response): void {
  if (typeof window === "undefined") return;
  const id = response.headers.get(WORKSPACE_HEADER);
  if (id) window.localStorage.setItem(WORKSPACE_KEY, id);
}

/** Merge the stored workspace token into a request's headers, if we have one. */
function withWorkspace(extra: Record<string, string> = {}): Record<string, string> {
  const id = loadWorkspaceId();
  return id ? { ...extra, [WORKSPACE_HEADER]: id } : extra;
}

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
    headers: withWorkspace(),
    body: form,
  });
  captureWorkspaceId(response);

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
    headers: withWorkspace({ "Content-Type": "application/json" }),
    body: JSON.stringify({ message, domain }),
  });
  captureWorkspaceId(response);

  if (!response.ok) {
    onEvent({ type: "error", content: await parseErrorDetail(response) });
    return;
  }
  await consumeSSE<ChatEvent>(response, onEvent);
}

export async function resetChat(): Promise<void> {
  const response = await fetch(`${API_URL}/chat/reset`, {
    method: "POST",
    credentials: "include",
    headers: withWorkspace(),
  });
  captureWorkspaceId(response);
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
    headers: withWorkspace(),
  });
  captureWorkspaceId(response);

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
    headers: withWorkspace({ "Content-Type": "application/json" }),
    body: JSON.stringify({ sql, code }),
  });
  captureWorkspaceId(response);

  if (!response.ok) {
    throw new Error(await parseErrorDetail(response));
  }
  return response.json();
}
