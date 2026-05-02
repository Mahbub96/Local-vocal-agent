import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/cn";

export type RoundToolbarButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  /** `md` ≈ 44px, `lg` ≈ 52px at sm+ */
  size?: "md" | "lg";
  children: ReactNode;
};

/** Circular chrome button (border + subtle fill); for toolbars / voice transport. */
export function RoundToolbarButton({
  size = "md",
  className,
  type = "button",
  children,
  ...props
}: RoundToolbarButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "grid shrink-0 place-items-center rounded-full border border-white/12 bg-white/5 text-white/90 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] transition hover:border-white/20 hover:bg-white/10",
        size === "md" && "size-11 sm:size-12",
        size === "lg" && "size-13 sm:size-14",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
