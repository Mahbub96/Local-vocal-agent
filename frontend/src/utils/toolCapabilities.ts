import type { ToolActivity } from "../types/ui";

export type ToolCapabilityId = "filesystem" | "web" | "memory";

/** Maps backend tool names to one of the three design-spec capability rows. */
export function classifyToolName(toolName: string): ToolCapabilityId | null {
  const n = toolName.toLowerCase();
  if (n === "internet_search_tool" || n.includes("internet_search")) return "web";
  if (n.includes("memory")) return "memory";
  if (n.includes("file") || n.includes("read") || n.includes("fs")) return "filesystem";
  return null;
}

/** Latest activity per capability (by `created_at`). */
export function latestActivityByCapability(activities: ToolActivity[]): Map<ToolCapabilityId, ToolActivity> {
  const map = new Map<ToolCapabilityId, ToolActivity>();
  for (const a of activities) {
    const id = classifyToolName(a.tool_name);
    if (!id) continue;
    const prev = map.get(id);
    if (!prev) {
      map.set(id, a);
      continue;
    }
    const tNew = a.created_at ? Date.parse(a.created_at) : 0;
    const tPrev = prev.created_at ? Date.parse(prev.created_at) : 0;
    if (tNew >= tPrev) map.set(id, a);
  }
  return map;
}
