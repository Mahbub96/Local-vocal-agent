import { useEffect, useState } from "react";
import { WaveformIcon } from "../common/WaveformIcon";

type TopBarProps = {
  onThemeToggle?: (isLight: boolean) => void;
  userInitial: string;
};

export function TopBar({ onThemeToggle, userInitial }: TopBarProps) {
  const [isLight, setIsLight] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.auroraTheme = isLight ? "light" : "dark";
  }, [isLight]);

  return (
    <header className="topbar">
      <div className="topbar-spacer" aria-hidden />
      <div className="topbar-brand" aria-label="Aurora AI Assistant">
        <div className="topbar-brand__stack">
          <div className="topbar-brand__titleline">
            <span className="topbar-brand__em">AURORA</span>
            <WaveformIcon className="topbar-brand__wave" />
          </div>
          <span className="topbar-brand__sub">AI ASSISTANT</span>
        </div>
      </div>
      <div className="topbar-actions">
        <button
          type="button"
          className="topbar-icon-btn"
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
          {isLight ? "☀" : "☽"}
        </button>
        <div className="top-avatar" role="img" aria-label="User profile">
          {userInitial}
        </div>
      </div>
    </header>
  );
}
