import type { VisualBar } from "../ui/BarVisualizer";
import { BarVisualizer } from "../ui/BarVisualizer";
import { GlowDot } from "../ui/GlowDot";
import { MicroLabel } from "../ui/MicroLabel";
import { cn } from "../../lib/cn";

export type VoiceOutputAsideProps = {
  /** Main status line (e.g. assistant transcript or state). */
  body: string;
  /** Bars for the output level meter. */
  meterBars: VisualBar[];
  className?: string;
  /** Column heading (default: Voice Output). */
  heading?: string;
  /** Muted line under heading (default: Speaking…). */
  subheading?: string;
  /** Meter section label (default: Audio Level). */
  meterLabel?: string;
};

/** Right column: status + transcript + level meter. */
export function VoiceOutputAside({
  body,
  meterBars,
  className,
  heading = "Voice Output",
  subheading = "Speaking…",
  meterLabel = "Audio Level",
}: VoiceOutputAsideProps) {
  return (
    <aside
      className={cn(
        "flex min-h-0 flex-col rounded-aurora-xl border border-white/[0.08] bg-black/30 p-3.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_0_40px_-12px_rgba(0,210,255,0.08)] sm:p-4",
        className,
      )}
      aria-label="Voice output"
    >
      <div className="shrink-0">
        <div className="flex items-center gap-2">
          <GlowDot className="bg-aurora-voice-output-dot shadow-[0_0_10px_rgba(56,189,248,0.85)]" aria-hidden />
          <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white">{heading}</span>
        </div>
        <p className="mt-2 text-sm font-medium text-aurora-voice-caption">{subheading}</p>
        <p className="mt-2 min-h-18 font-sans text-sm font-normal leading-relaxed text-balance-safe text-white sm:min-h-20">
          {body}
        </p>
      </div>

      <div className="mt-6 shrink-0 border-t border-white/6 pt-4 lg:mt-auto">
        <MicroLabel className="mb-2">{meterLabel}</MicroLabel>
        <BarVisualizer
          bars={meterBars}
          variant="gradient"
          dimInactive
          aria-label="Output level"
        />
      </div>
    </aside>
  );
}
