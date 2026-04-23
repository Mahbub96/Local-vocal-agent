import { Card } from "../common/Card";
import { CardHeader } from "../common/CardHeader";
import { toolActivityLabels } from "../../utils/tools";
import type { ToolActivity } from "../../types/ui";

type ActivityPanelProps = {
  activities: ToolActivity[];
};

export function ActivityPanel({ activities }: ActivityPanelProps) {
  return (
    <Card className="activity-card">
      <CardHeader title="Tools Activity" icon="✦" subtitle="View All" />
      <div className="activity-list">
        {activities.map((activity) => {
          const { title, detail } = toolActivityLabels(activity.tool_name);
          return (
            <div key={activity.message_id} className="activity-row">
              <span className="activity-check" aria-hidden>✓</span>
              <div className="activity-body">
                <span className="activity-name">{title}</span>
                <span className="activity-detail muted">{detail}</span>
              </div>
              <small className="activity-time">
                {activity.created_at ? new Date(activity.created_at).toLocaleTimeString() : "—"}
              </small>
            </div>
          );
        })}
        {activities.length === 0 ? <p className="muted">No recent tool calls in this view.</p> : null}
      </div>
    </Card>
  );
}
