"use client";

/**
 * Client-side chat session history, persisted to localStorage.
 *
 * Why localStorage and not the backend: workspace identity is already anonymous
 * and browser-local (see lib/api.ts), and the backend keeps only a single live
 * conversation per workspace in memory. So the browser is the natural source of
 * truth for "my past chats". Each session is a saved transcript; the live
 * backend agent tracks context for whichever session is currently active.
 *
 * Implemented as a module-level external store read via useSyncExternalStore.
 * That gives a stable server snapshot (empty) for SSR/hydration and a separate
 * client snapshot hydrated from localStorage — no hydration mismatch and no
 * setState-in-effect. No React Context/provider needed: it's a single
 * browser-global store.
 */
import { useSyncExternalStore } from "react";

export interface StoredMessage {
  role: "user" | "assistant" | "system";
  text: string;
  sql?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: StoredMessage[];
  updatedAt: number;
}

interface Snapshot {
  all: ChatSession[]; // includes the current empty draft; drafts aren't persisted
  activeId: string | null;
}

const STORAGE_KEY = "datagen_sessions";
const MAX_TITLE_LEN = 42;

// ── helpers ─────────────────────────────────────────────────────────────────

function deriveTitle(messages: StoredMessage[]): string {
  const firstUser = messages.find((m) => m.role === "user");
  if (!firstUser) return "New chat";
  const t = firstUser.text.trim().replace(/\s+/g, " ");
  return t.length > MAX_TITLE_LEN ? t.slice(0, MAX_TITLE_LEN) + "…" : t;
}

function newId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

function draftSession(): ChatSession {
  return { id: newId(), title: "New chat", messages: [], updatedAt: Date.now() };
}

function loadSessions(): ChatSession[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ChatSession[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

// ── external store ──────────────────────────────────────────────────────────

const SERVER_SNAPSHOT: Snapshot = { all: [], activeId: null };

let snapshot: Snapshot = SERVER_SNAPSHOT;
let initialized = false;
const listeners = new Set<() => void>();

function persist(all: ChatSession[]): void {
  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(all.filter((s) => s.messages.length > 0)),
    );
  } catch {
    /* quota / private mode — non-fatal */
  }
}

function setSnapshot(next: Snapshot): void {
  snapshot = next;
  persist(next.all);
  listeners.forEach((l) => l());
}

function ensureInit(): void {
  if (initialized) return;
  initialized = true;
  const loaded = loadSessions();
  if (loaded.length > 0) {
    snapshot = { all: loaded, activeId: loaded[0].id };
  } else {
    const d = draftSession();
    snapshot = { all: [d], activeId: d.id };
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getClientSnapshot(): Snapshot {
  ensureInit();
  return snapshot;
}

function getServerSnapshot(): Snapshot {
  return SERVER_SNAPSHOT;
}

// ── mutations ───────────────────────────────────────────────────────────────

function newSession(): void {
  ensureInit();
  const kept = snapshot.all.filter((s) => s.messages.length > 0);
  const d = draftSession();
  setSnapshot({ all: [d, ...kept], activeId: d.id });
}

function selectSession(id: string): void {
  ensureInit();
  // drop any empty draft other than the one being selected
  setSnapshot({
    all: snapshot.all.filter((s) => s.messages.length > 0 || s.id === id),
    activeId: id,
  });
}

function deleteSession(id: string): void {
  ensureInit();
  const remaining = snapshot.all.filter((s) => s.id !== id);
  if (id === snapshot.activeId) {
    const next = remaining.find((s) => s.messages.length > 0);
    if (next) {
      setSnapshot({ all: remaining, activeId: next.id });
    } else {
      const d = draftSession();
      setSnapshot({ all: [d], activeId: d.id });
    }
  } else {
    setSnapshot({ all: remaining, activeId: snapshot.activeId });
  }
}

function updateSessionMessages(
  id: string,
  updater: (prev: StoredMessage[]) => StoredMessage[],
): void {
  ensureInit();
  setSnapshot({
    activeId: snapshot.activeId,
    all: snapshot.all.map((s) => {
      if (s.id !== id) return s;
      const messages = updater(s.messages);
      return {
        ...s,
        messages,
        title: messages.length > 0 ? deriveTitle(messages) : s.title,
        updatedAt: Date.now(),
      };
    }),
  });
}

// ── hook ────────────────────────────────────────────────────────────────────

export interface UseSessions {
  /** Persisted sessions with at least one message, newest first. */
  sessions: ChatSession[];
  activeId: string | null;
  activeMessages: StoredMessage[];
  newSession: () => void;
  selectSession: (id: string) => void;
  deleteSession: (id: string) => void;
  updateSessionMessages: (
    id: string,
    updater: (prev: StoredMessage[]) => StoredMessage[],
  ) => void;
}

export function useSessions(): UseSessions {
  const snap = useSyncExternalStore(subscribe, getClientSnapshot, getServerSnapshot);
  const sessions = snap.all
    .filter((s) => s.messages.length > 0)
    .sort((a, b) => b.updatedAt - a.updatedAt);
  const active = snap.all.find((s) => s.id === snap.activeId);
  return {
    sessions,
    activeId: snap.activeId,
    activeMessages: active?.messages ?? [],
    newSession,
    selectSession,
    deleteSession,
    updateSessionMessages,
  };
}
