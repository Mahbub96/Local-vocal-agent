export function getStatusLabel(
  status: string,
): "done" | "running" | "pending" | "skip" {
  if (status === "completed" || status === "ready" || status === "done") return "done";
  if (status === "running" || status === "in_progress" || status === "active") return "running";
  if (status === "skipped") return "skip";
  return "pending";
}
