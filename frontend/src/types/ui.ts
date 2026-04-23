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
  entries: { name: string; path: string; is_dir: boolean }[];
};
