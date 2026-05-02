import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

export type StackHeadingProps = {
  title: string;
  subtitle?: string;
  titleId?: string;
  /** e.g. `<GlowDot className="bg-…" />` */
  leading?: ReactNode;
  className?: string;
  titleClassName?: string;
  subtitleClassName?: string;
  /** Announce subtitle changes (e.g. live speech caption). */
  subtitleAriaLive?: "off" | "polite" | "assertive";
};

/** Title row + optional muted subtitle; accessible heading + description. */
export function StackHeading({
  title,
  subtitle,
  titleId,
  leading,
  className,
  titleClassName,
  subtitleClassName,
  subtitleAriaLive = "off",
}: StackHeadingProps) {
  return (
    <header className={cn("shrink-0 space-y-1", className)}>
      <div className="flex items-center gap-2.5">
        {leading}
        <h2
          id={titleId}
          className={cn("font-sans text-lg font-semibold tracking-tight text-white md:text-xl", titleClassName)}
        >
          {title}
        </h2>
      </div>
      {subtitle != null && subtitle !== "" && (
        <p
          className={cn("text-sm leading-snug text-aurora-voice-caption", subtitleClassName)}
          aria-live={subtitleAriaLive === "off" ? undefined : subtitleAriaLive}
        >
          {subtitle}
        </p>
      )}
    </header>
  );
}
