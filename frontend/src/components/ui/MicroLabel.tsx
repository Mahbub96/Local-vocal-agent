import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

export type MicroLabelProps = HTMLAttributes<HTMLParagraphElement>;

/** Uppercase micro label (section captions, meter titles). */
export function MicroLabel({ className, ...props }: MicroLabelProps) {
  return (
    <p
      className={cn("text-[11px] font-semibold uppercase tracking-[0.18em] text-white/45", className)}
      {...props}
    />
  );
}
