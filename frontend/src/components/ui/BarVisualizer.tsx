import { motion } from "framer-motion";
import { cn } from "../../lib/cn";

export type VisualBar = { h: number; on: boolean };

export type BarVisualizerProps = {
  bars: VisualBar[];
  /** `cyan` = input-style bars; `gradient` = output meter (purple→cyan). */
  variant?: "cyan" | "gradient";
  className?: string;
  /** When `gradient`, inactive bars use a dim height for motion. */
  dimInactive?: boolean;
  /** Purely decorative (no `role` / label). */
  decorative?: boolean;
  /** Required when not decorative — e.g. "Output level". */
  "aria-label"?: string;
};

const active = {
  cyan: "bg-aurora-cyan shadow-[0_0_14px_rgba(0,210,255,0.9)]",
  gradient:
    "bg-linear-to-t from-[#9d50bb] to-[#00d2ff] shadow-[0_0_12px_rgba(0,210,255,0.5)]",
} as const;

const inactive = {
  cyan: "bg-white/12",
  gradient: "bg-white/10",
} as const;

/** Animated vertical bars driven by level data (any source). */
export function BarVisualizer({
  bars,
  variant = "cyan",
  className,
  dimInactive = false,
  decorative = false,
  "aria-label": ariaLabel,
}: BarVisualizerProps) {
  const a11y =
    decorative || !ariaLabel
      ? { "aria-hidden": true as const }
      : { role: "img" as const, "aria-label": ariaLabel };

  return (
    <div
      className={cn(
        "flex max-w-full items-end justify-center",
        variant === "cyan" && "h-16 gap-[3px] px-1 sm:h-18 sm:gap-1",
        variant === "gradient" && "h-18 justify-between gap-0.5 sm:gap-1",
        className,
      )}
      {...a11y}
    >
      {bars.map((b, i) => (
        <motion.span
          key={i}
          className={cn(
            variant === "cyan" && "w-[3px] rounded-sm sm:w-1",
            variant === "gradient" && "min-w-0 max-w-[10px] flex-1 rounded-sm",
            b.on ? active[variant] : inactive[variant],
          )}
          initial={false}
          animate={{
            height:
              variant === "gradient" && dimInactive && !b.on ? Math.max(4, b.h * 0.25) : b.h,
          }}
          transition={{ type: "spring", stiffness: variant === "cyan" ? 420 : 380, damping: variant === "cyan" ? 28 : 26 }}
        />
      ))}
    </div>
  );
}
