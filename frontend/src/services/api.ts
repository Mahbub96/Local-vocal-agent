import type { ChatResponse } from "../types/ui";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";

export const USER_ID = "ui-user";
export const apiBase = API_BASE;

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return (await res.json()) as T;
}

export type ApiFormDataOptions = {
  /** Default 10 minutes — voice pipeline can include STT + LLM + TTS cold start. */
  timeoutMs?: number;
};

const DEFAULT_FORM_TIMEOUT_MS = 600_000;

/** Multipart POST (e.g. voice upload). Do not set `Content-Type` — browser sets boundary. */
export async function apiPostFormData<T>(
  path: string,
  formData: FormData,
  options?: ApiFormDataOptions,
): Promise<T> {
  const timeoutMs = options?.timeoutMs ?? DEFAULT_FORM_TIMEOUT_MS;
  const controller = new AbortController();
  const tid = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`POST ${path} failed: ${res.status}${text ? ` — ${text.slice(0, 200)}` : ""}`);
    }
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error(`POST ${path} timed out after ${Math.round(timeoutMs / 1000)}s`, { cause: e });
    }
    throw e;
  } finally {
    clearTimeout(tid);
  }
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`);
  return (await res.json()) as T;
}

export type ChatStreamCallbacks = {
  onToken: (chunk: string) => void;
  onDone: (response: ChatResponse) => void;
  onError: (message: string) => void;
};

/** SSE `POST /chat/stream` — `token` deltas then `done` with `ChatResponse`. */
export async function apiPostChatStream(
  body: { message: string; user_id: string; session_id?: string },
  callbacks: ChatStreamCallbacks,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(
      `POST /chat/stream failed: ${res.status}${text ? ` — ${text.slice(0, 200)}` : ""}`,
    );
  }
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let sep: number;
    while ((sep = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, sep);
      buf = buf.slice(sep + 2);
      let ev = "";
      const dataLines: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) ev = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      }
      const data = dataLines.join("\n");
      if (!ev || !data) continue;
      if (ev === "token") {
        try {
          const j = JSON.parse(data) as { t?: string };
          if (j.t) callbacks.onToken(j.t);
        } catch {
          /* ignore malformed chunk */
        }
      } else if (ev === "done") {
        callbacks.onDone(JSON.parse(data) as ChatResponse);
      } else if (ev === "error") {
        try {
          const j = JSON.parse(data) as { detail?: string };
          callbacks.onError(j.detail ?? "Request failed");
        } catch {
          callbacks.onError(data || "Request failed");
        }
      }
    }
  }
}
