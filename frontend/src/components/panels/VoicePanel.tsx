import { useMemo } from "react";
import { Card } from "../common/Card";
import type { VoiceStatus } from "../../types/ui";

type VoicePanelProps = {
  voiceStatus: VoiceStatus | null;
  languageLabel: string;
  lastAssistantSnippet: string;
};

function titleFromState(state: string | undefined): string {
  const s = state?.toLowerCase() ?? "idle";
  if (s === "listening") return "Listening…";
  if (s === "transcribing") return "Transcribing…";
  if (s === "speaking") return "Speaking…";
  if (s === "idle" || s === "ready") return "Ready";
  return state ? state.charAt(0).toUpperCase() + state.slice(1) : "Ready";
}

function shortStateLabel(state: string | undefined): string {
  const s = state?.toLowerCase() ?? "idle";
  if (s === "idle") return "Idle";
  if (s === "ready") return "Ready";
  if (s === "listening") return "Listening";
  if (s === "transcribing") return "Transcribing";
  if (s === "speaking") return "Speaking";
  return state ? state.charAt(0).toUpperCase() + state.slice(1) : "Idle";
}

function useBars(count: number, level: number, seed: number) {
  return useMemo(() => {
    return Array.from({ length: count }, (_, i) => {
      const h = 4 + ((i * 6 + seed * 3 + Math.round(level / 6)) % 22);
      const on = i < Math.max(0, Math.round((level / 100) * count) - 0.01);
      return { h, on };
    });
  }, [count, level, seed]);
}

function IconMic() {
  return (
    <svg className="voice-ic" viewBox="0 0 24 24" width="20" height="20" aria-hidden>
      <path
        fill="currentColor"
        d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.49 6-3.31 6-6.72h-1.7z"
      />
    </svg>
  );
}

function IconStop() {
  return (
    <svg className="voice-ic voice-ic--stop" viewBox="0 0 24 24" width="22" height="22" aria-hidden>
      <rect x="5" y="5" width="14" height="14" rx="1.2" fill="currentColor" />
    </svg>
  );
}

function IconGear() {
  return (
    <svg className="voice-ic" viewBox="0 0 24 24" width="20" height="20" aria-hidden>
      <path
        fill="currentColor"
        d="M19.43 12.98c.04-.32.07-.64.07-.98s-.03-.66-.07-1l2.11-1.65c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.3-.61-.22l-2.49 1c-.52-.4-1.08-.73-1.69-.98l-.38-2.65A.488.488 0 0014 2h-4c-.25 0-.46.18-.49.42l-.38 2.65c-.61.25-1.17.59-1.69.98l-2.49-1c-.23-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64L4.57 11c-.04.34-.07.67-.07.98s.03.66.07.98l-2.11 1.65c-.19.15-.24.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1c.52.4 1.08.73 1.69.98l.38 2.65c.03.24.24.42.49.42h4c.25 0 .46-.18.49-.42l.38-2.65c.61-.25 1.17-.59 1.69-.98l2.49 1c.23.09.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.65zM12 15.5A3.5 3.5 0 1112 8a3.5 3.5 0 010 7.5z"
      />
    </svg>
  );
}

export function VoicePanel({ voiceStatus, languageLabel, lastAssistantSnippet }: VoicePanelProps) {
  const st = voiceStatus?.state;
  const s = st?.toLowerCase() ?? "idle";
  const level = Math.max(0, Math.min(100, voiceStatus?.audio_level ?? 0));

  const bars6a = useBars(6, level, 1);
  const bars6b = useBars(6, level, 2);
  const bars10 = useBars(10, level, 3);
  const barsSpec1 = useBars(6, level, 4);
  const barsSpec2 = useBars(6, level, 5);

  const listenAnim = s === "listening" || s === "transcribing" || s === "speaking";

  const hint = useMemo(() => {
    if (voiceStatus?.detail && s !== "idle" && s !== "ready") return voiceStatus.detail;
    if (s === "idle" || s === "ready") return "How can I help you?";
    return "Processing…";
  }, [voiceStatus?.detail, s]);

  const outLine = useMemo(() => {
    if (s === "speaking" && lastAssistantSnippet.trim()) {
      const t = lastAssistantSnippet.trim();
      return t.length > 200 ? `${t.slice(0, 197)}…` : t;
    }
    if (s === "speaking" && !lastAssistantSnippet.trim()) return "Speaking…";
    return shortStateLabel(st);
  }, [s, lastAssistantSnippet, st]);

  const showSpeakingKicker = s === "speaking" && Boolean(lastAssistantSnippet.trim());

  return (
    <Card className="voice-card">
      <div className="voice-body">
        <div className="voice-main">
          <div className="voice-top">
            <div className="voice-listen">
              <span
                className={`listen-dot${listenAnim ? " listen-dot--active" : ""}`}
                aria-hidden
              />
              <h2 className="voice-listen__tx">{titleFromState(st)}</h2>
            </div>
            <p className="voice-hint">{hint}</p>
          </div>

          <div className="voice-stage">
            <div className="voice-orbit-row">
              <div className="voice-wf-side">
                {bars6a.map((b, i) => (
                  <i key={i} className={b.on ? "on" : ""} style={{ height: b.h }} />
                ))}
              </div>
              <div className="voice-orbit-center">
                <div className="wave-line" />
                <div className="wave-ring">
                  <div className="inner-ring" />
                </div>
              </div>
              <div className="voice-wf-side">
                {bars6b.map((b, i) => (
                  <i key={i} className={b.on ? "on" : ""} style={{ height: b.h }} />
                ))}
              </div>
            </div>
            <p className="voice-lang-pill" title="Preferred languages (profile)">
              {languageLabel}
            </p>
            <div className="voice-ctrl voice-ctrl--three" role="group" aria-label="Voice controls">
              <button type="button" className="voice-icbtn voice-mic" title="Microphone" aria-label="Microphone">
                <IconMic />
              </button>
              <button type="button" className="voice-stop" title="Stop" aria-label="Stop">
                <IconStop />
              </button>
              <button
                type="button"
                className="voice-icbtn voice-gear"
                title="Voice / filter"
                aria-label="Settings"
              >
                <IconGear />
              </button>
            </div>
          </div>

          <div className="voice-spectrum" aria-hidden>
            <div className="audio-bars audio-bars--cluster">
              {barsSpec1.map((b, i) => (
                <i key={i} className={b.on ? "on" : ""} style={{ height: b.h }} />
              ))}
            </div>
            <div className="audio-bars audio-bars--cluster">
              {barsSpec2.map((b, i) => (
                <i key={i} className={b.on ? "on" : ""} style={{ height: b.h }} />
              ))}
            </div>
            <div className="voice-audio-level">
              <p className="voice-audio-level__label">Audio Level</p>
              <div className="audio-bars audio-bars--wide" role="img" aria-label="Audio level">
                {bars10.map((b, i) => (
                  <i key={i} className={b.on ? "on" : ""} style={{ height: b.h }} />
                ))}
              </div>
            </div>
          </div>
        </div>

        <aside className="voice-out" aria-label="Voice output">
          <p className="voice-out__label">
            <span className="voice-out__status-dot" aria-hidden />
            Voice Output
          </p>
          {showSpeakingKicker ? <p className="voice-out__kicker">Speaking…</p> : null}
          <p className="voice-out__primary">{outLine}</p>
        </aside>
      </div>
    </Card>
  );
}
