import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/cn";

export type GradientRingButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  /** Classes for the inner filled disc (e.g. icon background). */
  innerClassName?: string;
  /** `cyan` = electric-blue stop ring (reference UI); default = purple→cyan aurora ring. */
  ringVariant?: "aurora" | "cyan";
};

/** Primary action: gradient ring with inner content (e.g. stop). */
export function GradientRingButton({
  className,
  innerClassName,
  ringVariant = "aurora",
  type = "button",
  children,
  ...props
}: GradientRingButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "grid size-[3.35rem] shrink-0 place-items-center rounded-full p-[2.5px] transition hover:scale-[1.02] sm:size-[3.65rem]",
        ringVariant === "cyan" &&
          "bg-linear-to-br from-aurora-cyan via-sky-400 to-indigo-500 shadow-[0_0_28px_rgba(0,209,255,0.55),0_0_48px_rgba(0,209,255,0.25)] hover:shadow-[0_0_36px_rgba(0,209,255,0.65)]",
        ringVariant === "aurora" &&
          "bg-linear-to-br from-aurora-purple via-indigo-500 to-aurora-cyan shadow-[0_0_40px_rgba(157,80,187,0.58)] hover:shadow-[0_0_48px_rgba(157,80,187,0.7)]",
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
