import type { MutableRefObject } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

const AUDIO_CONSTRAINTS: MediaTrackConstraints = {
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
};

function hasGetUserMedia(): boolean {
  return typeof navigator !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);
}

/** Browsers omit `mediaDevices` on insecure pages (e.g. http:// + LAN IP). */
function describeMicUnavailable(): string {
  if (typeof window === "undefined") return "Microphone not available.";
  if (!window.isSecureContext) {
    const port = window.location.port || "5173";
    const host = window.location.hostname || "localhost";
    return (
      "Microphone is blocked: you opened a non-secure URL (usually http:// plus a Wi‑Fi/LAN address). " +
      `On this computer use http://localhost:${port}. From a phone, use https://${host}:${port} (not http://) when the dev server runs with HTTPS — see start.sh (FRONTEND_HTTPS defaults to 1) and accept the browser’s certificate warning once.`
    );
  }
  return "Microphone not available. Allow microphone permission for this site or try another browser.";
}

function formatGetUserMediaError(e: unknown): string {
  const name = e instanceof DOMException ? e.name : "";
  const msg = e instanceof Error ? e.message : String(e);
  if (name === "NotAllowedError" || /not allowed|permission/i.test(msg)) {
    return "Microphone permission denied. Allow the mic for this site in the browser address bar or site settings.";
  }
  return msg;
}

/** ~RMS on time-domain buffer (same scale as waveform meter). */
function rmsFromAnalyser(analyser: AnalyserNode): number {
  const buf = new Uint8Array(analyser.fftSize);
  analyser.getByteTimeDomainData(buf);
  let z = 0;
  for (let i = 0; i < buf.length; i++) {
    const x = (buf[i]! - 128) / 128;
    z += x * x;
  }
  return Math.sqrt(z / buf.length);
}

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) return "audio/webm;codecs=opus";
  if (MediaRecorder.isTypeSupported("audio/webm")) return "audio/webm";
  return undefined;
}

function stopMeter(
  rafRef: MutableRefObject<number>,
  audioCtxRef: MutableRefObject<AudioContext | null>,
  analyserRef: MutableRefObject<AnalyserNode | null>,
  setMicLevel: (n: number) => void,
) {
  cancelAnimationFrame(rafRef.current);
  rafRef.current = 0;
  analyserRef.current = null;
  void audioCtxRef.current?.close().catch(() => undefined);
  audioCtxRef.current = null;
  setMicLevel(0);
}

function releaseAllHardware(
  rafRef: MutableRefObject<number>,
  audioCtxRef: MutableRefObject<AudioContext | null>,
  analyserRef: MutableRefObject<AnalyserNode | null>,
  streamRef: MutableRefObject<MediaStream | null>,
  recRef: MutableRefObject<MediaRecorder | null>,
  chunksRef: MutableRefObject<BlobPart[]>,
) {
  cancelAnimationFrame(rafRef.current);
  rafRef.current = 0;
  analyserRef.current = null;
  void audioCtxRef.current?.close().catch(() => undefined);
  audioCtxRef.current = null;

  const mr = recRef.current;
  if (mr && mr.state !== "inactive") {
    try {
      mr.stop();
    } catch {
      /* ignore */
    }
  }
  recRef.current = null;
  chunksRef.current = [];

  streamRef.current?.getTracks().forEach((t) => t.stop());
  streamRef.current = null;
}

export type VoiceCaptureMode = "push" | "always";

type UseVoiceCaptureOptions = {
  mode: VoiceCaptureMode;
  /** Upload + model work — pause auto finalization (segment keeps recording until silence after busy). */
  busy: boolean;
  /** Snapshot live caption when the audio segment closes (before upload); avoids stale React state. */
  getTranscriptHint?: () => string;
  onUtterance: (blob: Blob, transcriptHint: string) => void | Promise<void>;
  /** User speaks over assistant TTS — stop playback (only after sustained loud input; see barge-in logic). */
  onBargeIn?: () => void;
  /** While assistant TTS is playing — ignore mic barge-in so small sounds do not cut off speech. */
  suppressBargeIn?: boolean;
};

/** Silence after speech to end one utterance (ms). Lower = faster turn-taking (more false cuts). */
const SILENCE_END_MS = 720;
/** Ignore very short noise bursts. */
const MIN_UTTERANCE_MS = 420;
/** If RMS stays modestly above noise this long (ms), count as speech (quiet talkers). */
const SOFT_SPEECH_MS = 160;
/** Absolute barge-in floor (also scaled vs adaptive noise floor below). */
const BARGE_RMS_MIN = 0.045;
/** Loud energy must stay above threshold this long (ms) to count as intentional interrupt. */
const BARGE_HOLD_MS = 280;
const MAX_SEGMENT_MS = 45_000;
/**
 * Hands-free: if VAD never sees speech, stop the segment after this long instead of waiting
 * for MAX_SEGMENT_MS. Long “silent” recordings still encode a large blob and can pass the
 * size gate → STT hallucinates garbage in random languages.
 */
const MAX_SILENCE_ABORT_MS = 15_000;
/** EMA alpha for always-listen RMS (reduces flutter that resets silence). */
const RMS_SMOOTH = 0.2;

/**
 * Adaptive VAD: thresholds are **relative to a running noise floor** + optional **drop from speech peak**.
 * Fixed RMS fails when room tone sits above a low “silence” line — the segment never ends.
 */
const MIN_NOISE_FLOOR = 0.004;
const MAX_NOISE_FLOOR = 0.042;
/** “Quiet” vs estimated noise floor — starts end-of-utterance timer. */
const SILENCE_ABOVE_FLOOR = 0.0045;
/** First sign of speech (above ambient). */
const VOICE_ON_ABOVE_FLOOR = 0.0045;
/** Strong speech — resets silence timer. */
const STRONG_ABOVE_FLOOR = 0.016;
/** Resume talking after a pause (soft continuation). */
const RESUME_ABOVE_FLOOR = 0.012;
/** If peak was this far above floor, also end when energy falls to `PEAK_FRACTION_END` of peak. */
const PEAK_MIN_OVER_FLOOR = 0.012;
const PEAK_FRACTION_END = 0.38;

/**
 * Single mic pipeline: **push** (tap mic to record/send) or **always** (hands-free; auto-send after pause).
 * One `MediaStream` at a time; echo cancellation enabled for duplex-style use.
 */
export function useVoiceCapture({
  mode,
  busy,
  onUtterance,
  getTranscriptHint,
  onBargeIn,
  suppressBargeIn = false,
}: UseVoiceCaptureOptions) {
  const [isHot, setIsHot] = useState(false);
  /** True once real speech is detected in the current hands-free segment (prevents “always listening” UI while idle noise). */
  const [segmentSpeechDetected, setSegmentSpeechDetected] = useState(false);
  /** Bumps when a voice segment is finalized (hands-free clip or push send) — reset live speech caption. */
  const [utteranceSeq, setUtteranceSeq] = useState(0);
  const [micLevel, setMicLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const rafRef = useRef(0);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mountedRef = useRef(true);
  const modeRef = useRef(mode);
  const busyRef = useRef(busy);
  const onUtteranceRef = useRef(onUtterance);
  const getTranscriptHintRef = useRef(getTranscriptHint);
  const onBargeInRef = useRef(onBargeIn);
  const suppressBargeInRef = useRef(suppressBargeIn);
  const alwaysLoopCancelRef = useRef<(() => void) | null>(null);
  const isHotRef = useRef(false);

  useEffect(() => {
    isHotRef.current = isHot;
  }, [isHot]);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);
  useEffect(() => {
    busyRef.current = busy;
  }, [busy]);
  useEffect(() => {
    onUtteranceRef.current = onUtterance;
  }, [onUtterance]);
  useEffect(() => {
    getTranscriptHintRef.current = getTranscriptHint;
  }, [getTranscriptHint]);
  useEffect(() => {
    onBargeInRef.current = onBargeIn;
  }, [onBargeIn]);
  useEffect(() => {
    suppressBargeInRef.current = suppressBargeIn;
  }, [suppressBargeIn]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      alwaysLoopCancelRef.current?.();
      alwaysLoopCancelRef.current = null;
      releaseAllHardware(rafRef, audioCtxRef, analyserRef, streamRef, recRef, chunksRef);
      setMicLevel(0);
      setIsHot(false);
      setSegmentSpeechDetected(false);
    };
  }, []);

  const setupMeter = useCallback((stream: MediaStream) => {
    try {
      const g = globalThis as typeof globalThis & { webkitAudioContext?: typeof AudioContext };
      const AC = globalThis.AudioContext ?? g.webkitAudioContext;
      if (!AC) return;
      const ctx = new AC();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.65;
      const src = ctx.createMediaStreamSource(stream);
      src.connect(analyser);
      audioCtxRef.current = ctx;
      analyserRef.current = analyser;

      const sample = () => {
        if (!mountedRef.current) return;
        const a = analyserRef.current;
        if (!a) return;
        const rms = rmsFromAnalyser(a);
        setMicLevel(Math.min(100, Math.round(rms ** 0.65 * 220)));
        rafRef.current = requestAnimationFrame(sample);
      };
      rafRef.current = requestAnimationFrame(sample);
    } catch {
      /* optional */
    }
  }, []);

  /** Push-to-talk: start one manual recording. */
  const startPush = useCallback(async () => {
    if (modeRef.current !== "push") return;
    setError(null);
    if (!hasGetUserMedia()) {
      setError(describeMicUnavailable());
      return;
    }
    try {
      const stream = await navigator.mediaDevices!.getUserMedia({ audio: AUDIO_CONSTRAINTS });
      streamRef.current = stream;
      setupMeter(stream);

      const mime = pickMimeType();
      const mr = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => {
        if (e.data.size) chunksRef.current.push(e.data);
      };
      mr.start(120);
      recRef.current = mr;
      setIsHot(true);
    } catch (e) {
      setError(formatGetUserMediaError(e));
      stopMeter(rafRef, audioCtxRef, analyserRef, setMicLevel);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, [setupMeter]);

  const stopPush = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      if (modeRef.current !== "push") {
        resolve(null);
        return;
      }
      const mr = recRef.current;
      if (!mr || mr.state === "inactive") {
        stopMeter(rafRef, audioCtxRef, analyserRef, setMicLevel);
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        recRef.current = null;
        setIsHot(false);
        resolve(null);
        return;
      }
      mr.onstop = () => {
        stopMeter(rafRef, audioCtxRef, analyserRef, setMicLevel);
        const mime = mr.mimeType || "audio/webm";
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        recRef.current = null;
        setIsHot(false);
        const blob = new Blob(chunksRef.current, { type: mime });
        chunksRef.current = [];
        resolve(blob.size ? blob : null);
      };
      mr.stop();
    });
  }, []);

  const discardPush = useCallback(async () => {
    await new Promise<void>((resolve) => {
      const mr = recRef.current;
      if (!mr || mr.state === "inactive") {
        stopMeter(rafRef, audioCtxRef, analyserRef, setMicLevel);
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        recRef.current = null;
        chunksRef.current = [];
        setIsHot(false);
        resolve();
        return;
      }
      chunksRef.current = [];
      mr.onstop = () => {
        stopMeter(rafRef, audioCtxRef, analyserRef, setMicLevel);
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        recRef.current = null;
        setIsHot(false);
        resolve();
      };
      mr.stop();
    });
  }, []);

  /** Always-listen loop: open one stream, segment on silence, call onUtterance. */
  useEffect(() => {
    if (mode !== "always") {
      alwaysLoopCancelRef.current?.();
      alwaysLoopCancelRef.current = null;
      return;
    }

    let cancelled = false;
    const cancel = () => {
      cancelled = true;
    };
    alwaysLoopCancelRef.current = cancel;

    const run = async () => {
      setError(null);
      if (!hasGetUserMedia()) {
        setError(describeMicUnavailable());
        return;
      }
      try {
        const stream = await navigator.mediaDevices!.getUserMedia({ audio: AUDIO_CONSTRAINTS });
        if (cancelled || modeRef.current !== "always") {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        setupMeter(stream);

        const analyser = analyserRef.current;
        if (!analyser) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        setIsHot(true);

        let firstHandsFreeSegment = true;
        while (!cancelled && mountedRef.current && modeRef.current === "always") {
          if (!firstHandsFreeSegment && mountedRef.current) {
            setUtteranceSeq((n) => n + 1);
          }
          firstHandsFreeSegment = false;

          const mime = pickMimeType();
          const mr = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
          const parts: BlobPart[] = [];
          mr.ondataavailable = (e) => {
            if (e.data.size) parts.push(e.data);
          };

          const blobPromise = new Promise<Blob | null>((resolve) => {
            mr.onstop = () => {
              if (mountedRef.current) {
                setSegmentSpeechDetected(false);
              }
              const blob = new Blob(parts, { type: mr.mimeType || "audio/webm" });
              // Never upload noise-only / silence segments — size alone is not a proxy for speech.
              resolve(blob.size > 280 && heardSpeech ? blob : null);
            };
          });

          mr.start(100);
          if (mountedRef.current) {
            setSegmentSpeechDetected(false);
          }

          let rafId = 0;
          let heardSpeech = false;
          let firstSpeechAt: number | null = null;
          let silenceAt: number | null = null;
          let emaRms = 0;
          let noiseFloor = 0.012;
          let speechPeak = 0;
          let softEnergyMs = 0;
          let lastTickAt = performance.now();
          const segmentStart = performance.now();
          let bargeArmed = true;
          let bargeHoldMs = 0;

          await new Promise<void>((done) => {
            const tick = () => {
              if (cancelled || modeRef.current !== "always" || !mountedRef.current) {
                cancelAnimationFrame(rafId);
                try {
                  if (mr.state !== "inactive") mr.stop();
                } catch {
                  /* ignore */
                }
                done();
                return;
              }

              const raw = rmsFromAnalyser(analyser);
              emaRms = emaRms === 0 ? raw : (1 - RMS_SMOOTH) * emaRms + RMS_SMOOTH * raw;
              const rms = emaRms;
              const now = performance.now();
              const dt = Math.min(80, now - lastTickAt);
              lastTickAt = now;

              if (!heardSpeech && rms > noiseFloor + 0.0035 && rms >= 0.0075) {
                softEnergyMs += dt;
                if (softEnergyMs >= SOFT_SPEECH_MS) {
                  if (firstSpeechAt === null) firstSpeechAt = now - Math.min(softEnergyMs, 380);
                  heardSpeech = true;
                  if (mountedRef.current) setSegmentSpeechDetected(true);
                }
              } else if (!heardSpeech) {
                softEnergyMs = 0;
              }

              const bargeTh = Math.max(BARGE_RMS_MIN, noiseFloor + 0.034);
              if (!suppressBargeInRef.current && rms > bargeTh) {
                bargeHoldMs += dt;
              } else {
                bargeHoldMs = Math.max(0, bargeHoldMs - dt * 1.8);
              }
              if (
                !suppressBargeInRef.current &&
                bargeArmed &&
                bargeHoldMs >= BARGE_HOLD_MS &&
                onBargeInRef.current
              ) {
                onBargeInRef.current();
                bargeHoldMs = 0;
                bargeArmed = false;
                window.setTimeout(() => {
                  bargeArmed = true;
                }, 900);
              }

              // Track ambient between ~silence and “strong” so thresholds move with HVAC / fan / gain.
              if (rms < noiseFloor + STRONG_ABOVE_FLOOR * 0.72) {
                noiseFloor = Math.max(
                  MIN_NOISE_FLOOR,
                  Math.min(MAX_NOISE_FLOOR, noiseFloor * 0.94 + rms * 0.06),
                );
              }

              const strongTh = noiseFloor + STRONG_ABOVE_FLOOR;
              const voiceOnTh = noiseFloor + VOICE_ON_ABOVE_FLOOR;
              const resumeTh = noiseFloor + RESUME_ABOVE_FLOOR;

              const tailByFloor = rms < noiseFloor + SILENCE_ABOVE_FLOOR;
              const tailByPeak =
                heardSpeech &&
                speechPeak >= noiseFloor + PEAK_MIN_OVER_FLOOR &&
                rms < speechPeak * PEAK_FRACTION_END;
              const inSilenceTail = tailByFloor || tailByPeak;

              // Never skip VAD while `busy`: silence detection would stall and the segment runs until
              // MAX_SEGMENT_MS — feels like the mic “never stops listening” after you finish talking.

              const elapsed = now - segmentStart;
              if (!heardSpeech && elapsed >= MAX_SILENCE_ABORT_MS) {
                cancelAnimationFrame(rafId);
                try {
                  if (mr.state !== "inactive") mr.stop();
                } catch {
                  /* ignore */
                }
                done();
                return;
              }

              // Hysteresis: mid band (not silence tail, not strong) does not reset silenceAt.
              if (rms >= strongTh) {
                if (!heardSpeech) firstSpeechAt = now;
                heardSpeech = true;
                if (mountedRef.current) setSegmentSpeechDetected(true);
                silenceAt = null;
              } else if (!heardSpeech && rms >= voiceOnTh) {
                if (firstSpeechAt === null) firstSpeechAt = now;
                heardSpeech = true;
                if (mountedRef.current) setSegmentSpeechDetected(true);
              } else if (heardSpeech) {
                if (rms >= resumeTh && silenceAt !== null) silenceAt = null;
                if (inSilenceTail) {
                  if (silenceAt === null) silenceAt = now;
                }
                const silentFor = silenceAt != null ? now - silenceAt : 0;
                const utterOk =
                  firstSpeechAt != null && now - firstSpeechAt >= MIN_UTTERANCE_MS && silentFor >= SILENCE_END_MS;
                const cap = heardSpeech && elapsed >= MAX_SEGMENT_MS;
                if (utterOk || cap) {
                  cancelAnimationFrame(rafId);
                  try {
                    if (mr.state !== "inactive") mr.stop();
                  } catch {
                    /* ignore */
                  }
                  done();
                  return;
                }
              }

              if (heardSpeech && rms >= voiceOnTh) {
                speechPeak = Math.max(speechPeak, rms);
              }

              rafId = requestAnimationFrame(tick);
            };
            rafId = requestAnimationFrame(tick);
          });

          const blob = await blobPromise;
          if (cancelled || modeRef.current !== "always") break;

          if (blob) {
            const hintSnapshot = (getTranscriptHintRef.current?.() ?? "").trim();
            const deadline = performance.now() + 45_000;
            while (busyRef.current && mountedRef.current && !cancelled && performance.now() < deadline) {
              await new Promise((r) => window.setTimeout(r, 60));
            }
            if (!cancelled && mountedRef.current) {
              try {
                await Promise.resolve(onUtteranceRef.current(blob, hintSnapshot));
              } catch {
                /* parent sets error */
              }
            }
          }

          await new Promise((r) => window.setTimeout(r, 120));
        }
      } catch (e) {
        if (mountedRef.current) setError(formatGetUserMediaError(e));
      } finally {
        stopMeter(rafRef, audioCtxRef, analyserRef, setMicLevel);
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        if (mountedRef.current) {
          setIsHot(false);
          setSegmentSpeechDetected(false);
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
      alwaysLoopCancelRef.current = null;
      streamRef.current?.getTracks().forEach((t) => t.stop());
      stopMeter(rafRef, audioCtxRef, analyserRef, setMicLevel);
      streamRef.current = null;
      setIsHot(false);
      setSegmentSpeechDetected(false);
    };
  }, [mode, setupMeter]);

  const togglePush = useCallback(async () => {
    if (modeRef.current !== "push") return;
    if (busyRef.current) return;
    if (isHotRef.current) {
      const blob = await stopPush();
      if (blob) {
        const hintSnapshot = (getTranscriptHintRef.current?.() ?? "").trim();
        await Promise.resolve(onUtteranceRef.current(blob, hintSnapshot));
        setUtteranceSeq((n) => n + 1);
      }
    } else {
      await startPush();
    }
  }, [startPush, stopPush]);

  const interrupt = useCallback(() => {
    onBargeInRef.current?.();
    if (modeRef.current === "push" && isHotRef.current) void discardPush();
  }, [discardPush]);

  /** UI “Listening…” should mean speech activity, not only an open hands-free stream. */
  const isListeningUi = mode === "always" ? segmentSpeechDetected : isHot;

  return {
    isHot,
    isListeningUi,
    utteranceSeq,
    micLevel,
    error,
    setError,
    togglePush,
    interrupt,
    startPush,
    stopPush,
    discardPush,
  };
}
