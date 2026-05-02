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
      available: metrics != null,
    },
    {
      key: "RAM",
      kind: "ram" as const,
      value: metrics ? `${metrics.memory_percent.toFixed(0)}%` : "—",
      pct: metrics?.memory_percent ?? 0,
      available: metrics != null,
    },
    {
      key: "GPU",
      kind: "gpu" as const,
      value: metrics?.gpu_percent != null ? `${metrics.gpu_percent.toFixed(0)}%` : "—",
      pct: metrics?.gpu_percent ?? 0,
      available: metrics?.gpu_percent != null,
    },
    {
      key: "NPU",
      kind: "npu" as const,
      value: metrics?.npu_percent != null ? `${metrics.npu_percent.toFixed(0)}%` : "—",
      pct: metrics?.npu_percent ?? 0,
      available: metrics?.npu_percent != null,
    },
  ];

  const barFill =
    "h-full rounded-full bg-linear-to-r from-aurora-cyan to-aurora-purple shadow-[0_0_14px_rgba(0,210,255,0.35),0_0_18px_rgba(157,80,187,0.25)]";

  return (
    <section
      className="aurora-glass rounded-aurora-2xl border border-white/12 bg-[linear-gradient(180deg,rgba(18,24,40,0.94),rgba(10,14,26,0.94))] p-3.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_0_18px_rgba(0,0,0,0.35)] md:p-4"
      aria-label="System status"
    >
      <h4 className="mb-2.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-white/70">
        System Status
      </h4>
      <div className="mb-3 h-10 overflow-hidden rounded-aurora-lg border border-white/8 bg-aurora-rail shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
        {sparkPath ? (
          <svg className="h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
            <defs>
              <linearGradient id="aurora-spark" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="var(--color-aurora-cyan)" />
                <stop offset="100%" stopColor="var(--color-aurora-purple)" />
              </linearGradient>
            </defs>
            <path
              d={sparkPath}
              fill="none"
              stroke="url(#aurora-spark)"
              strokeWidth={2.2}
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        ) : (
          <div className="h-full w-full bg-linear-to-r from-aurora-cyan/12 to-aurora-purple/12" />
        )}
      </div>
      <ul className="space-y-2">
        {rows.map((row) => (
          <li key={row.key} className="flex items-center gap-2 text-xs">
            <span className="w-8 shrink-0 text-xs tracking-[0.04em] text-white/80">{row.key}</span>
            <div className="relative h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-white/7">
              <div className="absolute inset-y-0 left-0 w-2 rounded-full bg-white/7" />
              {row.available ? (
                <div
                  className={`${barFill} transition-[width] duration-500`}
                  style={{ width: `${Math.max(4, Math.min(100, row.pct))}%` }}
                />
              ) : (
                <div className="absolute left-0 top-1/2 size-2 -translate-y-1/2 rounded-full bg-aurora-purple/80 shadow-[0_0_10px_rgba(157,80,187,0.35)]" />
              )}
            </div>
            <span className="w-10 shrink-0 text-right text-xs tabular-nums text-white/90">{row.value}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
