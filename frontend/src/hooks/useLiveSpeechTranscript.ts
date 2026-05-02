import { startTransition, useEffect, useMemo, useRef, useState } from "react";

/** Map profile language pill → `SpeechRecognition.lang` (best-effort). */
export function speechRecognitionLang(languageLabel: string): string {
  const raw = languageLabel.trim();
  if (!raw || raw.toLowerCase() === "default") {
    return typeof navigator !== "undefined" && navigator.language ? navigator.language : "en-US";
  }
  const l = raw.toLowerCase();
  if (l.includes("bangla") || raw.includes("বাংলা")) return "bn-BD";
  if (l.includes("english")) return "en-US";
  return "en-US";
}

function getSpeechRecognitionCtor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

/**
 * Live captioning while `active` (typically while mic is recording) via Web Speech API.
 * Interim + final results; no network round-trip. Falls back silently if unsupported.
 */
export function useLiveSpeechTranscript(active: boolean, languageLabel: string) {
  const [finalText, setFinalText] = useState("");
  const [interimText, setInterimText] = useState("");
  const activeRef = useRef(active);
  useEffect(() => {
    activeRef.current = active;
  }, [active]);

  const lang = useMemo(() => speechRecognitionLang(languageLabel), [languageLabel]);

  const displayText = useMemo(() => {
    const f = finalText.trim();
    const i = interimText.trim();
    if (!f && !i) return "";
    if (!i) return f;
    if (!f) return i;
    return `${f} ${i}`.trim();
  }, [finalText, interimText]);

  useEffect(() => {
    if (!active) {
      startTransition(() => {
        setFinalText("");
        setInterimText("");
      });
    }
  }, [active]);

  useEffect(() => {
    if (!active) return;

    startTransition(() => {
      setFinalText("");
      setInterimText("");
    });

    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return;

    let rec: SpeechRecognition | null = null;
    let accumulated = "";
    let disposed = false;

    const startFresh = () => {
      if (!activeRef.current || disposed) return;
      try {
        rec = new Ctor();
        rec.continuous = true;
        rec.interimResults = true;
        rec.lang = lang;

        rec.onresult = (event: SpeechRecognitionEvent) => {
          let interim = "";
          let chunk = "";
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const r = event.results[i];
            const t = r[0]?.transcript ?? "";
            if (r.isFinal) chunk += t;
            else interim += t;
          }
          if (chunk) {
            accumulated = `${accumulated} ${chunk}`.trim();
            setFinalText(accumulated);
          }
          setInterimText(interim.trim());
        };

        rec.onerror = () => {
          /* noisy in some browsers; live caption is best-effort */
        };

        rec.onend = () => {
          if (disposed || !activeRef.current || !rec) return;
          try {
            rec.start();
          } catch {
            /* already running */
          }
        };

        rec.start();
      } catch {
        /* ignore */
      }
    };

    startFresh();

    return () => {
      disposed = true;
      activeRef.current = false;
      if (rec) {
        rec.onresult = null;
        rec.onerror = null;
        rec.onend = null;
        try {
          rec.abort();
        } catch {
          try {
            rec.stop();
          } catch {
            /* ignore */
          }
        }
      }
      rec = null;
      startTransition(() => setInterimText(""));
    };
  }, [active, lang]);

  const supported = typeof window !== "undefined" && getSpeechRecognitionCtor() !== null;

  return { displayText, supported };
}
