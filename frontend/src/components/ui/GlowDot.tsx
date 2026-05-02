import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

export type GlowDotProps = HTMLAttributes<HTMLSpanElement>;

/** Small status indicator dot (color via `className`, e.g. `bg-aurora-voice-live`). */
export function GlowDot({ className, ...props }: GlowDotProps) {
  return <span className={cn("size-2 shrink-0 rounded-full", className)} {...props} />;
}
