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
import { NAV_ITEMS } from "./layout/navConfig";

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
  /** Close the mobile drawer (shown only below `xl`). */
  onRequestClose?: () => void;
  className?: string;
};

export function Sidebar({
  metrics,
  fileEntryCount,
  onRequestClose,
  className,
}: SidebarProps) {
  const [devMode, setDevMode] = useState(false);

  return (
    <aside
      className={cn(
        "flex min-h-0 w-full min-w-0 shrink-0 flex-col overflow-y-auto border-aurora-border bg-aurora-rail/95 py-3 pl-3 pr-2 backdrop-blur-xl xl:h-full xl:w-aurora-rail",
        className,
        devMode && "ring-1 ring-aurora-cyan/30",
      )}
    >
      <div className="mb-5 flex items-start justify-between gap-2 px-2 sm:mb-6">
        <div
          className="relative size-14 shrink-0 rounded-full bg-linear-to-br from-cyan-400/45 via-aurora-cyan/35 to-aurora-purple/55 shadow-[0_0_36px_rgba(0,210,255,0.5),0_0_48px_rgba(157,80,187,0.4)] ring-1 ring-white/20"
          aria-hidden
        >
          <span className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_32%_22%,rgba(255,255,255,0.45),transparent_58%)]" />
          <span className="absolute inset-[22%] rounded-full bg-[radial-gradient(ellipse_at_40%_35%,rgba(0,210,255,0.25),transparent_55%),#060912]" />
        </div>
        {onRequestClose ? (
          <button
            type="button"
            className="aurora-icon-btn-sm xl:hidden"
            aria-label="Close navigation"
            onClick={onRequestClose}
          >
            <X className="size-[18px]" strokeWidth={1.75} />
          </button>
        ) : null}
      </div>

      <nav
        className="flex flex-1 flex-col gap-0.5 px-1"
        aria-label="Main navigation"
      >
        {NAV_ITEMS.map((item, index) => {
          const Icon = NAV_ICONS[item];
          const active = index === 0;
          return (
            <button
              key={item}
              type="button"
              className={cn(
                "group flex w-full items-center gap-3 aurora-nav-item",
                active && "aurora-nav-item-active",
              )}
            >
              <Icon
                className={cn(
                  "size-[18px] shrink-0 stroke-[1.75]",
                  active ? "text-aurora-nav-icon-active" : "text-aurora-nav-icon group-hover:text-aurora-nav-icon-hover",
                )}
              />
              <span className="font-medium">
                {item}
                {item === "Files" && fileEntryCount != null ? (
                  <span className="ml-1 text-xs font-normal text-aurora-fg-subtle">
                    {" "}
                    {fileEntryCount}
                  </span>
                ) : null}
              </span>
            </button>
          );
        })}
      </nav>

      <div className="mt-4 flex min-h-0 flex-1 flex-col justify-end gap-3">
        <SystemStatus metrics={metrics} />
        <button
          type="button"
          onClick={() => setDevMode((d) => !d)}
          aria-pressed={devMode}
          className={cn(
            "flex items-center justify-between gap-2 rounded-aurora-xl border px-3 py-2.5 text-left text-xs font-medium transition-all",
            devMode
              ? "border-aurora-cyan/40 bg-aurora-cyan/10 text-aurora-cyan shadow-[0_0_20px_rgba(34,211,238,0.2)]"
              : "border-aurora-border bg-aurora-surface text-aurora-fg-muted hover:border-aurora-border-strong hover:bg-aurora-surface-hover",
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
