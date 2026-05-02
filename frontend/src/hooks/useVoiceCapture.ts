import type { MutableRefObject } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

const AUDIO_CONSTRAINTS: MediaTrackConstraints = {
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
};

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
  onUtterance: (blob: Blob) => void | Promise<void>;
  /** User speaks over assistant TTS — stop playback. */
  onBargeIn?: () => void;
};

/** Silence after speech to end one utterance (ms). */
const SILENCE_END_MS = 1500;
/** Ignore very short noise bursts. */
const MIN_UTTERANCE_MS = 700;
const SPEECH_RMS = 0.014;
const BARGE_RMS = 0.02;
const MAX_SEGMENT_MS = 45_000;

/**
 * Single mic pipeline: **push** (tap mic to record/send) or **always** (hands-free; auto-send after pause).
 * One `MediaStream` at a time; echo cancellation enabled for duplex-style use.
 */
export function useVoiceCapture({ mode, busy, onUtterance, onBargeIn }: UseVoiceCaptureOptions) {
  const [isHot, setIsHot] = useState(false);
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
  const onBargeInRef = useRef(onBargeIn);
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
    onBargeInRef.current = onBargeIn;
  }, [onBargeIn]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      alwaysLoopCancelRef.current?.();
      alwaysLoopCancelRef.current = null;
      releaseAllHardware(rafRef, audioCtxRef, analyserRef, streamRef, recRef, chunksRef);
      setMicLevel(0);
      setIsHot(false);
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
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Microphone not available.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: AUDIO_CONSTRAINTS });
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
      setError(e instanceof Error ? e.message : String(e));
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
      if (!navigator.mediaDevices?.getUserMedia) {
        setError("Microphone not available.");
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: AUDIO_CONSTRAINTS });
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

        while (!cancelled && mountedRef.current && modeRef.current === "always") {
          const mime = pickMimeType();
          const mr = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
          const parts: BlobPart[] = [];
          mr.ondataavailable = (e) => {
            if (e.data.size) parts.push(e.data);
          };

          const blobPromise = new Promise<Blob | null>((resolve) => {
            mr.onstop = () => {
              const blob = new Blob(parts, { type: mr.mimeType || "audio/webm" });
              resolve(blob.size > 400 ? blob : null);
            };
          });

          mr.start(100);

          let rafId = 0;
          let heardSpeech = false;
          let firstSpeechAt: number | null = null;
          let silenceAt: number | null = null;
          const segmentStart = performance.now();
          let bargeArmed = true;

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

              const rms = rmsFromAnalyser(analyser);
              const now = performance.now();

              if (bargeArmed && rms > BARGE_RMS && onBargeInRef.current) {
                onBargeInRef.current();
                bargeArmed = false;
                window.setTimeout(() => {
                  bargeArmed = true;
                }, 800);
              }

              if (busyRef.current) {
                rafId = requestAnimationFrame(tick);
                return;
              }

              const elapsed = now - segmentStart;
              if (!heardSpeech && elapsed >= MAX_SEGMENT_MS) {
                cancelAnimationFrame(rafId);
                try {
                  if (mr.state !== "inactive") mr.stop();
                } catch {
                  /* ignore */
                }
                done();
                return;
              }

              if (rms > SPEECH_RMS) {
                if (!heardSpeech) firstSpeechAt = now;
                heardSpeech = true;
                silenceAt = null;
              } else if (heardSpeech) {
                if (silenceAt === null) silenceAt = now;
                const silentFor = silenceAt ? now - silenceAt : 0;
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

              rafId = requestAnimationFrame(tick);
            };
            rafId = requestAnimationFrame(tick);
          });

          const blob = await blobPromise;
          if (cancelled || modeRef.current !== "always") break;

          if (blob && !busyRef.current) {
            try {
              await Promise.resolve(onUtteranceRef.current(blob));
            } catch {
              /* parent sets error */
            }
          }

          await new Promise((r) => window.setTimeout(r, 120));
        }
      } catch (e) {
        if (mountedRef.current) setError(e instanceof Error ? e.message : String(e));
      } finally {
        stopMeter(rafRef, audioCtxRef, analyserRef, setMicLevel);
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        if (mountedRef.current) setIsHot(false);
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
    };
  }, [mode, setupMeter]);

  const togglePush = useCallback(async () => {
    if (modeRef.current !== "push") return;
    if (busyRef.current) return;
    if (isHotRef.current) {
      const blob = await stopPush();
      if (blob) await Promise.resolve(onUtteranceRef.current(blob));
    } else {
      await startPush();
    }
  }, [startPush, stopPush]);

  const interrupt = useCallback(() => {
    onBargeInRef.current?.();
    if (modeRef.current === "push" && isHotRef.current) void discardPush();
  }, [discardPush]);

  return {
    isHot,
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
