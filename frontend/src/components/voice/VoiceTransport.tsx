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
    <div className={cn("flex items-center justify-center gap-3 sm:gap-4", className)} role="group" aria-label="Voice controls">
      <RoundToolbarButton
        title={micTitle}
        aria-label={micAria}
        aria-pressed={Boolean(isRecording || handsFree)}
        onClick={onMic}
        disabled={disabled}
        className={cn((isRecording || handsFree) && "border-cyan-400/45 bg-cyan-500/12 ring-1 ring-cyan-400/35")}
      >
        <Mic className="size-[1.15rem] sm:size-5" strokeWidth={1.75} />
      </RoundToolbarButton>
      <GradientRingButton
        title="Stop playback or cancel recording"
        aria-label="Stop playback or cancel recording"
        onClick={onStop}
        disabled={disabled}
      >
        <Square className="size-5 fill-white text-white sm:size-6" strokeWidth={0} />
      </GradientRingButton>
      <RoundToolbarButton title="Voice settings" aria-label="Voice settings" onClick={onSettings} disabled={disabled}>
        <Sliders className="size-[1.15rem] sm:size-5" strokeWidth={1.75} />
      </RoundToolbarButton>
    </div>
  );
}
