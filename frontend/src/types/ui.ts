export type Session = {
  session_id: string;
  title: string | null;
  user_id?: string | null;
  message_count?: number;
  last_message_at?: string | null;
  created_at?: string | null;
};

export type Message = {
  id: string;
  role: string;
  content: string;
  created_at?: string | null;
  token_count?: number | null;
};

export type ChatResponse = {
  session_id: string;
  user_message_id: string;
  assistant_message_id: string;
  response: string;
  used_memory: boolean;
  used_internet: boolean;
  audio_path?: string | null;
};

/** `POST /voice-chat` JSON — play TTS via `GET {apiBase}/{audio_url}`. */
export type VoiceChatResponse = {
  session_id: string;
  transcript: string;
  response: string;
  used_memory: boolean;
  used_internet: boolean;
  audio_path?: string | null;
  audio_url?: string | null;
  /** Voice ignored (wake gate); no new chat messages. */
  skipped?: boolean;
  /** wake_gate | no_speech */
  skip_reason?: string | null;
  voice_listen_paused?: boolean | null;
  voice_wake_session_active?: boolean | null;
};

export type Metrics = {
  cpu_percent: number;
  memory_percent: number;
  gpu_percent: number | null;
  npu_percent: number | null;
};

export type SystemStatus = {
  app_name: string;
  app_env: string;
  uptime_seconds: number;
  model_name?: string | null;
  load_avg_1m: number | null;
  load_avg_5m: number | null;
  load_avg_15m: number | null;
  sqlite_path: string;
  chroma_path: string;
};

export type ThinkingStep = {
  key: string;
  label: string;
  status: string;
  detail?: string | null;
};

export type ThinkingProcess = {
  session_id: string;
  steps: ThinkingStep[];
};

export type ToolActivity = {
  session_id: string;
  message_id: string;
  tool_name: string;
  created_at: string | null;
  role: string;
};

export type ToolActivityListResponse = {
  activities: ToolActivity[];
};

export type Profile = {
  name: string | null;
  language: string | null;
  location: string | null;
  profession: string | null;
  project: string | null;
  preferences: string[];
  /** Per-user TTS tempo (e.g. 1.2). Omitted = server default. */
  tts_playback_speed?: number | null;
  /** Say this name in voice when silent mode is on. */
  assistant_wake_name?: string | null;
  /** When true, voice is ignored unless the transcript includes the wake name (text chat always works). */
  voice_listen_paused?: boolean;
  /** After wake in quiet mode: follow-up voice works without wake until stop / keep quiet. */
  voice_wake_session_active?: boolean;
};

export type ProfileResponse = {
  user_id: string;
  profile: Profile;
};

export type UsageSummary = {
  user_id: string;
  total_messages: number;
  assistant_messages: number;
  total_tokens: number;
};

export type VoiceStatus = {
  state: string;
  audio_level: number;
  detail: string | null;
  updated_at: number;
};

export type MessageFeedbackValue = "like" | "dislike" | "none";

export type MessageFeedbackResponse = {
  message_id: string;
  value: MessageFeedbackValue;
};

export type FileListResponse = {
  root: string;
  current_path: string;
  entries: {
    name: string;
    path: string;
    is_dir: boolean;
    size?: number | null;
    modified_at?: string | null;
  }[];
};

export type FileContentResponse = {
  path: string;
  content: string;
};

export type MemorySearchMatch = {
  message_id: string;
  session_id: string;
  role: string;
  content: string;
  score: number;
  created_at?: string | null;
};

export type MemorySearchResponse = {
  matches: MemorySearchMatch[];
};

export type FileSearchMatch = {
  path: string;
  line_number: number;
  line: string;
};

export type FileSearchResponse = {
  query: string;
  matches: FileSearchMatch[];
};
