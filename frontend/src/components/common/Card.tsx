import type { PropsWithChildren } from "react";

type CardProps = PropsWithChildren<{
  className?: string;
}>;

export function Card({ className, children }: CardProps) {
  return <article className={`card ${className ?? ""}`.trim()}>{children}</article>;
}
