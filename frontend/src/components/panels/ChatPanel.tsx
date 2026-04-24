import type { FormEvent, KeyboardEvent, UIEvent } from "react";
import { useCallback, useEffect, useId, useRef, useState } from "react";
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

function UserAvatar() {
  return (
    <div className="bubble-avatar bubble-avatar--user" aria-hidden>
      <svg className="bubble-avatar__svg" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10.5" fill="var(--c-chat-avatar-user-fill)" />
        <path
          d="M12 11.2a2.6 2.6 0 1 0-2.6-2.6 2.6 2.6 0 0 0 2.6 2.6zm0 1.4c-2.2 0-4.1 1-4.1 2.7V16h8.2v-.7c0-1.7-1.9-2.7-4.1-2.7z"
          fill="var(--c-chat-avatar-user-icon)"
        />
      </svg>
    </div>
  );
}

function AssistantAvatar() {
  const id = useId();
  const gid = `chat-asst-ring-${id.replace(/[:]/g, "")}`;

  return (
    <div className="bubble-avatar bubble-avatar--asst" aria-hidden>
      <svg className="bubble-avatar__svg" viewBox="0 0 24 24">
        <defs>
          <linearGradient id={gid} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--c-voice-orbit-cyan)" />
            <stop offset="100%" stopColor="var(--c-accent-purple)" />
          </linearGradient>
        </defs>
        <circle cx="12" cy="12" r="9" fill="none" stroke={`url(#${gid})`} strokeWidth="2" />
        <circle cx="12" cy="12" r="4.4" fill="none" stroke={`url(#${gid})`} strokeWidth="1.2" opacity="0.5" />
      </svg>
    </div>
  );
}

function IconVolume() {
  return (
    <svg className="bubble-action__ic" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M3 10v4c0 .55.45 1 1 1h3l3.5 3.5c.35.35.9.1.9-.5V6c0-.6-.55-.85-.9-.5L7 9H4c-.55 0-1 .45-1 1zm13.5 2a4.5 4.5 0 0 0-1.2-3l-.9 1.26a2.5 2.5 0 0 1 .1 3.5l.9 1.24c.4-.5.6-1.1.1-1zM16.5 6a8.5 8.5 0 0 1 0 12l-.9-1.24A6.5 6.5 0 0 0 18 12a6.5 6.5 0 0 0-2.4-4.76L16.5 6z"
      />
    </svg>
  );
}

function IconCopy() {
  return (
    <svg className="bubble-action__ic" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M16 1H4c-1.1 0-2 .9-2 2v12h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"
      />
    </svg>
  );
}

function IconThumbUp() {
  return (
    <svg className="bubble-action__ic" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.3l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.82 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-1.91l-.01-.01L23 10z"
      />
    </svg>
  );
}

function IconThumbDown() {
  return (
    <svg className="bubble-action__ic" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M15 3H6c-.83 0-1.54.5-1.84 1.22L1.1 11.5c-.09.23-.14.47-.14.73V13c0 1.1.9 2 2 2h5.31l-.95 4.57-.03.32c0 .41.17.79.44 1.06L9.83 23l6.59-6.59c.36-.36.58-.86.58-1.41V5c0-1.1-.9-2-2-2zm4 0v12h4V3h-4z"
      />
    </svg>
  );
}

function IconMic() {
  return (
    <svg className="composer-mic__ic" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.49 6-3.31 6-6.72h-1.7z"
      />
    </svg>
  );
}

function IconSend() {
  return (
    <svg className="composer-send__ic" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"
      />
    </svg>
  );
}

function IconClip() {
  return (
    <svg className="composer-tool-ic" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M16.5 6.5v9.4c0 2.5-2 4.4-4.4 4.4-2.5 0-4.4-2-4.4-4.4V5.4C7.7 3.3 9.3 1.6 11.4 1.6c1.1 0 2.1.4 2.8 1.1l.1.1c.4.4.4 1 0 1.4-.4.4-1 .4-1.4 0l-.1-.1c-.4-.4-1-.7-1.5-.7-1.2 0-2.1 1-2.1 2.1v10.4c0 1.2 1 2.1 2.1 2.1 1.2 0 2.1-1 2.1-2.1V6.5c0-.6.4-1 1-1s1 .4 1 1z"
      />
    </svg>
  );
}

function IconGlobe() {
  return (
    <svg className="composer-tool-ic" viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 1.65-.41 3.18-1.11 4.49z"
      />
    </svg>
  );
}

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
  const chatListRef = useRef<HTMLDivElement | null>(null);
  const shouldStickToBottomRef = useRef(true);

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
    const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight);
    shouldStickToBottomRef.current = distanceFromBottom < 56;
  }, []);

  useEffect(() => {
    const list = chatListRef.current;
    if (!list) return;

    if (shouldStickToBottomRef.current) {
      list.scrollTop = list.scrollHeight;
    }
  }, [messages, loading]);

  return (
    <Card className="chat-card">
      <span className="visually-hidden">Session: {title}</span>
      <div className="chat-day-center">
        <span className="chat-day-pill" title={title || "Session"}>
          {dayLabel}
          <span className="chat-day-pill__chev" aria-hidden>
            ▾
          </span>
        </span>
      </div>
      <div className="chat-list" ref={chatListRef} onScroll={handleChatListScroll}>
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          const t = formatMessageTime(msg.created_at);
          const selected = !isUser ? localFeedback[msg.id] : undefined;
          return (
            <div
              className={`bubble-wrap ${isUser ? "bubble-wrap--user" : "bubble-wrap--asst"}`}
              key={msg.id}
            >
              {isUser ? <UserAvatar /> : <AssistantAvatar />}
              <div className={`bubble ${isUser ? "user" : "assistant"}`}>
                <div className="bubble-head">
                  <b
                    className={`bubble-name ${
                      isUser ? "bubble-name--user" : "bubble-name--asst"
                    }`}
                  >
                    {isUser ? "You" : "Aurora"}
                  </b>
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
                      <IconVolume />
                    </button>
                    <button
                      type="button"
                      className="bubble-action"
                      onClick={() => void copy(msg.content)}
                      title="Copy"
                      aria-label="Copy"
                    >
                      <IconCopy />
                    </button>
                    <button
                      type="button"
                      className={`bubble-action${selected === "like" ? " is-active" : ""}`}
                      onClick={() => void feedback(msg.id, selected === "like" ? "none" : "like")}
                      title="Thumbs up"
                      aria-pressed={selected === "like"}
                      aria-label="Thumbs up"
                    >
                      <IconThumbUp />
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
                      <IconThumbDown />
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          );
        })}
        {messages.length === 0 ? (
          <div className="bubble-wrap bubble-wrap--asst">
            <AssistantAvatar />
            <div className="bubble assistant">
              <div className="bubble-head">
                <b className="bubble-name bubble-name--asst">Aurora</b>
              </div>
              <p className="bubble-body">
                Send a message to start. Your session is connected to the local model.
              </p>
            </div>
          </div>
        ) : null}
      </div>
      <form className="composer" onSubmit={handleSubmit}>
        <div className="composer-row">
          <div className="composer-tools" aria-label="Quick actions">
            <span title="Attachments" aria-label="Attachment">
              <IconClip />
            </span>
            <span title="Web search" aria-label="Web search">
              <IconGlobe />
            </span>
          </div>
          <textarea
            className="composer-textarea"
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder="Type a message (Shift+Enter for a new line) or press and hold the mic…"
            rows={2}
            autoComplete="off"
          />
          <button
            type="button"
            className="composer-mic"
            disabled
            aria-label="Push to talk"
            title="Connect voice pipeline"
          >
            <IconMic />
          </button>
          <button
            type="submit"
            className="composer-send"
            disabled={loading}
            title="Send"
            aria-label="Send message"
          >
            {loading ? "…" : <IconSend />}
          </button>
        </div>
      </form>
    </Card>
  );
}
