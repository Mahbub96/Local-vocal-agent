import { useMemo } from "react";

export type LevelBar = { h: number; on: boolean };

/** Derive animated bar heights from a 0–100 level (any audio/VU source). */
export function useLevelBars(count: number, level: number, seed: number): LevelBar[] {
  return useMemo(() => {
    const lv = level / 100;
    return Array.from({ length: count }, (_, i) => {
      const wave = Math.sin((i * 0.9 + seed * 1.7) * 0.85) * 0.5 + 0.5;
      const h = 5 + Math.round(8 + wave * 20 * (0.35 + lv * 0.75));
      const on = i < Math.max(0, Math.round(lv * count) - 0.01);
      return { h, on };
    });
  }, [count, level, seed]);
}
