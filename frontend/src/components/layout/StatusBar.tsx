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
    <footer
      className="aurora-status-bar flex shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-1.5 px-3 py-2 text-[10px] sm:gap-x-5 sm:gap-y-2 sm:px-4 sm:py-2.5 sm:text-[11px] md:px-5 md:text-xs"
      role="contentinfo"
    >
      <div className="flex min-w-0 max-w-[45%] items-center gap-1.5 sm:max-w-none sm:gap-2">
        <span
          className={`size-2 shrink-0 rounded-full ${allSystemsOk ? "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.75)]" : "bg-amber-400"}`}
          aria-hidden
        />
        <span className="min-w-0 truncate">
          <span className="text-aurora-fg-muted">Model:</span>{" "}
          <span className="font-medium text-aurora-fg/85">{modelName}</span>
        </span>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 sm:justify-start sm:gap-x-5">
        <span>
          <span className="text-aurora-fg-muted sm:hidden">R:</span>
          <span className="hidden text-aurora-fg-muted sm:inline">Responses:</span>{" "}
          <span className="tabular-nums text-aurora-fg/80">{totalResponses}</span>
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="text-aurora-cyan/80" aria-hidden>
            ✦
          </span>
          <span className="text-aurora-fg-muted sm:hidden">T:</span>
          <span className="hidden text-aurora-fg-muted sm:inline">Tokens:</span>{" "}
          <span className="tabular-nums text-aurora-fg/80">{totalTokens.toLocaleString()}</span>
        </span>
        <span className="hidden sm:inline">
          <span className="text-aurora-fg-muted">Uptime:</span>{" "}
          <span className="tabular-nums text-aurora-fg/80">
            {uptimeSeconds != null ? formatUptimeSeconds(uptimeSeconds) : "—"}
          </span>
        </span>
      </div>
      <div className="flex w-full basis-full items-center justify-center gap-2 border-t border-aurora-divider pt-1.5 sm:w-auto sm:basis-auto sm:border-0 sm:pt-0">
        <span
          className={`size-2 rounded-full ${allSystemsOk ? "bg-emerald-400" : "bg-rose-400"}`}
          aria-hidden
        />
        <span className={allSystemsOk ? "text-emerald-300/90" : "text-amber-200/90"}>
          <span className="sm:hidden">{allSystemsOk ? "Operational" : "Degraded"}</span>
          <span className="hidden sm:inline">{allSystemsOk ? "All systems operational" : "Degraded"}</span>
        </span>
      </div>
    </footer>
  );
}
