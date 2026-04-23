import type { ReactNode } from "react";

type CardHeaderProps = {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  action?: ReactNode;
};

export function CardHeader({ title, subtitle, icon, action }: CardHeaderProps) {
  return (
    <div className="card-title-row">
      <div className="card-title-left">
        {icon != null ? <span className="card-title-ic" aria-hidden>{icon}</span> : null}
        <h3>{title}</h3>
      </div>
      <div className="card-title-right">
        {subtitle ? <span className="muted card-title-link">{subtitle}</span> : null}
        {action}
      </div>
    </div>
  );
}
