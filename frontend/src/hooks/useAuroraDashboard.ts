/* Data loads in effects intentionally sync server state into React; see React docs on data fetching. */
/* eslint-disable react-hooks/set-state-in-effect */
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiBase, apiGet, apiPost, apiPut, USER_ID } from "../services/api";
import type {
  ChatResponse,
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
const SSE_MAX_EVENTS = 60;

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
  const [error, setError] = useState("");

  const loadSessions = useCallback(async () => {
    const data = await apiGet<{ sessions: Session[] }>(`/sessions?user_id=${USER_ID}&limit=20`);
    setSessions(data.sessions);
    setActiveSessionId((prev) => prev || data.sessions[0]?.session_id || "");
  }, []);

  const loadMessages = useCallback(async (sessionId: string) => {
    const data = await apiGet<{ messages: Message[] }>(`/sessions/${sessionId}/messages?limit=30`);
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
    const data = await apiGet<ThinkingProcess>(`/sessions/${sessionId}/thinking-process`);
    setThinking(data.steps);
  }, []);

  const loadToolActivity = useCallback(async (sessionId: string | undefined) => {
    const q = new URLSearchParams({ limit: "8" });
    if (sessionId) q.set("session_id", sessionId);
    const data = await apiGet<ToolActivityListResponse>(`/tools/activity?${q.toString()}`);
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
      `${apiBase}/voice/status-stream?interval_ms=${SSE_VOICE_MS}&max_events=${SSE_MAX_EVENTS}`,
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
      `${apiBase}/sessions/${activeSessionId}/thinking-stream?interval_ms=${SSE_THINKING_MS}&max_events=${SSE_MAX_EVENTS}`,
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
    setLoading(true);
    setError("");
    try {
      const result = await apiPost<ChatResponse>("/chat", {
        message: input.trim(),
        user_id: USER_ID,
        session_id: activeSessionId || undefined,
      });
      setInput("");
      await loadSessions();
      setActiveSessionId(result.session_id);
      await loadMessages(result.session_id);
      await loadThinking(result.session_id);
      await loadToolActivity(result.session_id);
      await loadUsageSummary();
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [input, activeSessionId, loadSessions, loadMessages, loadThinking, loadToolActivity, loadUsageSummary]);

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

  const dayLabel = useMemo(() => {
    const t = activeSession?.last_message_at || activeSession?.created_at;
    return t ?? null;
  }, [activeSession]);

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
    dayLabel,
    lastAssistantText,
    userInitial,
    submitFeedback,
    saveProfile,
    allSystemsOk,
  };
}
