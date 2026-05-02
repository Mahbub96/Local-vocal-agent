import { motion } from "framer-motion";
import { cn } from "../../lib/cn";

export type VisualBar = { h: number; on: boolean };

export type BarVisualizerProps = {
  bars: VisualBar[];
  /** `cyan` = input (left); `magenta` = mirrored input (right); `gradient` = output meter (purple→cyan). */
  variant?: "cyan" | "magenta" | "gradient";
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
  magenta:
    "bg-linear-to-t from-aurora-pink to-aurora-purple shadow-[0_0_14px_rgba(168,85,247,0.85)]",
  gradient:
    "bg-linear-to-t from-aurora-purple to-aurora-cyan shadow-[0_0_12px_rgba(0,210,255,0.5)]",
} as const;

/** Idle bars stay on-brand (reference: cyan / purple bands, not flat gray). */
const inactive = {
  cyan: "bg-cyan-400/28 shadow-[0_0_8px_rgba(34,211,238,0.25)]",
  magenta: "bg-fuchsia-400/26 shadow-[0_0_8px_rgba(232,121,249,0.22)]",
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
        (variant === "cyan" || variant === "magenta") && "h-16 gap-[3px] px-1 sm:h-18 sm:gap-1",
        variant === "gradient" && "h-18 justify-between gap-0.5 sm:gap-1",
        className,
      )}
      {...a11y}
    >
      {bars.map((b, i) => (
        <motion.span
          key={i}
          className={cn(
            (variant === "cyan" || variant === "magenta") && "w-[3px] rounded-sm sm:w-1",
            variant === "gradient" && "min-w-0 max-w-[10px] flex-1 rounded-sm",
            b.on ? active[variant] : inactive[variant],
          )}
          initial={false}
          animate={{
            height:
              variant === "gradient" && dimInactive && !b.on ? Math.max(4, b.h * 0.25) : b.h,
          }}
          transition={{
            type: "spring",
            stiffness: variant === "gradient" ? 380 : 420,
            damping: variant === "gradient" ? 26 : 28,
          }}
        />
      ))}
    </div>
  );
}
