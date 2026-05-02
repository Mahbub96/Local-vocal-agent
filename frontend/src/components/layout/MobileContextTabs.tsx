import { useState } from "react";
import type { Profile, ThinkingStep, ToolActivity } from "../../types/ui";
import { MemoryPanel } from "../MemoryPanel";
import { ThinkingPanel } from "../ThinkingPanel";
import { ToolsPanel } from "../ToolsPanel";

type MobileContextTabsProps = {
  thinking: ThinkingStep[];
  profile: Profile | null;
  onSaveProfile: (next: Profile) => Promise<void>;
  activities: ToolActivity[];
};

const TABS = [
  { id: "think" as const, label: "Thinking" },
  { id: "memory" as const, label: "Memory" },
  { id: "tools" as const, label: "Tools" },
];

export function MobileContextTabs({
  thinking,
  profile,
  onSaveProfile,
  activities,
}: MobileContextTabsProps) {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("think");

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden lg:hidden">
      <div
        className="flex shrink-0 gap-1 rounded-2xl border border-white/10 bg-black/30 p-1"
        role="tablist"
        aria-label="Context panels"
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`min-h-11 flex-1 rounded-xl px-2 py-2 text-center text-xs font-medium transition sm:text-sm ${
              tab === t.id
                ? "bg-white/10 text-white shadow-[0_0_16px_rgba(59,130,246,0.2)]"
                : "text-white/50 hover:bg-white/4 hover:text-white/80"
            }`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="mt-3 min-h-0 flex-1 overflow-y-auto overflow-x-hidden" role="tabpanel">
        {tab === "think" ? <ThinkingPanel thinking={thinking} /> : null}
        {tab === "memory" ? <MemoryPanel profile={profile} onSave={onSaveProfile} /> : null}
        {tab === "tools" ? <ToolsPanel activities={activities} /> : null}
      </div>
    </div>
  );
}
