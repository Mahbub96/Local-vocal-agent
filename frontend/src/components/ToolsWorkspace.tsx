import { Activity, Brain, Globe, HardDrive, Search, Wrench } from "lucide-react";
import type { SystemStatus, ToolActivity, VoiceStatus } from "../types/ui";
import { toolActivityLabels } from "../utils/tools";

type ToolsWorkspaceProps = {
  activities: ToolActivity[];
  voiceStatus: VoiceStatus | null;
  systemStatus: SystemStatus | null;
};

const CAPS = [
  { id: "filesystem" as const, title: "Filesystem", Icon: HardDrive },
  { id: "web" as const, title: "Web Search", Icon: Globe },
  { id: "memory" as const, title: "Memory", Icon: Brain },
];

export function ToolsWorkspace({
  activities,
  voiceStatus,
  systemStatus,
}: ToolsWorkspaceProps) {
  return (
    <section className="aurora-glass flex min-h-0 flex-1 flex-col overflow-hidden rounded-aurora-2xl border border-white/10 p-3.5 sm:p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-semibold text-white">Tools Workspace</h3>
          <p className="text-xs text-white/50">
            Live capability status and recent tool executions.
          </p>
        </div>
        <span className="inline-flex items-center gap-1 rounded-aurora-md border border-white/10 bg-white/3 px-2 py-1 text-[11px] text-white/65">
          <Wrench className="size-3.5" />
          {activities.length} recent activity
        </span>
      </div>

      <div className="mb-3 grid grid-cols-1 gap-2 md:grid-cols-3">
        {CAPS.map((cap) => {
          const hit = activities.find((a) => {
            const n = a.tool_name.toLowerCase();
            if (cap.id === "filesystem") return n.includes("file") || n.includes("read") || n.includes("fs");
            if (cap.id === "web") return n.includes("internet_search");
            return n.includes("memory");
          });
          const Icon = cap.Icon;
          const detail = hit ? toolActivityLabels(hit.tool_name).detail : "No recent run";
          return (
            <article
              key={cap.id}
              className="rounded-aurora-lg border border-white/10 bg-white/3 px-3 py-2.5"
            >
              <div className="mb-1 flex items-center gap-2">
                <Icon className="size-4 text-cyan-300/90" />
                <p className="text-sm font-semibold text-white/92">{cap.title}</p>
              </div>
              <p className="line-clamp-2 text-xs text-white/55">{detail}</p>
            </article>
          );
        })}
      </div>

      <div className="mb-3 grid grid-cols-1 gap-2 md:grid-cols-2">
        <article className="rounded-aurora-lg border border-white/10 bg-white/3 px-3 py-2.5">
          <div className="mb-1 flex items-center gap-2">
            <Activity className="size-4 text-emerald-300/90" />
            <p className="text-sm font-semibold text-white/92">Voice runtime</p>
          </div>
          <p className="text-xs text-white/65">
            State: <span className="text-white/90">{voiceStatus?.state ?? "unknown"}</span>
          </p>
          <p className="text-xs text-white/55">
            {voiceStatus?.detail || "No active detail."}
          </p>
        </article>
        <article className="rounded-aurora-lg border border-white/10 bg-white/3 px-3 py-2.5">
          <div className="mb-1 flex items-center gap-2">
            <Search className="size-4 text-cyan-300/90" />
            <p className="text-sm font-semibold text-white/92">Model runtime</p>
          </div>
          <p className="text-xs text-white/65">
            Model: <span className="text-white/90">{systemStatus?.model_name || "unknown"}</span>
          </p>
          <p className="text-xs text-white/55">
            Uptime: {systemStatus?.uptime_seconds != null ? `${Math.round(systemStatus.uptime_seconds)}s` : "N/A"}
          </p>
        </article>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-white/55">
          Recent tool log
        </h4>
        <div className="space-y-2">
          {activities.length ? (
            activities.map((a, idx) => {
              const l = toolActivityLabels(a.tool_name);
              return (
                <article
                  key={`${a.message_id}-${idx}`}
                  className="rounded-aurora-lg border border-white/10 bg-white/2 px-3 py-2.5"
                >
                  <p className="text-sm font-medium text-white/90">{l.title}</p>
                  <p className="text-xs text-white/55">{l.detail}</p>
                  <p className="mt-1 text-[11px] text-white/40">
                    {a.created_at ? new Date(a.created_at).toLocaleString() : "No timestamp"}
                  </p>
                </article>
              );
            })
          ) : (
            <p className="rounded-aurora-lg border border-white/10 bg-white/2 px-3 py-2.5 text-sm text-white/55">
              No tool activity yet.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
