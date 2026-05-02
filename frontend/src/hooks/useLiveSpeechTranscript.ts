import type { MutableRefObject } from "react";
import { startTransition, useEffect, useMemo, useRef, useState } from "react";

function joinDisplay(finalChunk: string, interimChunk: string): string {
  const f = finalChunk.trim();
  const i = interimChunk.trim();
  if (!f && !i) return "";
  if (!i) return f;
  if (!f) return i;
  return `${f} ${i}`.trim();
}

/** Ordered `SpeechRecognition.lang` codes to try (Bangla: Chromium often accepts bn-IN where bn-BD fails). */
export function speechRecognitionLangCandidates(languageLabel: string): readonly string[] {
  const raw = languageLabel.trim();
  const l = raw.toLowerCase();
  if (!raw || l === "default") {
    const nav =
      typeof navigator !== "undefined" && navigator.language ? navigator.language : "en-US";
    return [nav];
  }
  const isBangla =
    l.includes("bangla") || raw.includes("বাংলা") || l.includes("bengali");
  if (isBangla) {
    return ["bn-IN", "bn-BD", "bn", "en-US"];
  }
  if (l.includes("english")) return ["en-US"];
  return ["en-US"];
}

/** Map profile language pill → primary `SpeechRecognition.lang` (best-effort). */
export function speechRecognitionLang(languageLabel: string): string {
  return speechRecognitionLangCandidates(languageLabel)[0] ?? "en-US";
}

function getSpeechRecognitionCtor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null;
}

/**
 * Live captioning while `active` (typically while mic is recording) via Web Speech API.
 * Interim + final results; no network round-trip. Falls back silently if unsupported.
 * `utteranceSeq` increments when a VAD/push segment ends — clears accumulated text so only the current clip shows.
 */
export function useLiveSpeechTranscript(
  active: boolean,
  languageLabel: string,
  utteranceSeq = 0,
  /** Optional: same text as `displayText`, for parents that need a sync read (e.g. voice segment snapshot). */
  mirrorRef?: MutableRefObject<string>,
) {
  const [finalText, setFinalText] = useState("");
  const [interimText, setInterimText] = useState("");
  const accumulatedRef = useRef("");
  /** Same as `displayText`, updated synchronously in `onresult` so voice upload can snapshot at segment end. */
  const displayTextRef = useRef("");
  const activeRef = useRef(active);
  useEffect(() => {
    activeRef.current = active;
  }, [active]);

  const langCandidates = useMemo(
    () => speechRecognitionLangCandidates(languageLabel),
    [languageLabel],
  );

  useEffect(() => {
    accumulatedRef.current = "";
    displayTextRef.current = "";
    if (mirrorRef) mirrorRef.current = "";
    startTransition(() => {
      setFinalText("");
      setInterimText("");
    });
  }, [utteranceSeq, mirrorRef]);

  const displayText = useMemo(
    () => joinDisplay(finalText, interimText),
    [finalText, interimText],
  );

  useEffect(() => {
    if (!active) {
      displayTextRef.current = "";
      if (mirrorRef) mirrorRef.current = "";
      startTransition(() => {
        setFinalText("");
        setInterimText("");
      });
    }
  }, [active, mirrorRef]);

  useEffect(() => {
    if (!active) return;

    displayTextRef.current = "";
    if (mirrorRef) mirrorRef.current = "";
    startTransition(() => {
      setFinalText("");
      setInterimText("");
    });

    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return;

    let rec: SpeechRecognition | null = null;
    let disposed = false;
    let attemptSeq = 0;
    let heardAnyToken = false;
    let noTokenTimer: number | null = null;

    const tearDownRec = () => {
      if (noTokenTimer != null) {
        window.clearTimeout(noTokenTimer);
        noTokenTimer = null;
      }
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
    };

    const startAt = (index: number) => {
      if (disposed || !activeRef.current || index >= langCandidates.length) return;
      const langCode = langCandidates[index]!;
      const localAttempt = ++attemptSeq;
      heardAnyToken = false;

      tearDownRec();

      try {
        const r = new Ctor();
        rec = r;
        r.continuous = true;
        r.interimResults = true;
        r.lang = langCode;

        r.onresult = (event: SpeechRecognitionEvent) => {
          let interim = "";
          let chunk = "";
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const result = event.results[i];
            const t = result[0]?.transcript ?? "";
            if (result.isFinal) chunk += t;
            else interim += t;
          }
          if (chunk) {
            heardAnyToken = true;
            accumulatedRef.current = `${accumulatedRef.current} ${chunk}`.trim();
            setFinalText(accumulatedRef.current);
          }
          if (interim.trim()) heardAnyToken = true;
          const interimTrim = interim.trim();
          setInterimText(interimTrim);
          const d = joinDisplay(accumulatedRef.current, interimTrim);
          displayTextRef.current = d;
          if (mirrorRef) mirrorRef.current = d;
        };

        r.onerror = (ev: Event) => {
          const code = (ev as SpeechRecognitionErrorEvent).error;
          if (
            code === "language-not-supported" ||
            (code === "network" && index < langCandidates.length - 1)
          ) {
            tearDownRec();
            startAt(index + 1);
            return;
          }
        };

        r.onend = () => {
          if (disposed || !activeRef.current) return;
          try {
            r.start();
          } catch {
            /* already running or invalid state */
          }
        };

        r.start();
        // Some browsers accept Bangla lang code but never emit tokens.
        // Auto-fallback to next candidate if nothing is heard shortly.
        noTokenTimer = window.setTimeout(() => {
          if (disposed || !activeRef.current) return;
          if (localAttempt !== attemptSeq) return;
          if (heardAnyToken) return;
          if (index + 1 >= langCandidates.length) return;
          tearDownRec();
          startAt(index + 1);
        }, 2500);
      } catch {
        if (index + 1 < langCandidates.length) {
          startAt(index + 1);
        }
      }
    };

    startAt(0);

    return () => {
      disposed = true;
      activeRef.current = false;
      tearDownRec();
      startTransition(() => setInterimText(""));
    };
  }, [active, langCandidates, utteranceSeq, mirrorRef]);

  const supported = typeof window !== "undefined" && getSpeechRecognitionCtor() !== null;

  return { displayText, displayTextRef, supported };
}
