/* Data loads in effects intentionally sync server state into React; see React docs on data fetching. */
/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  apiBase,
  apiGet,
  apiPost,
  apiPostChatStream,
  apiPostVoiceStream,
  apiPut,
  USER_ID,
} from "../services/api";
import type {
  FileListResponse,
  Message,
  MessageFeedbackValue,
  Metrics,
  Profile,
  ProfileResponse,
  Session,
  SystemStatus,
  ThinkingProcess,
  ThinkingStep,
  ToolActivity,
  ToolActivityListResponse,
  UsageSummary,
  VoiceStatus,
} from "../types/ui";

/** One combined system poll (metrics + status); keeps backend quiet vs stacked intervals. */
const SYSTEM_POLL_MS = 10000;
const USAGE_POLL_MS = 30000;
const SSE_THINKING_MS = 2000;
const SSE_VOICE_MS = 2000;
/** Voice status SSE: long-lived while dashboard is open. */
const SSE_VOICE_MAX_EVENTS = 60;
/** Thinking panel SSE: shorter run avoids 2min open connections (60×2s); thinking also refreshes on chat. */
const SSE_THINKING_MAX_EVENTS = 20;

/** Recent messages for chat UI + aligns with server short-term context default (6). */
const RECENT_MESSAGES_LIMIT = 6;

export function useAuroraDashboard() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [thinking, setThinking] = useState<ThinkingStep[]>([]);
  const [activities, setActivities] = useState<ToolActivity[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [usageSummary, setUsageSummary] = useState<UsageSummary | null>(null);
  const [fileEntriesCount, setFileEntriesCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  /** Only while a voice clip is uploading/processing — hands-free waits on this, not on text chat `loading`. */
  const [voiceUploadBusy, setVoiceUploadBusy] = useState(false);
  const [error, setError] = useState("");
  const [streamingAssistantText, setStreamingAssistantText] = useState("");
  const [ttsRevealText, setTtsRevealText] = useState("");
  const [voiceGateHint, setVoiceGateHint] = useState("");
  /** Server STT result (SSE `transcript`) shown until reply completes — confirms early progress. */
  const [voiceSttPreview, setVoiceSttPreview] = useState("");
  /** True from TTS playback start-attempt until ended/stop — blocks overlapping hands-free turns. */
  const [ttsAudioPlaying, setTtsAudioPlaying] = useState(false);
  const voiceGateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const voiceAudioRef = useRef<HTMLAudioElement | null>(null);
  const ttsFullRef = useRef("");
  /** URLs for sequential playback of incremental voice TTS (`tts_chunk` SSE). */
  const ttsPlayQueueRef = useRef<string[]>([]);
  const ttsDrainLoopRef = useRef(false);
  /** Monotonic request id to ignore stale async completions. */
  const latestTurnRequestRef = useRef(0);
  const latestMessagesSessionRef = useRef("");
  const latestThinkingSessionRef = useRef("");
  const latestActivityKeyRef = useRef("");

  const beginTurnRequest = useCallback(() => {
    latestTurnRequestRef.current += 1;
    return latestTurnRequestRef.current;
  }, []);

  const isLatestTurnRequest = useCallback(
    (requestId: number) => latestTurnRequestRef.current === requestId,
    [],
  );

  const playStreamingTtsQueue = useCallback(
    async (requestId: number) => {
      if (ttsDrainLoopRef.current) return;
      ttsDrainLoopRef.current = true;
      try {
        while (isLatestTurnRequest(requestId)) {
          const url = ttsPlayQueueRef.current.shift();
          if (!url) break;
          setTtsAudioPlaying(true);
          await new Promise<void>((resolve) => {
            const audio = new Audio(url);
            voiceAudioRef.current = audio;
            audio.addEventListener("ended", () => resolve(), { once: true });
            audio.addEventListener("error", () => resolve(), { once: true });
            void audio.play().catch(() => resolve());
          });
        }
      } finally {
        voiceAudioRef.current = null;
        ttsDrainLoopRef.current = false;
        if (!isLatestTurnRequest(requestId)) {
          ttsPlayQueueRef.current = [];
        }
        const more = ttsPlayQueueRef.current.length > 0;
        setTtsAudioPlaying(more);
        if (more && isLatestTurnRequest(requestId)) {
          void playStreamingTtsQueue(requestId);
        }
      }
    },
    [isLatestTurnRequest],
  );

  const queueStreamingTtsUrl = useCallback(
    (requestId: number, audioUrlRelative: string) => {
      const base = apiBase.replace(/\/$/, "");
      const path = audioUrlRelative.replace(/^\//, "");
      ttsPlayQueueRef.current.push(`${base}/${path}`);
      void playStreamingTtsQueue(requestId);
    },
    [playStreamingTtsQueue],
  );

  /** Drop decode buffers and network hold on TTS `Audio` (prevents leaks on repeated playback / unmount). */
  const releaseVoiceAudio = useCallback(() => {
    setTtsAudioPlaying(false);
    ttsPlayQueueRef.current = [];
    ttsDrainLoopRef.current = false;
    const a = voiceAudioRef.current;
    if (!a) return;
    a.pause();
    a.src = "";
    a.removeAttribute("src");
    void a.load();
    voiceAudioRef.current = null;
    setTtsRevealText("");
    ttsFullRef.current = "";
  }, []);

  useEffect(() => {
    return () => releaseVoiceAudio();
  }, [releaseVoiceAudio]);

  useEffect(() => {
    return () => {
      if (voiceGateTimerRef.current) clearTimeout(voiceGateTimerRef.current);
    };
  }, []);

  const loadSessions = useCallback(async () => {
    const data = await apiGet<{ sessions: Session[] }>(`/sessions?user_id=${USER_ID}&limit=20`);
    setSessions(data.sessions);
    setActiveSessionId((prev) => prev || data.sessions[0]?.session_id || "");
  }, []);

  const loadMessages = useCallback(async (sessionId: string) => {
    latestMessagesSessionRef.current = sessionId;
    const data = await apiGet<{ messages: Message[] }>(
      `/sessions/${sessionId}/messages?limit=${RECENT_MESSAGES_LIMIT}`,
    );
    if (latestMessagesSessionRef.current !== sessionId) return;
    setMessages(data.messages);
  }, []);

  const loadSystemOverview = useCallback(async () => {
    const data = await apiGet<{ metrics: Metrics; status: SystemStatus }>("/system/overview");
    setMetrics(data.metrics);
    setSystemStatus(data.status);
  }, []);

  const loadProfile = useCallback(async () => {
    const data = await apiGet<ProfileResponse>(`/profile?user_id=${USER_ID}`);
    setProfile(data.profile);
  }, []);

  const loadUsageSummary = useCallback(async () => {
    const data = await apiGet<UsageSummary>(`/usage/summary?user_id=${USER_ID}`);
    setUsageSummary(data);
  }, []);

  const loadThinking = useCallback(async (sessionId: string) => {
    latestThinkingSessionRef.current = sessionId;
    const data = await apiGet<ThinkingProcess>(`/sessions/${sessionId}/thinking-process`);
    if (latestThinkingSessionRef.current !== sessionId) return;
    setThinking(data.steps);
  }, []);

  const loadToolActivity = useCallback(async (sessionId: string | undefined) => {
    const key = sessionId ?? "__all__";
    latestActivityKeyRef.current = key;
    const q = new URLSearchParams({ limit: "8" });
    if (sessionId) q.set("session_id", sessionId);
    const data = await apiGet<ToolActivityListResponse>(`/tools/activity?${q.toString()}`);
    if (latestActivityKeyRef.current !== key) return;
    setActivities(data.activities);
  }, []);

  const loadVoiceSnapshot = useCallback(async () => {
    const data = await apiGet<VoiceStatus>("/voice/status");
    setVoiceStatus(data);
  }, []);

  const loadFilesRoot = useCallback(async () => {
    const data = await apiGet<FileListResponse>("/files?limit=200");
    setFileEntriesCount(data.entries.length);
  }, []);

  useEffect(() => {
    void loadSessions().catch((e) => setError(String(e)));
    void loadProfile().catch((e) => setError(String(e)));
    void loadToolActivity(undefined).catch((e) => setError(String(e)));
    void loadVoiceSnapshot().catch(() => {
      /* voice service optional at cold start */
    });
    void loadFilesRoot().catch(() => setFileEntriesCount(null));
  }, [loadSessions, loadProfile, loadToolActivity, loadVoiceSnapshot, loadFilesRoot]);

  const pollSystem = useCallback(async () => {
    try {
      await loadSystemOverview();
    } catch (e) {
      setError(String(e));
    }
  }, [loadSystemOverview]);

  useEffect(() => {
    void pollSystem().catch((e) => setError(String(e)));
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void pollSystem().catch(() => undefined);
      }
    }, SYSTEM_POLL_MS);
    const onVis = () => {
      if (document.visibilityState === "visible") {
        void pollSystem().catch(() => undefined);
      }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [pollSystem]);

  useEffect(() => {
    void loadUsageSummary().catch((e) => setError(String(e)));
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void loadUsageSummary().catch(() => undefined);
      }
    }, USAGE_POLL_MS);
    return () => clearInterval(id);
  }, [loadUsageSummary]);

  useEffect(() => {
    if (!activeSessionId) return;
    void loadMessages(activeSessionId).catch((e) => setError(String(e)));
    void loadThinking(activeSessionId).catch((e) => setError(String(e)));
    void loadToolActivity(activeSessionId).catch((e) => setError(String(e)));
  }, [activeSessionId, loadMessages, loadThinking, loadToolActivity]);

  useEffect(() => {
    const source = new EventSource(
      `${apiBase}/voice/status-stream?interval_ms=${SSE_VOICE_MS}&max_events=${SSE_VOICE_MAX_EVENTS}`,
    );
    source.addEventListener("voice_status", (event) => {
      try {
        setVoiceStatus(JSON.parse((event as MessageEvent).data) as VoiceStatus);
      } catch {
        /* ignore */
      }
    });
    source.onerror = () => source.close();
    return () => source.close();
  }, []);

  useEffect(() => {
    if (!activeSessionId) return;
    const source = new EventSource(
      `${apiBase}/sessions/${activeSessionId}/thinking-stream?interval_ms=${SSE_THINKING_MS}&max_events=${SSE_THINKING_MAX_EVENTS}`,
    );
    source.addEventListener("thinking_update", (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data) as ThinkingProcess;
        setThinking(payload.steps);
      } catch {
        /* ignore */
      }
    });
    source.onerror = () => source.close();
    return () => source.close();
  }, [activeSessionId]);

  const sendMessage = useCallback(async () => {
    if (!input.trim()) return;
    const requestId = beginTurnRequest();
    setLoading(true);
    setError("");
    setStreamingAssistantText("");
    setTtsRevealText("");
    try {
      await apiPostChatStream(
        {
          message: input.trim(),
          user_id: USER_ID,
          session_id: activeSessionId || undefined,
        },
        {
          onToken: (t) => {
            if (!isLatestTurnRequest(requestId)) return;
            setStreamingAssistantText((prev) => prev + t);
          },
          onDone: async (result) => {
            if (!isLatestTurnRequest(requestId)) return;
            setInput("");
            // Keep streamed text visible until persisted messages are reloaded.
            // This prevents the UI from collapsing to "all at once" on fast done events.
            setStreamingAssistantText((prev) => prev || result.response || "");
            const sid = result.session_id;
            await loadSessions();
            if (!isLatestTurnRequest(requestId)) return;
            setActiveSessionId(sid);
            await Promise.all([
              loadMessages(sid),
              loadThinking(sid),
              loadToolActivity(sid),
              loadUsageSummary(),
              loadProfile(),
            ]);
            if (!isLatestTurnRequest(requestId)) return;
            setStreamingAssistantText("");
          },
          onError: (msg) => {
            if (!isLatestTurnRequest(requestId)) return;
            setError(msg);
            setStreamingAssistantText("");
          },
        },
      );
    } catch (err) {
      if (!isLatestTurnRequest(requestId)) return;
      setError(String(err));
      setStreamingAssistantText("");
    } finally {
      if (isLatestTurnRequest(requestId)) {
        setLoading(false);
      }
    }
  }, [
    input,
    activeSessionId,
    beginTurnRequest,
    isLatestTurnRequest,
    loadSessions,
    loadMessages,
    loadThinking,
    loadToolActivity,
    loadUsageSummary,
    loadProfile,
  ]);

  const stopVoicePlayback = releaseVoiceAudio;

  const sendVoiceBlob = useCallback(
    async (blob: Blob, transcriptHint?: string) => {
      if (!blob.size) return;
      const requestId = beginTurnRequest();
      setLoading(true);
      setVoiceUploadBusy(true);
      setError("");
      try {
        const fd = new FormData();
        const ext = blob.type.includes("webm") ? "webm" : "wav";
        fd.append("file", blob, `speech.${ext}`);
        fd.append("user_id", USER_ID);
        if (activeSessionId) fd.append("session_id", activeSessionId);
        const hint = (transcriptHint || "").trim();
        if (hint.length >= 3) fd.append("transcript_hint", hint);
        stopVoicePlayback();
        setStreamingAssistantText("");
        setVoiceSttPreview("");
        let usedStreamingTts = false;
        await apiPostVoiceStream(fd, {
          onTranscript: (t) => {
            if (!isLatestTurnRequest(requestId)) return;
            setVoiceSttPreview(t);
          },
          onToken: (t) => {
            if (!isLatestTurnRequest(requestId)) return;
            setStreamingAssistantText((prev) => prev + t);
          },
          onTtsChunk: (audioUrlRelative) => {
            if (!isLatestTurnRequest(requestId)) return;
            usedStreamingTts = true;
            queueStreamingTtsUrl(requestId, audioUrlRelative);
          },
          onDone: async (res) => {
            if (!isLatestTurnRequest(requestId)) return;
            if (res.skipped) {
              setError("");
              setVoiceSttPreview("");
              if (res.skip_reason === "no_speech") {
                if (voiceGateTimerRef.current) clearTimeout(voiceGateTimerRef.current);
                setVoiceGateHint("No speech detected. Speak a bit longer or check the mic.");
                voiceGateTimerRef.current = setTimeout(() => {
                  setVoiceGateHint("");
                  voiceGateTimerRef.current = null;
                }, 6000);
                return;
              }
              if (voiceGateTimerRef.current) clearTimeout(voiceGateTimerRef.current);
              setVoiceGateHint(
                "Silent mode is on: this clip had no wake name, so it was not sent. " +
                  "Say your wake name in the same recording, use push-to-talk, or say “resume listening.”",
              );
              voiceGateTimerRef.current = setTimeout(() => {
                setVoiceGateHint("");
                voiceGateTimerRef.current = null;
              }, 10_000);
              await loadProfile().catch(() => undefined);
              return;
            }
            setVoiceGateHint("");
            setVoiceSttPreview("");
            // Keep streamed text visible until messages are refreshed.
            setStreamingAssistantText((prev) => prev || res.response || "");
            ttsFullRef.current = res.response;
            setTtsRevealText("");

            if (!usedStreamingTts && res.audio_url) {
              setTtsAudioPlaying(true);
              const base = apiBase.replace(/\/$/, "");
              const path = res.audio_url.replace(/^\//, "");
              const url = `${base}/${path}`;
              const audio = new Audio(url);
              audio.preload = "auto";
              voiceAudioRef.current = audio;

              const syncCaption = () => {
                const full = ttsFullRef.current;
                const a = voiceAudioRef.current;
                if (!full || !a) return;
                const dur = a.duration;
                if (!Number.isFinite(dur) || dur <= 0) {
                  setTtsRevealText(full);
                  return;
                }
                const n = Math.min(
                  full.length,
                  Math.max(0, Math.ceil((a.currentTime / dur) * full.length)),
                );
                setTtsRevealText(full.slice(0, n));
              };

              audio.addEventListener("timeupdate", syncCaption);
              audio.addEventListener("loadeddata", syncCaption);
              audio.addEventListener("ended", () => {
                setTtsAudioPlaying(false);
                setTtsRevealText(ttsFullRef.current);
                audio.removeEventListener("timeupdate", syncCaption);
                audio.removeEventListener("loadeddata", syncCaption);
              });
              void audio.play().catch((err) => {
                console.warn("TTS playback failed (response still saved):", err);
                setTtsAudioPlaying(false);
                setTtsRevealText(ttsFullRef.current);
              });
            } else if (!usedStreamingTts) {
              setTtsAudioPlaying(false);
              setTtsRevealText(res.response);
            }

            const sid = res.session_id;
            await loadSessions();
            if (!isLatestTurnRequest(requestId)) return;
            setActiveSessionId(sid);
            await Promise.all([
              loadMessages(sid),
              loadThinking(sid),
              loadToolActivity(sid),
              loadUsageSummary(),
              loadProfile(),
            ]);
            if (!isLatestTurnRequest(requestId)) return;
            setStreamingAssistantText("");
            setTtsRevealText("");
          },
          onError: (msg) => {
            if (!isLatestTurnRequest(requestId)) return;
            stopVoicePlayback();
            setError(msg);
            setStreamingAssistantText("");
            setVoiceSttPreview("");
          },
        });
      } catch (err) {
        if (!isLatestTurnRequest(requestId)) return;
        setError(String(err));
        setVoiceSttPreview("");
      } finally {
        if (isLatestTurnRequest(requestId)) {
          setLoading(false);
          setVoiceUploadBusy(false);
        }
      }
    },
    [
      activeSessionId,
      beginTurnRequest,
      isLatestTurnRequest,
      loadSessions,
      loadMessages,
      loadThinking,
      loadToolActivity,
      loadUsageSummary,
      stopVoicePlayback,
      loadProfile,
      queueStreamingTtsUrl,
    ],
  );

  const submitFeedback = useCallback(async (messageId: string, value: MessageFeedbackValue) => {
    try {
      await apiPost<{ message_id: string; value: string }>(`/messages/${messageId}/feedback`, { value });
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const saveProfile = useCallback(async (next: Profile) => {
    const data = await apiPut<ProfileResponse>(`/profile?user_id=${USER_ID}`, next);
    setProfile(data.profile);
  }, []);

  const activeSession = useMemo(
    () => sessions.find((s) => s.session_id === activeSessionId),
    [sessions, activeSessionId],
  );

  const activeSessionTitle = activeSession?.title || "Active Session";

  const lastAssistantText = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === "assistant") return messages[i].content;
    }
    return "";
  }, [messages]);

  const userInitial = useMemo(() => {
    const n = profile?.name?.trim();
    if (n && n.length) return n[0]!.toUpperCase();
    return "U";
  }, [profile?.name]);

  const totalMessageCount = usageSummary?.assistant_messages ?? 0;
  const totalTokens = usageSummary?.total_tokens ?? 0;

  const allSystemsOk = systemStatus != null;

  return {
    sessions,
    activeSessionId,
    setActiveSessionId,
    messages,
    input,
    setInput,
    metrics,
    thinking,
    activities,
    profile,
    voiceStatus,
    systemStatus,
    usageSummary,
    fileEntriesCount,
    totalMessageCount,
    totalTokens,
    loading,
    error,
    sendMessage,
    activeSessionTitle,
    lastAssistantText,
    streamingAssistantText,
    ttsRevealText,
    userInitial,
    submitFeedback,
    saveProfile,
    allSystemsOk,
    sendVoiceBlob,
    stopVoicePlayback,
    loadProfile,
    voiceGateHint,
    voiceSttPreview,
    voiceUploadBusy,
    ttsAudioPlaying,
  };
}
