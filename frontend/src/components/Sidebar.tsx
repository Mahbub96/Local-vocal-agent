import { useState } from "react";
import {
  Brain,
  FolderOpen,
  Home,
  MessageSquare,
  Search,
  Settings,
  Terminal,
  Wrench,
  X,
} from "lucide-react";
import type { Metrics } from "../types/ui";
import { cn } from "../lib/cn";
import { SystemStatus } from "./SystemStatus";
import { NAV_ITEMS, type NavItem } from "./layout/navConfig";

const NAV_ICONS = {
  Home,
  Chat: MessageSquare,
  Memory: Brain,
  Files: FolderOpen,
  Tools: Wrench,
  Search,
  Settings,
} as const;

type SidebarProps = {
  metrics: Metrics | null;
  fileEntryCount: number | null;
  activeNav?: NavItem;
  onNavSelect?: (item: NavItem) => void;
  /** Close the mobile drawer (shown only below `xl`). */
  onRequestClose?: () => void;
  className?: string;
};

export function Sidebar({
  metrics,
  fileEntryCount,
  activeNav = "Home",
  onNavSelect,
  onRequestClose,
  className,
}: SidebarProps) {
  const [devMode, setDevMode] = useState(false);

  return (
    <aside
      className={cn(
        "flex min-h-0 w-full min-w-0 shrink-0 flex-col overflow-y-auto border-r border-white/10 bg-[linear-gradient(180deg,#070b16_0%,#050812_100%)] px-2.5 py-3 backdrop-blur-xl xl:h-full xl:w-aurora-rail",
        className,
        devMode && "ring-1 ring-aurora-cyan/30",
      )}
    >
      <div className="mb-5 flex items-start justify-between gap-2 px-0.5 sm:mb-6">
        <div className="relative h-14 flex-1" aria-hidden>
          <span className="pointer-events-none absolute left-11 right-2 top-1/2 h-4 -translate-y-1/2 rounded-full bg-[linear-gradient(90deg,rgba(112,78,177,0.22),rgba(58,38,103,0.14)_42%,rgba(8,12,24,0.0))]" />
          <span className="pointer-events-none absolute left-11 right-2 top-1/2 h-px -translate-y-1/2 bg-linear-to-r from-cyan-200/24 via-fuchsia-300/16 to-transparent" />
          <div className="relative size-11 rounded-full border border-cyan-100/16 shadow-[0_0_10px_rgba(102,187,235,0.22)]">
            <span className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_32%_24%,rgba(197,243,255,0.95),rgba(95,177,210,0.72)_38%,rgba(76,103,168,0.58)_66%,rgba(82,62,143,0.52)_100%)]" />
            <span className="absolute inset-[18%] rounded-full bg-[radial-gradient(circle_at_28%_20%,rgba(255,255,255,0.28),transparent_56%)]" />
          </div>
        </div>
        {onRequestClose ? (
          <button
            type="button"
            className="grid size-8.5 place-items-center rounded-xl border border-white/12 bg-white/5 text-white/70 transition hover:bg-white/10 xl:hidden"
            aria-label="Close navigation"
            onClick={onRequestClose}
          >
            <X className="size-4.5" strokeWidth={1.75} />
          </button>
        ) : null}
      </div>

      <nav className="flex flex-1 flex-col gap-1.5 px-0.5" aria-label="Main navigation">
        {NAV_ITEMS.map((item) => {
          const Icon = NAV_ICONS[item];
          const active = activeNav === item;
          return (
            <button
              key={item}
              type="button"
              onClick={() => onNavSelect?.(item)}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group flex w-full items-center gap-2.5 rounded-full border border-transparent px-3 py-2.5 text-left text-[14px] text-white/74 transition-all duration-200",
                active
                  ? "border-cyan-300/24 bg-[linear-gradient(90deg,rgba(97,57,153,0.33),rgba(58,37,101,0.24))] text-white shadow-[0_0_12px_rgba(111,66,168,0.2),inset_0_1px_0_rgba(255,255,255,0.08)]"
                  : "hover:border-white/8 hover:bg-white/4 hover:text-white/90",
              )}
            >
              <Icon
                className={cn(
                  "size-4 shrink-0 stroke-[1.75]",
                  active ? "text-white" : "text-white/62 group-hover:text-white/88",
                )}
              />
              <span className={cn("font-semibold tracking-[0.005em]", !active && "font-medium text-white/82")}>
                {item}
                {item === "Files" && fileEntryCount != null ? (
                  <span className="ml-1 text-xs font-normal text-white/40">
                    {" "}
                    {fileEntryCount}
                  </span>
                ) : null}
              </span>
            </button>
          );
        })}
      </nav>

      <div className="mt-5 flex min-h-0 flex-1 flex-col justify-end gap-3">
        <SystemStatus metrics={metrics} />
        <button
          type="button"
          onClick={() => setDevMode((d) => !d)}
          aria-pressed={devMode}
          className={cn(
            "flex items-center justify-between gap-2 rounded-xl border px-2.5 py-2 text-left text-[11px] font-medium transition-all",
            devMode
              ? "border-aurora-cyan/40 bg-aurora-cyan/10 text-aurora-cyan shadow-[0_0_20px_rgba(34,211,238,0.2)]"
              : "border-aurora-border bg-aurora-surface text-aurora-fg-muted hover:border-white/15 hover:bg-white/8",
          )}
        >
          <span className="flex items-center gap-2">
            <Terminal className="size-4 opacity-80" />
            <span>Developer Mode</span>
          </span>
          <span
            className={`relative h-5 w-9 rounded-full transition-colors ${devMode ? "bg-cyan-500/50" : "bg-white/15"}`}
            aria-hidden
          >
            <span
              className={`absolute top-0.5 size-4 rounded-full bg-white shadow transition-transform ${devMode ? "left-4" : "left-0.5"}`}
            />
          </span>
        </button>
      </div>
    </aside>
  );
}
