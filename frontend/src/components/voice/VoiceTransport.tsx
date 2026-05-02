import { Mic, Sliders, Square } from "lucide-react";
import { cn } from "../../lib/cn";
import { GradientRingButton } from "../ui/GradientRingButton";
import { RoundToolbarButton } from "../ui/RoundToolbarButton";

export type VoiceTransportProps = {
  onMic?: () => void;
  /** Cancel recording + stop TTS playback. */
  onStop?: () => void;
  onSettings?: () => void;
  /** Disable controls (e.g. while uploading). */
  disabled?: boolean;
  /** Visual + a11y: mic is capturing (push) or always-listen is active. */
  isRecording?: boolean;
  /** Hands-free mode: mic ends continuous listening instead of push-to-talk. */
  handsFree?: boolean;
  className?: string;
};

/** Mic: push-to-talk or end hands-free · Stop: discard + silence audio · Settings: reserved. */
export function VoiceTransport({
  onMic,
  onStop,
  onSettings,
  disabled,
  isRecording,
  handsFree,
  className,
}: VoiceTransportProps) {
  const micTitle = handsFree
    ? "Stop hands-free listening"
    : isRecording
      ? "Tap to stop and send"
      : "Tap to speak";
  const micAria = handsFree ? "Stop hands-free listening" : isRecording ? "Stop recording and send" : "Start voice recording";

  return (
    <div className={cn("flex items-center justify-center gap-2 sm:gap-2.5", className)} role="group" aria-label="Voice controls">
      <RoundToolbarButton
        title={micTitle}
        aria-label={micAria}
        aria-pressed={Boolean(isRecording || handsFree)}
        onClick={onMic}
        disabled={disabled}
        className={cn(
          "size-10 sm:size-11",
          (isRecording || handsFree) && "border-cyan-400/45 bg-cyan-500/12 ring-1 ring-cyan-400/35",
        )}
      >
        <Mic className="size-4 sm:size-[1.05rem]" strokeWidth={1.75} />
      </RoundToolbarButton>
      <GradientRingButton
        ringVariant="cyan"
        title="Stop playback or cancel recording"
        aria-label="Stop playback or cancel recording"
        onClick={onStop}
        disabled={disabled}
        className="size-[2.95rem] shadow-[0_0_26px_rgba(0,210,255,0.45)] sm:size-[3.2rem]"
      >
        <Square className="size-3.5 fill-white text-white sm:size-[1.05rem]" strokeWidth={0} />
      </GradientRingButton>
      <RoundToolbarButton title="Voice settings" aria-label="Voice settings" onClick={onSettings} disabled={disabled} className="size-10 sm:size-11">
        <Sliders className="size-4 sm:size-[1.05rem]" strokeWidth={1.75} />
      </RoundToolbarButton>
    </div>
  );
}
