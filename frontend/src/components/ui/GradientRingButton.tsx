import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/cn";

export type GradientRingButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  /** Classes for the inner filled disc (e.g. icon background). */
  innerClassName?: string;
};

/** Primary action: gradient ring with inner content (e.g. stop). */
export function GradientRingButton({
  className,
  innerClassName,
  type = "button",
  children,
  ...props
}: GradientRingButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "grid size-13 shrink-0 place-items-center rounded-full bg-linear-to-br from-[#9d50bb] via-indigo-500 to-[#00d2ff] p-[2px] shadow-[0_0_40px_rgba(157,80,187,0.58)] transition hover:scale-[1.02] hover:shadow-[0_0_48px_rgba(157,80,187,0.7)] sm:size-14",
        className,
      )}
      {...props}
    >
      <span className={cn("grid size-full place-items-center rounded-full bg-aurora-canvas/95", innerClassName)}>
        {children}
      </span>
    </button>
  );
}
