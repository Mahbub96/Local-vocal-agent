import { useMemo } from "react";

export const VOICE_LANG_OPTIONS = ["বাংলা (Bangla)", "English", "Default"] as const;

export function useVoiceLanguageOptions(current: string) {
  return useMemo(() => {
    const c = (current || "Default").trim() || "Default";
    const rest = VOICE_LANG_OPTIONS.filter((x) => x !== c);
    return [c, ...rest];
  }, [current]);
}
