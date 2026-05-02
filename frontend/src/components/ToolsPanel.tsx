import { useMemo } from "react";
import { Brain, Check, FolderOpen, Search } from "lucide-react";
import { toolActivityLabels } from "../utils/tools";
import { latestActivityByCapability } from "../utils/toolCapabilities";
import type { ToolActivity } from "../types/ui";

type ToolsPanelProps = {
  activities: ToolActivity[];
};

const CAPABILITY_ROWS = [
  { id: "filesystem" as const, title: "Filesystem access", Icon: FolderOpen },
  { id: "web" as const, title: "Web search", Icon: Search },
  { id: "memory" as const, title: "Memory retrieval", Icon: Brain },
];

export function ToolsPanel({ activities }: ToolsPanelProps) {
  const latest = useMemo(() => latestActivityByCapability(activities), [activities]);

  return (
    <section className="aurora-glass rounded-3xl border border-white/10 p-4 md:p-5" aria-label="Tools activity">
      <h3 className="mb-4 text-sm font-semibold tracking-tight text-white">Tools Activity</h3>
      <ul className="space-y-2.5">
        {CAPABILITY_ROWS.map((row) => {
          const Icon = row.Icon;
          const act = latest.get(row.id);
          const { detail } = act ? toolActivityLabels(act.tool_name) : { detail: null };
          const sub = act?.created_at
            ? `Last used ${new Date(act.created_at).toLocaleTimeString()}`
            : "Ready";
          return (
            <li
              key={row.id}
              className="flex items-center gap-3 rounded-xl border border-white/5 bg-white/2 px-3 py-3 transition hover:border-white/10 hover:bg-white/4"
            >
              <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-emerald-500/15 text-emerald-300 shadow-[0_0_12px_rgba(52,211,153,0.25)] ring-1 ring-emerald-400/30">
                <Check className="size-4" strokeWidth={2.5} aria-hidden />
              </span>
              <Icon className="size-4 shrink-0 text-cyan-300/90" strokeWidth={2} aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-white/90">{row.title}</p>
                <p className="mt-0.5 text-xs text-white/45">{detail || sub}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
