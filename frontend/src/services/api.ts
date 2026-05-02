import type { ChatResponse, VoiceChatResponse } from "../types/ui";

/** Dev: relative `/api/v1` + Vite proxy → backend (works from phone via LAN IP). Prod: set VITE_API_BASE if needed. */
const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined)?.trim() ||
  (import.meta.env.DEV ? "/api/v1" : "http://localhost:8000/api/v1");

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

export type VoiceStreamCallbacks = {
  /** Fired as soon as server STT finishes (before LLM) — improves perceived latency / Network TTFB. */
  onTranscript?: (text: string) => void;
  onToken: (chunk: string) => void;
  /** Incremental TTS WAV path under API base (streaming voice only). */
  onTtsChunk?: (audioUrl: string, snippet: string) => void;
  onDone: (response: VoiceChatResponse) => void;
  onError: (message: string) => void;
};

function emitSmallestTextChunks(text: string, onChunk: (chunk: string) => void): void {
  // Emit by Unicode code points for near-token real-time UI updates.
  for (const ch of Array.from(text)) onChunk(ch);
}

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
  let sawTerminal = false;
  try {
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
            if (j.t) emitSmallestTextChunks(j.t, callbacks.onToken);
          } catch {
            /* ignore malformed chunk */
          }
        } else if (ev === "done") {
          sawTerminal = true;
          try {
            callbacks.onDone(JSON.parse(data) as ChatResponse);
          } catch {
            callbacks.onError("Invalid chat response payload.");
          }
        } else if (ev === "error") {
          sawTerminal = true;
          try {
            const j = JSON.parse(data) as { detail?: string };
            callbacks.onError(j.detail ?? "Request failed");
          } catch {
            callbacks.onError(data || "Request failed");
          }
        }
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* already released */
    }
  }
  if (!sawTerminal) {
    callbacks.onError("Connection closed before the reply finished.");
  }
}

/** SSE `POST /voice-chat/stream` multipart — token deltas, then final VoiceChatResponse. */
export async function apiPostVoiceStream(
  formData: FormData,
  callbacks: VoiceStreamCallbacks,
): Promise<void> {
  const res = await fetch(`${API_BASE}/voice-chat/stream`, {
    method: "POST",
    headers: { Accept: "text/event-stream" },
    body: formData,
  });
  if (!res.ok) {
    // Backward-compatible fallback: if streaming route is not available,
    // use regular multipart voice-chat endpoint.
    if (res.status === 404 || res.status === 405 || res.status === 501) {
      const fallback = await fetch(`${API_BASE}/voice-chat`, {
        method: "POST",
        body: formData,
      });
      if (!fallback.ok) {
        const text = await fallback.text();
        throw new Error(
          `POST /voice-chat failed: ${fallback.status}${text ? ` — ${text.slice(0, 200)}` : ""}`,
        );
      }
      try {
        const body = (await fallback.json()) as VoiceChatResponse;
        callbacks.onDone(body);
      } catch {
        throw new Error("Voice response was not valid JSON.");
      }
      return;
    }
    const text = await res.text();
    throw new Error(
      `POST /voice-chat/stream failed: ${res.status}${text ? ` — ${text.slice(0, 200)}` : ""}`,
    );
  }
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");
  const dec = new TextDecoder();
  let buf = "";
  let sawTerminal = false;
  try {
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
        if (ev === "transcript") {
          try {
            const j = JSON.parse(data) as { t?: string };
            if (typeof j.t === "string" && callbacks.onTranscript) callbacks.onTranscript(j.t);
          } catch {
            /* ignore */
          }
        } else if (ev === "token") {
          try {
            const j = JSON.parse(data) as { t?: string };
            if (j.t) emitSmallestTextChunks(j.t, callbacks.onToken);
          } catch {
            /* ignore malformed chunk */
          }
        } else if (ev === "tts_chunk") {
          try {
            const j = JSON.parse(data) as { audio_url?: string; t?: string };
            const au = j.audio_url?.trim();
            if (au && callbacks.onTtsChunk) callbacks.onTtsChunk(au, j.t ?? "");
          } catch {
            /* ignore */
          }
        } else if (ev === "done") {
          sawTerminal = true;
          try {
            callbacks.onDone(JSON.parse(data) as VoiceChatResponse);
          } catch {
            callbacks.onError("Invalid voice response payload.");
          }
        } else if (ev === "error") {
          sawTerminal = true;
          try {
            const j = JSON.parse(data) as { detail?: string };
            callbacks.onError(j.detail ?? "Request failed");
          } catch {
            callbacks.onError(data || "Request failed");
          }
        }
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* already released */
    }
  }
  if (!sawTerminal) {
    callbacks.onError("Connection closed before the voice reply finished.");
  }
}
