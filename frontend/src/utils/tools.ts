/**
 * Human-readable labels for persisted tool names from the assistant pipeline.
 * Keeps display strings out of presentational components.
 */
export function toolActivityLabels(toolName: string): { title: string; detail: string } {
  const n = toolName.toLowerCase();
  if (n === "internet_search_tool" || n.includes("internet_search")) {
    return { title: "Web Search", detail: "searched the web for your query" };
  }
  if (n === "memory_context_tool" || n.includes("memory")) {
    return { title: "Memory", detail: "retrieved long-term and session context" };
  }
  if (n.includes("file") || n.includes("read") || n.includes("fs")) {
    return { title: "Filesystem", detail: toolName };
  }
  return { title: toolName.replace(/_/g, " "), detail: toolName };
}
