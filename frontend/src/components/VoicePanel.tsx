import { Globe } from "lucide-react";
import { useId, useMemo } from "react";
import { cn } from "../lib/cn";
import type { VoiceCaptureMode } from "../hooks/useVoiceCapture";
import { BarVisualizer, GlowDot, HeroSurface, SelectPill, StackHeading } from "./ui";
import { VoiceOrb } from "./voice/VoiceOrb";
import { VoiceOutputAside } from "./voice/VoiceOutputAside";
import { VoiceTransport } from "./voice/VoiceTransport";
import { shortVoiceStateLabel, titleFromVoiceState } from "./voice/voiceLabels";
import { useVoiceLanguageOptions } from "./voice/voiceLanguage";
import { useLevelBars } from "../hooks/useLevelBars";
import type { VoiceStatus } from "../types/ui";

type VoicePanelProps = {
  voiceStatus: VoiceStatus | null;
  languageLabel: string;
  lastAssistantSnippet: string;
  /** Live assistant text while streaming chat or TTS-synced voice caption. */
  liveAssistantOutput?: string;
  onLanguageChange?: (language: string) => void;
  captureMode: VoiceCaptureMode;
  onCaptureModeChange: (mode: VoiceCaptureMode) => void;
  /** Local mic capture (browser) — drives orb + transport. */
  isListening?: boolean;
  voiceBusy?: boolean;
  onMicPrimary?: () => void;
  onVoiceInterrupt?: () => void;
  /** Live caption from Web Speech API while recording. */
  liveUserText?: string;
  /** RMS-based level (0–100) for input bars while recording. */
  micLevelLocal?: number;
};

export function VoicePanel({
  voiceStatus,
  languageLabel,
  lastAssistantSnippet,
  liveAssistantOutput = "",
  onLanguageChange,
  captureMode,
  onCaptureModeChange,
  isListening = false,
  voiceBusy = false,
  onMicPrimary,
  onVoiceInterrupt,
  liveUserText = "",
  micLevelLocal,
}: VoicePanelProps) {
  const st = voiceStatus?.state;
  const s = st?.toLowerCase() ?? "idle";
  const serverLevel = Math.max(0, Math.min(100, voiceStatus?.audio_level ?? 0));
  const level = isListening && micLevelLocal != null ? micLevelLocal : serverLevel;
  const langId = useId();
  const langOptions = useVoiceLanguageOptions(languageLabel);
  const handsFree = captureMode === "always";

  const barsIn = useLevelBars(20, level, 1);
  const barsOut = useLevelBars(18, s === "speaking" ? level + 15 : level, 3);

  const listenAnim = s === "listening" || s === "transcribing" || s === "speaking" || isListening;

  const hint = useMemo(() => {
    if (voiceStatus?.detail && s !== "idle" && s !== "ready") return voiceStatus.detail;
    if (s === "listening") return "I'm listening. How can I help you?";
    if (s === "idle" || s === "ready") return "How can I help you?";
    return "Processing…";
  }, [voiceStatus?.detail, s]);

  const listeningSubtitle = useMemo(() => {
    const live = liveUserText.trim();
    if (live) return live;
    return "I'm listening. How can I help you?";
  }, [liveUserText]);

  const showLiveCaptionStyle = isListening && Boolean(liveUserText.trim());

  const panelTitle = useMemo(() => {
    if (handsFree && isListening) return "Hands-free…";
    if (isListening) return "Listening…";
    return titleFromVoiceState(st);
  }, [handsFree, isListening, st]);

  const stackSubtitle = useMemo(() => {
    if (handsFree && isListening) {
      return "Speak anytime — segments send after a short pause. Tap the mic to stop.";
    }
    if (isListening) return listeningSubtitle;
    return hint;
  }, [handsFree, isListening, listeningSubtitle, hint]);

  const outLine = useMemo(() => {
    const live = liveAssistantOutput.trim();
    if (live) {
      return live.length > 220 ? `${live.slice(0, 217)}…` : live;
    }
    if (s === "speaking" && lastAssistantSnippet.trim()) {
      const t = lastAssistantSnippet.trim();
      return t.length > 220 ? `${t.slice(0, 217)}…` : t;
    }
    if (s === "speaking" && !lastAssistantSnippet.trim()) return "…";
    return shortVoiceStateLabel(st);
  }, [s, lastAssistantSnippet, st, liveAssistantOutput]);

  const outputSubheading = useMemo(() => {
    if (liveAssistantOutput.trim()) return "Live response";
    if (s === "speaking") return "Speaking…";
    return "Idle";
  }, [liveAssistantOutput, s]);

  const selectValue = langOptions.includes(languageLabel) ? languageLabel : langOptions[0]!;

  return (
    <HeroSurface aria-label="Voice assistant">
      <div className="relative grid grid-cols-1 gap-6 lg:min-h-[min(380px,52vh)] lg:grid-cols-12 lg:gap-5 lg:items-stretch xl:gap-8">
        <div className="flex min-h-0 flex-col gap-4 lg:col-span-3">
          <StackHeading
            titleId="voice-title"
            title={panelTitle}
            subtitle={stackSubtitle}
            subtitleAriaLive={isListening ? "polite" : "off"}
            subtitleClassName={cn(
              isListening && "min-h-[2.75rem]",
              showLiveCaptionStyle && "text-base font-normal leading-relaxed text-white/95",
              isListening && !showLiveCaptionStyle && "text-aurora-voice-caption",
            )}
            leading={
              <GlowDot className="bg-aurora-voice-live shadow-[0_0_10px_rgba(34,197,94,0.9)]" aria-hidden />
            }
          />

          <div className="mt-auto flex shrink-0 flex-col gap-3">
            <label className="flex cursor-pointer select-none flex-wrap items-center gap-x-2.5 gap-y-1 rounded-aurora-xl border border-white/10 bg-white/4 px-3 py-2.5 text-xs text-white/80 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] transition hover:border-white/15 hover:bg-white/6">
              <input
                type="checkbox"
                className="size-4 shrink-0 rounded border-white/25 bg-white/5 text-[#00d2ff] focus:ring-[#00d2ff]/40"
                checked={handsFree}
                onChange={(e) => onCaptureModeChange(e.target.checked ? "always" : "push")}
                disabled={voiceBusy && !handsFree}
              />
              <span className="font-medium text-white/95">Always listen</span>
              <span className="w-full text-[11px] text-white/45 sm:w-auto sm:pl-0">
                Auto-send after you pause
              </span>
            </label>
            <SelectPill
              id={langId}
              label="Response language"
              value={selectValue}
              options={langOptions}
              onChange={onLanguageChange}
              title="Preferred language"
              icon={<Globe className="size-4 shrink-0 text-[#00d2ff]/90" aria-hidden />}
            />
          </div>
        </div>

        <div className="flex min-h-0 flex-col items-center justify-center gap-6 lg:col-span-5 xl:col-span-6">
          <div className="flex w-full flex-col items-center justify-center gap-5 sm:flex-row sm:gap-4 md:gap-6">
            <VoiceOrb active={listenAnim} />
            <div className="h-16 w-full min-w-0 max-w-md flex-1 sm:h-20 lg:max-w-[min(100%,20rem)]">
              <BarVisualizer
                bars={barsIn}
                variant="cyan"
                decorative
                className="h-full w-full justify-start sm:justify-center"
              />
            </div>
          </div>
          <VoiceTransport
            handsFree={handsFree}
            onMic={onMicPrimary}
            onStop={onVoiceInterrupt}
            disabled={voiceBusy && !handsFree}
            isRecording={isListening}
          />
        </div>

        <VoiceOutputAside
          className="lg:col-span-4 xl:col-span-3"
          body={outLine}
          meterBars={barsOut}
          subheading={outputSubheading}
        />
      </div>
    </HeroSurface>
  );
}
