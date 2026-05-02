import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/cn";

export type HeroSurfaceProps = HTMLAttributes<HTMLElement> & {
  as?: "section" | "div" | "article";
  /** Top-centered blue wash (Aurora hero). */
  withRadialHighlight?: boolean;
  children: ReactNode;
};

/** Large rounded canvas card with optional top radial glow. */
export function HeroSurface({
  as: Tag = "section",
  withRadialHighlight = true,
  className,
  children,
  ...props
}: HeroSurfaceProps) {
  return (
    <Tag
      className={cn(
        "relative overflow-hidden rounded-3xl border border-white/[0.09] bg-[#0b0d17]/92 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.07),0_0_64px_-18px_rgba(0,210,255,0.14),0_0_72px_-28px_rgba(157,80,187,0.16)] sm:p-5 md:p-6",
        className,
      )}
      {...props}
    >
      {withRadialHighlight && (
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_85%_55%_at_50%_-8%,rgba(0,210,255,0.1),transparent_52%),radial-gradient(ellipse_60%_40%_at_80%_100%,rgba(157,80,187,0.08),transparent_45%)]"
          aria-hidden
        />
      )}
      {children}
    </Tag>
  );
}
