import { Globe } from "lucide-react";
import { useId, useMemo } from "react";
import { cn } from "../lib/cn";
import type { VoiceCaptureMode } from "../hooks/useVoiceCapture";
import {
  BarVisualizer,
  GlowDot,
  HeroSurface,
  SelectPill,
} from "./ui";
import { VoiceOrb } from "./voice/VoiceOrb";
import { VoiceTransport } from "./voice/VoiceTransport";
import { shortVoiceStateLabel, titleFromVoiceState } from "./voice/voiceLabels";
import { useVoiceLanguageOptions } from "./voice/voiceLanguage";
import { useLevelBars } from "../hooks/useLevelBars";
import type { VoiceStatus } from "../types/ui";

type VoicePanelProps = {
  voiceStatus: VoiceStatus | null;
  languageLabel: string;
  lastAssistantSnippet: string;
  liveAssistantOutput?: string;
  onLanguageChange?: (language: string) => void;
  captureMode: VoiceCaptureMode;
  onCaptureModeChange: (mode: VoiceCaptureMode) => void;
  isListening?: boolean;
  /** Hands-free: stream is open even between VAD segments — use for meter + live caption styling. */
  voiceSessionHot?: boolean;
  voiceBusy?: boolean;
  onMicPrimary?: () => void;
  onVoiceInterrupt?: () => void;
  liveUserText?: string;
  micLevelLocal?: number;
  /** Short-lived hint when voice was skipped (e.g. silent mode without wake name). */
  gateHint?: string;
};

/** Voice card layout matches reference: header (listen | output title), waveform through orb, footer (lang | controls | output stack). */
export function VoicePanel({
  voiceStatus,
  languageLabel,
  lastAssistantSnippet,
  liveAssistantOutput = "",
  onLanguageChange,
  captureMode,
  onCaptureModeChange,
  isListening = false,
  voiceSessionHot = false,
  voiceBusy = false,
  onMicPrimary,
  onVoiceInterrupt,
  liveUserText = "",
  micLevelLocal,
  gateHint = "",
}: VoicePanelProps) {
  const st = voiceStatus?.state;
  const s = st?.toLowerCase() ?? "idle";
  const serverLevel = Math.max(0, Math.min(100, voiceStatus?.audio_level ?? 0));
  const handsFree = captureMode === "always";
  const segmentOrPushHot = isListening || (handsFree && voiceSessionHot);
  const level =
    segmentOrPushHot && micLevelLocal != null ? micLevelLocal : serverLevel;
  const langId = useId();
  const langOptions = useVoiceLanguageOptions(languageLabel);

  /** Open mic stream (hands-free) alone should not look like “always listening” — only capture + server work states. */
  const listenAnim =
    s === "listening" ||
    s === "transcribing" ||
    s === "thinking" ||
    s === "speaking" ||
    isListening;

  /** Reference UI: side waveforms stay visibly cyan / purple when idle (not washed-out gray). */
  const waveLevel = useMemo(() => {
    const active = listenAnim;
    return active ? level : Math.max(level, 44);
  }, [level, listenAnim]);

  const barsIn = useLevelBars(24, waveLevel, 1);
  const barsInMirror = useLevelBars(24, waveLevel, 2);
  const barsOut = useLevelBars(18, s === "speaking" ? level + 15 : level, 3);

  const hint = useMemo(() => {
    if (voiceStatus?.detail && s !== "idle" && s !== "ready")
      return voiceStatus.detail;
    if (s === "listening") return "I'm listening. How can I help you?";
    if (s === "idle" || s === "ready") return "How can I help you?";
    return "Processing…";
  }, [voiceStatus?.detail, s]);

  const listeningSubtitle = useMemo(() => {
    const live = liveUserText.trim();
    if (live) return live;
    return "I'm listening. How can I help you?";
  }, [liveUserText]);

  const showLiveCaptionStyle =
    Boolean(liveUserText.trim()) && !(handsFree && !isListening);

  const listenHeading = useMemo(() => {
    /** Between VAD clips, show Hands-free even if Web Speech left stale interim text. */
    if (handsFree && !isListening) return "Hands-free";
    if (liveUserText.trim()) return "Listening…";
    if (handsFree && isListening) return "Listening…";
    if (isListening) return "Listening…";
    return titleFromVoiceState(st);
  }, [handsFree, isListening, st, liveUserText]);

  const listenSub = useMemo(() => {
    if (gateHint.trim()) return gateHint;
    /** Match heading: between VAD segments, don’t let stale Web Speech text imply you’re still “in” listening. */
    if (handsFree && !isListening) {
      return "Between clips the mic rests until you speak again. Tap the mic to stop hands-free.";
    }
    if (liveUserText.trim()) return listeningSubtitle;
    if (handsFree && isListening) {
      return "Speak anytime — segments send after a short pause. Tap the mic to stop hands-free.";
    }
    if (isListening) return listeningSubtitle;
    return hint;
  }, [
    gateHint,
    handsFree,
    isListening,
    liveUserText,
    listeningSubtitle,
    hint,
  ]);

  const outLine = useMemo(() => {
    const live = liveAssistantOutput.trim();
    if (live) {
      return live.length > 240 ? `${live.slice(0, 237)}…` : live;
    }
    if (s === "speaking" && lastAssistantSnippet.trim()) {
      const t = lastAssistantSnippet.trim();
      return t.length > 240 ? `${t.slice(0, 237)}…` : t;
    }
    if (s === "speaking" && !lastAssistantSnippet.trim()) return "…";
    return shortVoiceStateLabel(st);
  }, [s, lastAssistantSnippet, st, liveAssistantOutput]);

  const outputSubheading = useMemo(() => {
    if (s === "speaking") return "Speaking";
    return "Idle";
  }, [s]);
  const outputStateLine = useMemo(() => {
    if (s === "transcribing") return "Transcribing";
    if (s === "thinking") return "Thinking";
    if (s === "listening") return "Listening";
    if (s === "speaking") return "Speaking";
    return "Ready";
  }, [s]);

  const selectValue = langOptions.includes(languageLabel)
    ? languageLabel
    : langOptions[0]!;

  return (
    <HeroSurface
      aria-label="Voice assistant"
      withRadialHighlight
      className="rounded-aurora-lg border border-white/6 bg-aurora-canvas/95 p-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.04),0_0_22px_-10px_rgba(0,209,255,0.07)] backdrop-blur-sm"
    >
      <div className="relative z-10 flex min-h-0 flex-col gap-1.5 sm:gap-2">
        {/* Row 1 — reference: listen left; Voice Output title only right (accent blue) */}
        <div className="grid grid-cols-1 gap-1 sm:grid-cols-2 sm:items-start sm:gap-3">
          <header className="min-w-0 space-y-0.5">
            <div className="flex items-center gap-2">
              <GlowDot
                className="bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.75)]"
                aria-hidden
              />
              <h2
                id="voice-title"
                className="font-sans text-[14px] font-semibold leading-tight text-white sm:text-[15px]"
              >
                {listenHeading}
              </h2>
            </div>
            <p
              className={cn(
                "max-w-120 pl-[18px] text-[13px] leading-snug text-white/45 sm:pl-5",
                showLiveCaptionStyle && "text-[13px] text-white/90 sm:text-[14px]",
                gateHint.trim() && "text-amber-100/95",
              )}
              aria-live={
                isListening || gateHint || liveUserText.trim()
                  ? "polite"
                  : undefined
              }
            >
              {listenSub}
            </p>
          </header>

          <header className="flex min-w-0 items-start justify-start sm:justify-end">
            <div className="flex items-center gap-2">
              <GlowDot
                className="bg-aurora-cyan shadow-[0_0_12px_rgba(0,210,255,0.75)]"
                aria-hidden
              />
              <span className="font-sans text-[17px] font-semibold leading-tight text-aurora-cyan">
                Voice Output
              </span>
            </div>
          </header>
        </div>

        {/* Row 2 — single horizontal band: waveforms meet the orb (reference: passes through center) */}
        <div className="relative flex w-full min-h-[5.25rem] items-center justify-center gap-0 py-0 sm:min-h-26 md:min-h-28">
          <div className="flex min-h-0 min-w-0 flex-1 items-center justify-end pr-0 md:pr-0.5">
            <BarVisualizer
              bars={barsIn}
              variant="cyan"
              decorative
              className="h-14 w-full max-w-none justify-end gap-px sm:h-16 md:h-[4.4rem]"
            />
          </div>
          <div className="relative z-20 -mx-0.5 shrink-0 sm:-mx-1.5 md:-mx-2">
            <VoiceOrb active={listenAnim} />
          </div>
          <div className="flex min-h-0 min-w-0 flex-1 items-center justify-start pl-0 md:pl-0.5">
            <BarVisualizer
              bars={barsInMirror}
              variant="magenta"
              decorative
              className="h-14 w-full max-w-none justify-start gap-px sm:h-16 md:h-[4.4rem]"
            />
          </div>
        </div>

        {/* Row 3 — language | controls | voice output stack (reference: output area on the right) */}
        <div
          className={cn(
            "grid grid-cols-1 gap-2",
            "lg:grid-cols-[minmax(0,1fr)_auto_minmax(220px,280px)] lg:items-center lg:gap-2 xl:gap-3",
          )}
        >
          <div className="order-2 flex min-w-0 justify-start lg:order-1 lg:max-w-[200px]">
            <SelectPill
              id={langId}
              label="Response language"
              value={selectValue}
              options={langOptions}
              onChange={onLanguageChange}
              title="Preferred language"
              icon={
                <Globe
                  className="size-4 shrink-0 text-aurora-cyan/90"
                  aria-hidden
                />
              }
              className="w-full"
            />
          </div>

          <div className="order-3 flex justify-center lg:order-2">
            <VoiceTransport
              handsFree={handsFree}
              onMic={onMicPrimary}
              onStop={onVoiceInterrupt}
              onSettings={
                onCaptureModeChange
                  ? () => onCaptureModeChange(handsFree ? "push" : "always")
                  : undefined
              }
              disabled={voiceBusy && !handsFree}
              isRecording={segmentOrPushHot}
            />
          </div>

          <div
            className="order-1 space-y-1 rounded-aurora-lg border border-cyan-400/24 bg-black/60 p-2.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.04),0_8px_24px_rgba(0,0,0,0.4)] backdrop-blur-md lg:order-3 lg:-mt-9 xl:-mt-10"
            aria-label="Voice output"
          >
            <p className="text-[14px] font-medium leading-tight text-white/82">
              {outputSubheading}
            </p>
            <p className="text-[15px] font-semibold leading-tight text-white/96">
              {outputStateLine}
            </p>
            {liveAssistantOutput.trim() ? (
              <p className="line-clamp-2 min-h-8 text-pretty text-[12px] font-normal leading-snug text-white/75">
                {outLine}
              </p>
            ) : <div className="min-h-8" />}
            <div>
              <span className="sr-only">Audio level</span>
              <BarVisualizer
                bars={barsOut}
                variant="gradient"
                dimInactive
                aria-label="Output level"
                className="h-10 w-full justify-between"
              />
            </div>
          </div>
        </div>
      </div>
    </HeroSurface>
  );
}
