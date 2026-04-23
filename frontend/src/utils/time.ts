export function formatUptimeSeconds(total: number): string {
  if (total < 60) return `${total}s`;
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export function formatMessageTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" }).format(d);
}

/** Label for the chat list day divider (e.g. Today), from session or message time. */
export function formatSessionDayLabel(iso: string | null | undefined): string {
  if (!iso) return "Today";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Today";
  const today = new Date();
  if (d.toDateString() === today.toDateString()) return "Today";
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(d);
}
