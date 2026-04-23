/* CPU sparkline updates from metrics; intentional effect sync. */
/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useState } from "react";
import { MetricRow } from "../common/MetricRow";
import type { Metrics } from "../../types/ui";

type SideRailProps = {
  metrics: Metrics | null;
  brandInitial: string;
  fileEntryCount: number | null;
};

const NAV_ITEMS = ["Home", "Chat", "Memory", "Files", "Tools", "Search", "Settings"] as const;
const ICONS = ["⌂", "◈", "◍", "⌘", "⚙", "⌕", "⋯"];

export function SideRail({ metrics, brandInitial, fileEntryCount }: SideRailProps) {
  const [devMode, setDevMode] = useState(false);
  const [cpuSpark, setCpuSpark] = useState<number[]>([]);

  useEffect(() => {
    if (metrics == null) return;
    setCpuSpark((prev) => [...prev, metrics.cpu_percent].slice(-40));
  }, [metrics]);

  const sparkPath =
    cpuSpark.length < 2
      ? ""
      : cpuSpark
          .map((v, i) => {
            const x = (i / (cpuSpark.length - 1)) * 100;
            const y = 100 - Math.max(0, Math.min(100, v));
            return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
          })
          .join(" ");

  const statRows = [
    { key: "CPU", kind: "cpu" as const, value: metrics ? `${metrics.cpu_percent.toFixed(0)}%` : "--", pct: metrics?.cpu_percent ?? 0 },
    { key: "RAM", kind: "ram" as const, value: metrics ? `${metrics.memory_percent.toFixed(0)}%` : "--", pct: metrics?.memory_percent ?? 0 },
    { key: "GPU", kind: "gpu" as const, value: metrics?.gpu_percent != null ? `${metrics.gpu_percent.toFixed(0)}%` : "--", pct: metrics?.gpu_percent ?? 0 },
    { key: "NPU", kind: "npu" as const, value: metrics?.npu_percent != null ? `${metrics.npu_percent.toFixed(0)}%` : "--", pct: metrics?.npu_percent ?? 0 },
  ];

  return (
    <aside className={`rail ${devMode ? "rail--dev" : ""}`}>
      <div className="rail-avatar" aria-label="Aurora" title="Aurora">
        {brandInitial}
      </div>
      <nav className="rail-menu">
        {NAV_ITEMS.map((item, index) => (
          <button key={item} type="button" className={`rail-btn ${index === 0 ? "active" : ""}`}>
            <span className="rail-btn__ic">{ICONS[index]}</span>
            <span className="rail-btn__tx">
              {item}
              {item === "Files" && fileEntryCount != null ? (
                <span className="rail-btn__meta"> {fileEntryCount}</span>
              ) : null}
            </span>
          </button>
        ))}
      </nav>
      <section className="system-card">
        <h4>System Status</h4>
        <div className="system-spark" aria-hidden>
          {sparkPath ? (
            <svg className="system-spark__svg" viewBox="0 0 100 100" preserveAspectRatio="none">
              <path className="system-spark__path" d={sparkPath} fill="none" />
            </svg>
          ) : (
            <div className="system-spark__empty" />
          )}
        </div>
        {statRows.map((row) => (
          <div key={row.key} className="system-stat">
            <MetricRow label={row.key} value={row.value} />
            <div className={`stat-bar stat-bar--${row.kind}`}>
              <i style={{ width: `${Math.max(6, Math.min(100, row.pct))}%` }} />
            </div>
          </div>
        ))}
      </section>
      <div className="rail-dev">
        <span className="rail-dev__ic" aria-hidden>
          &gt;_
        </span>
        <span className="rail-dev__tx">Developer Mode</span>
        <button
          type="button"
          className={devMode ? "rail-toggle rail-toggle--on" : "rail-toggle"}
          role="switch"
          aria-checked={devMode}
          onClick={() => setDevMode((d) => !d)}
        />
      </div>
    </aside>
  );
}
