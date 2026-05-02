import { useMemo } from "react";
import { Brain, Check, FolderOpen, Search } from "lucide-react";
import { toolActivityLabels } from "../utils/tools";
import { latestActivityByCapability } from "../utils/toolCapabilities";
import type { ToolActivity } from "../types/ui";

type ToolsPanelProps = {
  activities: ToolActivity[];
};

const CAPABILITY_ROWS = [
  {
    id: "filesystem" as const,
    title: "Filesystem access",
    fallbackDetail: "Ready",
    Icon: FolderOpen,
  },
  {
    id: "web" as const,
    title: "Web search",
    fallbackDetail: "Not used yet for this session",
    Icon: Search,
  },
  {
    id: "memory" as const,
    title: "Memory retrieval",
    fallbackDetail: "Retrieved long-term and session context",
    Icon: Brain,
  },
];

export function ToolsPanel({ activities }: ToolsPanelProps) {
  const latest = useMemo(() => latestActivityByCapability(activities), [activities]);

  return (
    <section
      className="aurora-glass rounded-aurora-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(16,22,40,0.9),rgba(10,14,28,0.92))] p-3.5 md:p-4"
      aria-label="Tools activity"
    >
      <h3 className="mb-2.5 text-sm font-semibold tracking-tight text-white">Tools Activity</h3>
      <ul className="space-y-2.5">
        {CAPABILITY_ROWS.map((row) => {
          const Icon = row.Icon;
          const act = latest.get(row.id);
          const { detail } = act ? toolActivityLabels(act.tool_name) : { detail: null };
          const sub = detail || row.fallbackDetail;
          return (
            <li
              key={row.id}
              className="flex items-center gap-2.5 rounded-aurora-xl border border-white/8 bg-white/3 px-2.5 py-3 transition hover:border-white/15 hover:bg-white/5 sm:gap-3 sm:px-3"
            >
              <span className="grid size-10 shrink-0 place-items-center rounded-aurora-lg border border-emerald-300/20 bg-emerald-400/10 text-emerald-200 shadow-[0_0_16px_rgba(16,185,129,0.35)]">
                <Check className="size-4" strokeWidth={2.5} aria-hidden />
              </span>
              <Icon className="size-4 shrink-0 text-aurora-cyan/95" strokeWidth={2} aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-[1.05rem] font-semibold leading-tight text-white/95">{row.title}</p>
                <p className="mt-1 text-[0.72rem] leading-tight text-white/55">{sub}</p>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
