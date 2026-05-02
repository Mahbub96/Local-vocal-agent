export function titleFromVoiceState(state: string | undefined): string {
  const s = state?.toLowerCase() ?? "idle";
  if (s === "listening") return "Listening…";
  if (s === "transcribing") return "Transcribing…";
  if (s === "speaking") return "Speaking…";
  if (s === "idle" || s === "ready") return "Ready";
  return state ? state.charAt(0).toUpperCase() + state.slice(1) : "Ready";
}

export function shortVoiceStateLabel(state: string | undefined): string {
  const s = state?.toLowerCase() ?? "idle";
  if (s === "idle") return "Idle";
  if (s === "ready") return "Ready";
  if (s === "listening") return "Listening";
  if (s === "transcribing") return "Transcribing";
  if (s === "speaking") return "Speaking";
  return state ? state.charAt(0).toUpperCase() + state.slice(1) : "Idle";
}
