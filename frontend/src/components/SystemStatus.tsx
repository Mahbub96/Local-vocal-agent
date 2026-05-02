/* CPU sparkline history updates when polled metrics change; mirrors prior SideRail behavior. */
/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useState } from "react";
import type { Metrics } from "../types/ui";

type SystemStatusProps = {
  metrics: Metrics | null;
};

export function SystemStatus({ metrics }: SystemStatusProps) {
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

  const rows = [
    {
      key: "CPU",
      kind: "cpu" as const,
      value: metrics ? `${metrics.cpu_percent.toFixed(0)}%` : "—",
      pct: metrics?.cpu_percent ?? 0,
    },
    {
      key: "RAM",
      kind: "ram" as const,
      value: metrics ? `${metrics.memory_percent.toFixed(0)}%` : "—",
      pct: metrics?.memory_percent ?? 0,
    },
    {
      key: "GPU",
      kind: "gpu" as const,
      value: metrics?.gpu_percent != null ? `${metrics.gpu_percent.toFixed(0)}%` : "—",
      pct: metrics?.gpu_percent ?? 0,
    },
    {
      key: "NPU",
      kind: "npu" as const,
      value: metrics?.npu_percent != null ? `${metrics.npu_percent.toFixed(0)}%` : "—",
      pct: metrics?.npu_percent ?? 0,
    },
  ];

  const barFill =
    "h-full rounded-full bg-linear-to-r from-[#00d2ff] to-[#9d50bb] shadow-[0_0_14px_rgba(0,210,255,0.35),0_0_18px_rgba(157,80,187,0.25)]";

  return (
    <section
      className="rounded-aurora-2xl border border-aurora-border bg-aurora-surface p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
      aria-label="System status"
    >
      <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-aurora-fg-muted">
        System Status
      </h4>
      <div className="mb-3 h-10 overflow-hidden rounded-aurora-md border border-aurora-divider bg-black/35">
        {sparkPath ? (
          <svg className="h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
            <defs>
              <linearGradient id="aurora-spark" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#00d2ff" />
                <stop offset="100%" stopColor="#9d50bb" />
              </linearGradient>
            </defs>
            <path
              d={sparkPath}
              fill="none"
              stroke="url(#aurora-spark)"
              strokeWidth={2.5}
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        ) : (
          <div className="h-full w-full bg-linear-to-r from-aurora-cyan/8 to-aurora-purple/8" />
        )}
      </div>
      <ul className="space-y-2.5">
        {rows.map((row) => (
          <li key={row.key} className="flex items-center gap-2 text-xs">
            <span className="w-8 shrink-0 text-aurora-fg-muted">{row.key}</span>
            <div className="relative h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-white/6">
              <div
                className={`${barFill} transition-[width] duration-500`}
                style={{ width: `${Math.max(6, Math.min(100, row.pct))}%` }}
              />
            </div>
            <span className="w-9 shrink-0 text-right tabular-nums text-aurora-fg/80">{row.value}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
