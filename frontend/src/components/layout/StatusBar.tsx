import { formatUptimeSeconds } from "../../utils/time";

type StatusBarProps = {
  modelName: string;
  uptimeSeconds: number | null;
  totalResponses: number;
  totalTokens: number;
  allSystemsOk: boolean;
};

export function StatusBar({
  modelName,
  uptimeSeconds,
  totalResponses,
  totalTokens,
  allSystemsOk,
}: StatusBarProps) {
  return (
    <footer className="status-bar" role="contentinfo">
      <div className="status-bar__left">
        <span className="status-bar__dot" aria-hidden />
        <span className="status-bar__label">Model: {modelName}</span>
      </div>
      <div className="status-bar__mid">
        <span>Responses: {totalResponses}</span>
        <span className="status-bar__tokens">
          <span className="status-bar__spark" aria-hidden>✦</span>
          Tokens: {totalTokens.toLocaleString()}
        </span>
      </div>
      <div className="status-bar__right">
        <span>Uptime: {uptimeSeconds != null ? formatUptimeSeconds(uptimeSeconds) : "—"}</span>
        <span className="status-bar__ops">
          <span className="status-bar__dot status-bar__dot--ok" aria-hidden />
          {allSystemsOk ? "All systems operational" : "Degraded"}
        </span>
      </div>
    </footer>
  );
}
