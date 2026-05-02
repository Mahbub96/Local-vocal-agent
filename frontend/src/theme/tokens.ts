/**
 * Read-only JS mirror of `aurora.theme.css` for rare programmatic use
 * (canvas export, tests, third-party widgets). Prefer Tailwind classes in UI.
 */
export const auroraTheme = {
  canvas: "#05070a",
  rail: "#070a12",
  fg: "#f8fafc",
  fgMuted: "rgb(148 163 184)",
  border: "rgb(255 255 255 / 0.1)",
  cyan: "#22d3ee",
  blue: "#3b82f6",
  purple: "#a855f7",
  emerald: "#34d399",
  voiceCaption: "#9ca3af",
  voiceLive: "#22c55e",
  voiceOutputDot: "#38bdf8",
  railWidth: 250,
  contextWidth: 300,
} as const;

export type AuroraTheme = typeof auroraTheme;
