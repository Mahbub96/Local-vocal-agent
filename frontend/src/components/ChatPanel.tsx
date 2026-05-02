import type { FormEvent, KeyboardEvent, UIEvent } from "react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  Copy,
  Globe,
  Mic,
  Paperclip,
  Send,
  ThumbsDown,
  ThumbsUp,
  Volume2,
} from "lucide-react";
import { formatMessageTime, formatSessionDayLabel } from "../utils/time";
import type { Message, MessageFeedbackValue } from "../types/ui";
import type { VoiceCaptureMode } from "../hooks/useVoiceCapture";

type ChatPanelProps = {
  title: string;
  sessionDayTime: string | null;
  messages: Message[];
  input: string;
  loading: boolean;
  onInputChange: (value: string) => void;
  onSubmit: () => Promise<void>;
  onFeedback: (messageId: string, value: MessageFeedbackValue) => Promise<void>;
  /** In-progress assistant reply from SSE stream. */
  streamingAssistantText?: string;
  voiceCaptureMode?: VoiceCaptureMode;
  /** Mic hot in push mode (recording) or always-listen mode. */
  isVoiceHot?: boolean;
  /** Same as voice card primary mic (push toggle or end hands-free). */
  onVoicePrimary?: () => void;
};

export function ChatPanel({
  title,
  sessionDayTime,
  messages,
  input,
  loading,
  onInputChange,
  onSubmit,
  onFeedback,
  streamingAssistantText = "",
  voiceCaptureMode = "push",
  isVoiceHot = false,
  onVoicePrimary,
}: ChatPanelProps) {
  const dayLabel = formatSessionDayLabel(sessionDayTime);
  const [localFeedback, setLocalFeedback] = useState<
    Record<string, MessageFeedbackValue>
  >({});
  const chatListRef = useRef<HTMLDivElement | null>(null);
  const shouldStickToBottomRef = useRef(true);
  const userGradId = useId().replace(/:/g, "");

  const sendMessage = useCallback(async () => {
    if (loading) return;
    await onSubmit();
  }, [loading, onSubmit]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await sendMessage();
  };

  const handleComposerKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key !== "Enter" || e.nativeEvent.isComposing) return;
      if (e.shiftKey) return;
      e.preventDefault();
      if (!input.trim() || loading) return;
      void sendMessage();
    },
    [input, loading, sendMessage],
  );

  const copy = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* non-secure context */
    }
  }, []);

  const feedback = useCallback(
    async (messageId: string, value: MessageFeedbackValue) => {
      setLocalFeedback((prev) => ({ ...prev, [messageId]: value }));
      await onFeedback(messageId, value);
    },
    [onFeedback],
  );

  const handleChatListScroll = useCallback((event: UIEvent<HTMLDivElement>) => {
    const el = event.currentTarget;
    const distanceFromBottom =
      el.scrollHeight - (el.scrollTop + el.clientHeight);
    shouldStickToBottomRef.current = distanceFromBottom < 56;
  }, []);

  useEffect(() => {
    const list = chatListRef.current;
    if (!list) return;
    if (shouldStickToBottomRef.current) {
      list.scrollTop = list.scrollHeight;
    }
  }, [messages, loading, streamingAssistantText]);

  return (
    <section
      className="aurora-glass flex min-h-0 flex-1 flex-col overflow-hidden rounded-3xl border border-aurora-border"
      aria-label="Chat"
    >
      <span className="sr-only">Session: {title}</span>

      <div className="flex shrink-0 justify-center border-b border-aurora-divider py-3">
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-full border border-aurora-border bg-white/4 px-4 py-1.5 text-xs font-medium text-white/75 shadow-[0_0_20px_rgba(59,130,246,0.08)] transition hover:border-white/20 hover:bg-white/7"
          title={title || "Session"}
        >
          {dayLabel}
          <span className="text-white/45" aria-hidden>
            ▾
          </span>
        </button>
      </div>

      <div
        ref={chatListRef}
        onScroll={handleChatListScroll}
        className="min-h-0 flex-1 space-y-4 overflow-y-auto overflow-x-hidden px-3 py-3 sm:space-y-5 sm:px-4 sm:py-4 md:px-5"
      >
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          const t = formatMessageTime(msg.created_at);
          const selected = !isUser ? localFeedback[msg.id] : undefined;
          return (
            <div
              key={msg.id}
              className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}
            >
              {isUser ? (
                <div
                  className="mt-0.5 grid size-10 shrink-0 place-items-center rounded-2xl bg-linear-to-br from-purple-500/35 to-indigo-600/40 ring-1 ring-purple-400/30"
                  aria-hidden
                >
                  <svg
                    className="size-5 text-white/90"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    aria-hidden
                  >
                    <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                  </svg>
                </div>
              ) : (
                <div
                  className="mt-0.5 grid size-10 shrink-0 place-items-center rounded-2xl bg-slate-950/80 ring-1 ring-cyan-400/35"
                  aria-hidden
                >
                  <svg className="size-7" viewBox="0 0 24 24" aria-hidden>
                    <defs>
                      <linearGradient
                        id={`asst-${userGradId}`}
                        x1="0%"
                        y1="0%"
                        x2="100%"
                        y2="100%"
                      >
                        <stop offset="0%" stopColor="#00d2ff" />
                        <stop offset="100%" stopColor="#9d50bb" />
                      </linearGradient>
                    </defs>
                    <circle
                      cx="12"
                      cy="12"
                      r="9"
                      fill="none"
                      stroke={`url(#asst-${userGradId})`}
                      strokeWidth="2"
                    />
                    <circle
                      cx="12"
                      cy="12"
                      r="4.4"
                      fill="none"
                      stroke={`url(#asst-${userGradId})`}
                      strokeWidth="1.2"
                      opacity="0.5"
                    />
                  </svg>
                </div>
              )}
              <div
                className={`min-w-0 flex-1 rounded-2xl border px-4 py-3 ${
                  isUser
                    ? "border-purple-500/25 bg-purple-500/8 shadow-[0_0_24px_rgba(168,85,247,0.12)]"
                    : "border-aurora-border bg-white/4"
                }`}
              >
                <div className="mb-1.5 flex flex-wrap items-baseline gap-2">
                  <span
                    className={`text-sm font-semibold ${isUser ? "text-purple-200" : "text-cyan-200/90"}`}
                  >
                    {isUser ? "You" : "Aurora"}
                  </span>
                  {t ? (
                    <time
                      dateTime={msg.created_at ?? undefined}
                      className="text-[11px] text-white/40"
                    >
                      {t}
                    </time>
                  ) : null}
                </div>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-white/88">
                  {msg.content}
                </p>
                {!isUser ? (
                  <div
                    className="mt-3 flex flex-wrap gap-1 border-t border-aurora-divider pt-2"
                    role="group"
                    aria-label="Message actions"
                  >
                    <button
                      type="button"
                      className="rounded-lg p-2 text-white/45 transition hover:bg-white/6 hover:text-white disabled:opacity-40"
                      title="Read aloud (TTS when enabled)"
                      aria-label="Speak"
                      disabled
                    >
                      <Volume2 className="size-4" strokeWidth={1.75} />
                    </button>
                    <button
                      type="button"
                      className="rounded-lg p-2 text-white/45 transition hover:bg-white/6 hover:text-white"
                      onClick={() => void copy(msg.content)}
                      title="Copy"
                      aria-label="Copy"
                    >
                      <Copy className="size-4" strokeWidth={1.75} />
                    </button>
                    <button
                      type="button"
                      className={`rounded-lg p-2 transition hover:bg-white/6 ${selected === "like" ? "text-emerald-300" : "text-white/45 hover:text-white"}`}
                      onClick={() =>
                        void feedback(
                          msg.id,
                          selected === "like" ? "none" : "like",
                        )
                      }
                      title="Thumbs up"
                      aria-pressed={selected === "like"}
                      aria-label="Thumbs up"
                    >
                      <ThumbsUp className="size-4" strokeWidth={1.75} />
                    </button>
                    <button
                      type="button"
                      className={`rounded-lg p-2 transition hover:bg-white/6 ${selected === "dislike" ? "text-rose-300" : "text-white/45 hover:text-white"}`}
                      onClick={() =>
                        void feedback(
                          msg.id,
                          selected === "dislike" ? "none" : "dislike",
                        )
                      }
                      title="Thumbs down"
                      aria-pressed={selected === "dislike"}
                      aria-label="Thumbs down"
                    >
                      <ThumbsDown className="size-4" strokeWidth={1.75} />
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          );
        })}
        {streamingAssistantText ? (
          <div className="flex gap-3" aria-live="polite" aria-busy="true">
            <div
              className="mt-0.5 grid size-10 shrink-0 place-items-center rounded-2xl bg-slate-950/80 ring-1 ring-cyan-400/35"
              aria-hidden
            >
              <span className="text-xs font-bold text-cyan-300">A</span>
            </div>
            <div className="min-w-0 flex-1 rounded-2xl border border-aurora-border bg-white/4 px-4 py-3">
              <div className="mb-1.5 flex flex-wrap items-baseline gap-2">
                <span className="text-sm font-semibold text-cyan-200/90">
                  Aurora
                </span>
                <span className="text-[11px] text-cyan-400/70">typing…</span>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-white/88">
                {streamingAssistantText}
                <span
                  className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-cyan-400/90 align-text-bottom"
                  aria-hidden
                />
              </p>
            </div>
          </div>
        ) : null}
        {messages.length === 0 && !streamingAssistantText ? (
          <div className="flex gap-3">
            <div
              className="mt-0.5 grid size-10 shrink-0 place-items-center rounded-2xl bg-slate-950/80 ring-1 ring-cyan-400/35"
              aria-hidden
            >
              <span className="text-xs font-bold text-cyan-300">A</span>
            </div>
            <div className="min-w-0 flex-1 rounded-2xl border border-aurora-border bg-white/4 px-4 py-3">
              <p className="text-sm font-semibold text-cyan-200/90">Aurora</p>
              <p className="mt-1 text-sm text-white/65">
                Send a message to start. Your session is connected to the local
                model.
              </p>
            </div>
          </div>
        ) : null}
      </div>

      <form
        onSubmit={handleSubmit}
        className="shrink-0 border-t border-aurora-border bg-black/20 p-3 md:p-4"
      >
        <div className="flex items-end gap-2 rounded-2xl border border-aurora-border bg-[#0a0d14]/90 px-2 py-2 shadow-inner md:gap-3 md:px-3">
          <div className="flex shrink-0 gap-0.5 pb-1.5 text-white/45">
            <button
              type="button"
              className="grid place-items-center rounded-lg p-2 transition hover:bg-white/6 hover:text-white"
              title="Attachments"
              aria-label="Attachment"
            >
              <Paperclip className="size-[18px]" strokeWidth={1.75} />
            </button>
            <button
              type="button"
              className="grid place-items-center rounded-lg p-2 transition hover:bg-white/6 hover:text-white"
              title="Web search"
              aria-label="Web search"
            >
              <Globe className="size-[18px]" strokeWidth={1.75} />
            </button>
          </div>
          <textarea
            className="min-h-[44px] flex-1 resize-none bg-transparent py-2.5 text-sm text-white/90 outline-none placeholder:text-white/35"
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder={
              voiceCaptureMode === "always"
                ? "Type a message — voice sends automatically after you pause…"
                : "Type a message or press and hold the mic…"
            }
            rows={2}
            autoComplete="off"
          />
          <button
            type="button"
            className={`mb-0.5 grid size-12 shrink-0 place-items-center rounded-full border text-white transition hover:brightness-110 disabled:opacity-40 ${
              isVoiceHot
                ? "border-aurora-purple/70 bg-linear-to-br from-aurora-purple/45 to-indigo-700/50 shadow-[0_0_40px_rgba(157,80,187,0.65)] ring-2 ring-aurora-purple/45"
                : "border-aurora-purple/45 bg-linear-to-br from-aurora-purple/35 to-indigo-900/45 shadow-[0_0_32px_rgba(157,80,187,0.45)]"
            }`}
            disabled={
              (voiceCaptureMode === "push" && loading) || !onVoicePrimary
            }
            aria-label={
              voiceCaptureMode === "always"
                ? "Stop hands-free listening"
                : isVoiceHot
                  ? "Stop recording and send"
                  : "Start voice recording"
            }
            aria-pressed={isVoiceHot || voiceCaptureMode === "always"}
            title={
              voiceCaptureMode === "always"
                ? "Stop hands-free listening"
                : isVoiceHot
                  ? "Tap to send recording"
                  : "Tap to speak"
            }
            onClick={() => onVoicePrimary?.()}
          >
            <Mic className="size-5" strokeWidth={1.75} />
          </button>
          <button
            type="submit"
            className="mb-0.5 grid size-11 shrink-0 place-items-center rounded-xl bg-linear-to-br from-aurora-cyan to-indigo-600 text-aurora-canvas shadow-[0_0_28px_rgba(0,210,255,0.45)] transition hover:brightness-110 disabled:opacity-50"
            disabled={loading}
            title="Send"
            aria-label="Send message"
          >
            {loading ? (
              <span className="text-lg">…</span>
            ) : (
              <Send className="size-5" strokeWidth={1.75} />
            )}
          </button>
        </div>
      </form>
    </section>
  );
}
