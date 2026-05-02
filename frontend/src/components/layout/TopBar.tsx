import { useEffect, useState } from "react";
import { Menu, Moon, Sun } from "lucide-react";
import { WaveformIcon } from "../common/WaveformIcon";
import { IconButton } from "../ui/IconButton";
import { cn } from "../../lib/cn";

type TopBarProps = {
  onThemeToggle?: (isLight: boolean) => void;
  userInitial: string;
  onMenuClick?: () => void;
};

export function TopBar({ onThemeToggle, userInitial, onMenuClick }: TopBarProps) {
  const [isLight, setIsLight] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.auroraTheme = isLight ? "light" : "dark";
  }, [isLight]);

  return (
    <div
      className={cn(
        "aurora-topbar relative flex h-aurora-topbar shrink-0 items-center gap-2 px-3 sm:px-4 md:px-5",
      )}
      role="banner"
    >
      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        <div
          className="hidden items-center gap-1.5 pl-0.5 sm:flex"
          aria-hidden
        >
          <span className="size-2.5 rounded-full bg-[#ff5f57] shadow-[0_0_8px_rgba(255,95,87,0.65)]" />
          <span className="size-2.5 rounded-full bg-[#febc2e] shadow-[0_0_8px_rgba(254,188,46,0.55)]" />
          <span className="size-2.5 rounded-full bg-[#28c840] shadow-[0_0_8px_rgba(40,200,64,0.55)]" />
        </div>
        {onMenuClick ? (
          <IconButton className="xl:hidden" aria-label="Open navigation menu" onClick={onMenuClick}>
            <Menu className="size-[18px]" strokeWidth={1.75} />
          </IconButton>
        ) : (
          <span className="size-10 shrink-0 xl:hidden" aria-hidden />
        )}
      </div>

      <div className="flex min-w-0 flex-1 justify-center xl:absolute xl:left-1/2 xl:-translate-x-1/2">
        <div
          className="flex max-w-[min(100%,20rem)] items-center gap-2 sm:gap-2.5 md:max-w-none"
          aria-label="Aurora AI Assistant"
        >
          <span className="truncate text-[10px] font-semibold uppercase tracking-[0.2em] text-white sm:text-[11px] md:text-xs md:tracking-[0.28em]">
            <span className="sm:hidden">AURORA</span>
            <span className="hidden sm:inline">AURORA AI ASSISTANT</span>
          </span>
          <WaveformIcon className="hidden h-3 w-10 shrink-0 text-aurora-cyan/90 sm:block sm:w-12" />
        </div>
      </div>
      <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2 md:gap-3">
        <IconButton
          variant="amber"
          aria-pressed={isLight}
          aria-label={isLight ? "Switch to dark" : "Switch to light"}
          onClick={() => {
            setIsLight((l) => {
              const n = !l;
              onThemeToggle?.(n);
              return n;
            });
          }}
        >
          {isLight ? <Moon className="size-[18px]" strokeWidth={1.75} /> : <Sun className="size-[18px]" strokeWidth={1.75} />}
        </IconButton>
        <div
          className="grid size-10 place-items-center rounded-full bg-linear-to-br from-aurora-purple/45 to-aurora-cyan/35 text-sm font-semibold text-aurora-fg shadow-[0_0_28px_rgba(157,80,187,0.4)] ring-2 ring-white/15"
          role="img"
          aria-label="User profile"
        >
          {userInitial}
        </div>
      </div>
    </div>
  );
}
