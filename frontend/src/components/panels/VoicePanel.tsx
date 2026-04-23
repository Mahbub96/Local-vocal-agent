import { useId, useMemo } from "react";
import { Card } from "../common/Card";
import type { VoiceStatus } from "../../types/ui";

const VOICE_LANG_OPTIONS = ["বাংলা (Bangla)", "English", "Default"] as const;

type VoicePanelProps = {
  voiceStatus: VoiceStatus | null;
  languageLabel: string;
  lastAssistantSnippet: string;
  onLanguageChange?: (language: string) => void;
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
    const lv = level / 100;
    return Array.from({ length: count }, (_, i) => {
      const wave = Math.sin((i * 0.9 + seed * 1.7) * 0.85) * 0.5 + 0.5;
      const h = 5 + Math.round(8 + wave * 20 * (0.35 + lv * 0.75));
      const on = i < Math.max(0, Math.round(lv * count) - 0.01);
      return { h, on };
    });
  }, [count, level, seed]);
}

function useLanguageOptions(current: string) {
  return useMemo(() => {
    const c = (current || "Default").trim() || "Default";
    const rest = VOICE_LANG_OPTIONS.filter((x) => x !== c);
    return [c, ...rest];
  }, [current]);
}

function IconMic() {
  return (
    <svg
      className="voice-ic"
      viewBox="0 0 24 24"
      width="20"
      height="20"
      aria-hidden
    >
      <path
        fill="currentColor"
        d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.49 6-3.31 6-6.72h-1.7z"
      />
    </svg>
  );
}

function IconStop() {
  return (
    <svg
      className="voice-ic voice-ic--stop"
      viewBox="0 0 24 24"
      width="22"
      height="22"
      aria-hidden
    >
      <rect x="5" y="5" width="14" height="14" rx="1.2" fill="currentColor" />
    </svg>
  );
}

function IconFilterSliders() {
  return (
    <svg
      className="voice-ic"
      viewBox="0 0 24 24"
      width="20"
      height="20"
      aria-hidden
    >
      <rect x="4" y="4" width="3" height="16" rx="1" fill="currentColor" />
      <rect x="10.5" y="8" width="3" height="12" rx="1" fill="currentColor" />
      <rect x="17" y="2" width="3" height="18" rx="1" fill="currentColor" />
    </svg>
  );
}

function IconGlobe() {
  return (
    <svg
      className="voice-lang-globe"
      viewBox="0 0 24 24"
      width="16"
      height="16"
      aria-hidden
    >
      <path
        fill="currentColor"
        d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 1.65-.41 3.18-1.11 4.49z"
      />
    </svg>
  );
}

export function VoicePanel({
  voiceStatus,
  languageLabel,
  lastAssistantSnippet,
  onLanguageChange,
}: VoicePanelProps) {
  const st = voiceStatus?.state;
  const s = st?.toLowerCase() ?? "idle";
  const level = Math.max(0, Math.min(100, voiceStatus?.audio_level ?? 0));
  const langId = useId();
  const langOptions = useLanguageOptions(languageLabel);

  const bars6a = useBars(8, level, 1);
  const bars6b = useBars(8, level, 2);
  const barsOut = useBars(16, s === "speaking" ? level + 15 : level, 3);

  const listenAnim =
    s === "listening" || s === "transcribing" || s === "speaking";

  const hint = useMemo(() => {
    if (voiceStatus?.detail && s !== "idle" && s !== "ready")
      return voiceStatus.detail;
    if (s === "listening") return "I'm listening. How can I help you?";
    if (s === "idle" || s === "ready") return "How can I help you?";
    return "Processing…";
  }, [voiceStatus?.detail, s]);

  const outLine = useMemo(() => {
    if (s === "speaking" && lastAssistantSnippet.trim()) {
      const t = lastAssistantSnippet.trim();
      return t.length > 200 ? `${t.slice(0, 197)}…` : t;
    }
    if (s === "speaking" && !lastAssistantSnippet.trim()) return "…";
    return shortStateLabel(st);
  }, [s, lastAssistantSnippet, st]);

  const isSpeaking = s === "speaking";

  return (
    <Card className="voice-card">
      <div className="voice-surface">
        <div className="voice-hero" role="group" aria-label="Voice interface">
          <div className="voice-col voice-col--status">
            <div className="voice-top">
              <div className="voice-listen">
                <span
                  className={`listen-dot${listenAnim ? " listen-dot--active" : ""}`}
                  aria-hidden
                />
                <h2 className="voice-listen__tx" id="voice-listen-title">
                  {titleFromState(st)}
                </h2>
              </div>
              <p className="voice-hint" aria-describedby="voice-listen-title">
                {hint}
              </p>
            </div>
          </div>

          <div className="voice-col voice-col--stage">
            <div className="voice-orbit-row">
              <div className="voice-orbit-row__line" aria-hidden />
              <div className="voice-wf-side voice-wf-side--in">
                {bars6a.map((b, i) => (
                  <i
                    key={i}
                    className={b.on ? "on" : ""}
                    style={{ height: b.h }}
                  />
                ))}
              </div>
              <div className="voice-orbit-mid">
                <div className="wave-ring">
                  <div className="inner-ring" />
                </div>
              </div>
              <div className="voice-wf-side voice-wf-side--out">
                {bars6b.map((b, i) => (
                  <i
                    key={i}
                    className={b.on ? "on" : ""}
                    style={{ height: b.h }}
                  />
                ))}
              </div>
            </div>
          </div>

          <aside className="voice-col voice-col--out" aria-label="Voice output">
            <div className="voice-out-inner">
              <div className="voice-out__text">
                <div className="voice-out__head">
                  <p className="voice-out__label">
                    <span className="voice-out__status-dot" aria-hidden />
                    <span>Voice Output</span>
                  </p>
                  {isSpeaking ? (
                    <span className="voice-out__state-pill">Speaking…</span>
                  ) : null}
                </div>
                <p className="voice-out__primary">{outLine}</p>
              </div>
              <div className="voice-out__meter-block">
                <p className="voice-out__meter-lbl">Audio Level</p>
                <div
                  className="voice-out__meter"
                  role="img"
                  aria-label="Output level"
                >
                  {barsOut.map((b, i) => (
                    <i
                      key={i}
                      className={b.on ? "on" : ""}
                      style={{ height: b.h }}
                    />
                  ))}
                </div>
              </div>
            </div>
          </aside>
        </div>

        <div className="voice-footgrid" aria-label="Language and transport">
          <div className="voice-footgrid__lang">
            <div className="voice-lang-pill">
              <span
                className="voice-lang-pill__icon"
                title="Language"
                aria-hidden
              >
                <IconGlobe />
              </span>
              <label className="visually-hidden" htmlFor={langId}>
                Response language
              </label>
              <select
                id={langId}
                className="voice-lang-select"
                value={
                  langOptions.includes(languageLabel)
                    ? languageLabel
                    : langOptions[0]!
                }
                onChange={(e) => onLanguageChange?.(e.target.value)}
                title="Preferred language"
              >
                {langOptions.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="voice-footgrid__ctrl">
            <div
              className="voice-ctrl voice-ctrl--three"
              role="group"
              aria-label="Voice controls"
            >
              <button
                type="button"
                className="voice-icbtn voice-mic"
                title="Microphone"
                aria-label="Microphone"
              >
                <IconMic />
              </button>
              <button
                type="button"
                className="voice-stop"
                title="Stop"
                aria-label="Stop"
              >
                <IconStop />
              </button>
              <button
                type="button"
                className="voice-icbtn voice-gear"
                title="Voice / filter"
                aria-label="Filter"
              >
                <IconFilterSliders />
              </button>
            </div>
          </div>
          <div className="voice-footgrid__pad" aria-hidden />
        </div>
      </div>
    </Card>
  );
}
