import type { HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type SurfaceProps = HTMLAttributes<HTMLElement> & {
  as?: "section" | "div" | "article" | "aside";
  /** `glass` default card; `inset` nested panel */
  variant?: "glass" | "inset";
};

export function Surface({ as: Tag = "section", variant = "glass", className, ...props }: SurfaceProps) {
  return <Tag className={cn(variant === "inset" ? "aurora-glass-inset" : "aurora-glass", className)} {...props} />;
}
