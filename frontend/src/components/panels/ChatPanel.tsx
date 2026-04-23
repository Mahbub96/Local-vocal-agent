import type { FormEvent } from "react";
import { useCallback, useState } from "react";
import { Card } from "../common/Card";
import { formatMessageTime, formatSessionDayLabel } from "../../utils/time";
import type { Message, MessageFeedbackValue } from "../../types/ui";

type ChatPanelProps = {
  title: string;
  sessionDayTime: string | null;
  messages: Message[];
  input: string;
  loading: boolean;
  onInputChange: (value: string) => void;
  onSubmit: () => Promise<void>;
  onFeedback: (messageId: string, value: MessageFeedbackValue) => Promise<void>;
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
}: ChatPanelProps) {
  const dayLabel = formatSessionDayLabel(sessionDayTime);
  const [localFeedback, setLocalFeedback] = useState<Record<string, MessageFeedbackValue>>({});

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await onSubmit();
  };

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

  return (
    <Card className="chat-card">
      <p className="chat-session-line muted">Session — {title}</p>
      <div className="chat-day-center">
        <span className="chat-day-pill" title="Current thread day">
          {dayLabel}
          <span className="chat-day-pill__chev" aria-hidden>▾</span>
        </span>
      </div>
      <div className="chat-list">
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          const t = formatMessageTime(msg.created_at);
          const selected = !isUser ? localFeedback[msg.id] : undefined;
          return (
            <div
              className={`bubble-wrap ${isUser ? "bubble-wrap--user" : "bubble-wrap--asst"}`}
              key={msg.id}
            >
              <div className="bubble-avatar" aria-hidden>
                {isUser ? "Y" : "A"}
              </div>
              <div className={`bubble ${isUser ? "user" : "assistant"}`}>
                <div className="bubble-head">
                  <b>{isUser ? "You" : "Aurora"}</b>
                  {t ? (
                    <time dateTime={msg.created_at ?? undefined} className="bubble-time">
                      {t}
                    </time>
                  ) : null}
                </div>
                <p className="bubble-body">{msg.content}</p>
                {!isUser ? (
                  <div className="bubble-actions" role="group" aria-label="Message actions">
                    <button
                      type="button"
                      className="bubble-action"
                      title="Read aloud (TTS from server when enabled)"
                      aria-label="Speak"
                      disabled
                    >
                      🔈
                    </button>
                    <button
                      type="button"
                      className="bubble-action"
                      onClick={() => void copy(msg.content)}
                      title="Copy"
                      aria-label="Copy"
                    >
                      ⎘
                    </button>
                    <button
                      type="button"
                      className={`bubble-action${selected === "like" ? " is-active" : ""}`}
                      onClick={() => void feedback(msg.id, selected === "like" ? "none" : "like")}
                      title="Thumbs up"
                      aria-pressed={selected === "like"}
                      aria-label="Thumbs up"
                    >
                      👍
                    </button>
                    <button
                      type="button"
                      className={`bubble-action${selected === "dislike" ? " is-active" : ""}`}
                      onClick={() =>
                        void feedback(msg.id, selected === "dislike" ? "none" : "dislike")
                      }
                      title="Thumbs down"
                      aria-pressed={selected === "dislike"}
                      aria-label="Thumbs down"
                    >
                      👎
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          );
        })}
        {messages.length === 0 ? (
          <div className="bubble-wrap bubble-wrap--asst">
            <div className="bubble-avatar" aria-hidden>
              A
            </div>
            <div className="bubble assistant">
              <div className="bubble-head">
                <b>Aurora</b>
              </div>
              <p className="bubble-body">Send a message to start. Your session is connected to the local model.</p>
            </div>
          </div>
        ) : null}
      </div>
      <form className="composer" onSubmit={handleSubmit}>
        <div className="composer-tools">
          <span title="Attachments (use Files API from tools)" aria-label="Attachment" role="img">
            📎
          </span>
          <span title="Search uses the assistant when needed" aria-label="Web" role="img">
            🌐
          </span>
        </div>
        <textarea
          className="composer-textarea"
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          placeholder="Type a message or press and hold the mic…"
          rows={2}
          autoComplete="off"
        />
        <button type="button" className="composer-mic" disabled aria-label="Push to talk" title="Connect voice pipeline">
          🎤
        </button>
        <button
          type="submit"
          className="composer-send"
          disabled={loading}
          title="Send"
          aria-label="Send message"
        >
          {loading ? "…" : "➤"}
        </button>
      </form>
    </Card>
  );
}
