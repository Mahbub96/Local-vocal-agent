import type { ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

export type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  /** `md` = 40px rail, `sm` = 36px compact */
  size?: "md" | "sm";
  /** `amber` = theme toggle glow; default matches chrome icon buttons */
  variant?: "default" | "amber";
};

export function IconButton({
  size = "md",
  variant = "default",
  className,
  type = "button",
  ...props
}: IconButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        size === "sm" ? "aurora-icon-btn-sm" : "aurora-icon-btn",
        variant === "amber" &&
          "text-amber-200/90 shadow-[0_0_20px_rgba(251,191,36,0.12)] hover:border-amber-400/30",
        className,
      )}
      {...props}
    />
  );
}
