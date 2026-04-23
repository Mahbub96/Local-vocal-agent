import { Card } from "../common/Card";
import { CardHeader } from "../common/CardHeader";
import { getStatusLabel } from "../../utils/thinkingStatus";
import type { ThinkingStep } from "../../types/ui";

type ThinkingPanelProps = {
  thinking: ThinkingStep[];
};

function markClassName(kind: ReturnType<typeof getStatusLabel>) {
  if (kind === "pending") return "pend";
  return kind;
}

function StepMark({ kind }: { kind: ReturnType<typeof getStatusLabel> }) {
  return <span className={`thinking-mark thinking-mark--${markClassName(kind)}`} aria-hidden />;
}

export function ThinkingPanel({ thinking }: ThinkingPanelProps) {
  return (
    <Card className="thinking-card">
      <CardHeader title="Thinking Process" icon="🧠" />
      <div className="thinking-list">
        {thinking.slice(0, 6).map((step) => {
          const k = getStatusLabel(step.status);
          return (
            <div className="thinking-item" key={step.key}>
              <StepMark kind={k} />
              <div className="thinking-item__body">
                <p>{step.label}</p>
                <small>
                  {step.detail ||
                    (k === "running"
                      ? "Working…"
                      : k === "pending"
                        ? "Queued"
                        : k === "skip"
                          ? "Skipped for this request"
                          : "Done")}
                </small>
              </div>
            </div>
          );
        })}
        {thinking.length === 0 ? <p className="muted">Waiting for session activity.</p> : null}
      </div>
    </Card>
  );
}
