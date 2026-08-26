import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Playback clock for the frame buffer.
 *
 * Playback is deliberately decoupled from arrival: the server streams as fast
 * as it can compute (the request asks for no server-side pacing), the client
 * shows step 0 the moment it lands and then walks the buffer at a speed the
 * user controls. If playback catches up with the stream — which it does on a
 * long run — `waiting` goes true and the UI says so instead of silently
 * stalling. Once the run is over, the same buffer replays with no re-run.
 */

export const SPEED_OPTIONS = [2, 4, 8, 16] as const;
export type PlaybackSpeed = (typeof SPEED_OPTIONS)[number];

export interface Playback {
  /** Index into the frame buffer; frame 0 is the resting state. */
  step: number;
  isPlaying: boolean;
  /** True when playback has run out of buffered frames but more are coming. */
  waiting: boolean;
  /** Steps per second. */
  speed: PlaybackSpeed;
  setSpeed: (speed: PlaybackSpeed) => void;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  seek: (step: number) => void;
  stepForward: () => void;
  stepBack: () => void;
  /** Jump back to step 0 and play the buffered run again. */
  replay: () => void;
}

export interface PlaybackOptions {
  /** Number of frames currently buffered. */
  frameCount: number;
  /** True while the server is still sending frames for this run. */
  isStreaming: boolean;
  /** Changes whenever a new run begins; resets the clock. */
  runKey: number;
}

export function usePlayback({
  frameCount,
  isStreaming,
  runKey,
}: PlaybackOptions): Playback {
  const [step, setStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [speed, setSpeed] = useState<PlaybackSpeed>(8);

  const frameCountRef = useRef(frameCount);
  frameCountRef.current = frameCount;
  const streamingRef = useRef(isStreaming);
  streamingRef.current = isStreaming;
  const speedRef = useRef<PlaybackSpeed>(speed);
  speedRef.current = speed;

  // A new run: rewind and start playing as frames arrive.
  useEffect(() => {
    setStep(0);
    setWaiting(false);
    setIsPlaying(true);
  }, [runKey]);

  useEffect(() => {
    if (!isPlaying) {
      setWaiting(false);
      return;
    }

    let raf = 0;
    let last = performance.now();
    let accumulated = 0;

    const tick = (now: number) => {
      const delta = (now - last) / 1000;
      last = now;
      accumulated += delta;

      const perStep = 1 / speedRef.current;
      let advance = 0;
      while (accumulated >= perStep) {
        accumulated -= perStep;
        advance += 1;
      }

      if (advance > 0) {
        setStep((current) => {
          const lastIndex = frameCountRef.current - 1;
          if (current >= lastIndex) {
            if (streamingRef.current) {
              setWaiting(true);
            } else if (lastIndex >= 0) {
              // Run finished and playback reached the end: stop cleanly.
              setIsPlaying(false);
              setWaiting(false);
            }
            return current < 0 ? 0 : current;
          }
          setWaiting(false);
          return Math.min(lastIndex, current + advance);
        });
      }

      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [isPlaying]);

  const play = useCallback(() => setIsPlaying(true), []);
  const pause = useCallback(() => setIsPlaying(false), []);
  const toggle = useCallback(() => setIsPlaying((v) => !v), []);

  const seek = useCallback((target: number) => {
    const lastIndex = frameCountRef.current - 1;
    setIsPlaying(false);
    setWaiting(false);
    setStep(Math.max(0, Math.min(lastIndex < 0 ? 0 : lastIndex, Math.round(target))));
  }, []);

  const stepForward = useCallback(() => {
    setIsPlaying(false);
    setStep((c) => Math.min(Math.max(0, frameCountRef.current - 1), c + 1));
  }, []);

  const stepBack = useCallback(() => {
    setIsPlaying(false);
    setStep((c) => Math.max(0, c - 1));
  }, []);

  const replay = useCallback(() => {
    setStep(0);
    setWaiting(false);
    setIsPlaying(true);
  }, []);

  // Clamp if the buffer shrank (a new run cleared it).
  useEffect(() => {
    setStep((current) => {
      const lastIndex = frameCount - 1;
      if (lastIndex < 0) return 0;
      return current > lastIndex ? lastIndex : current;
    });
  }, [frameCount]);

  return {
    step,
    isPlaying,
    waiting,
    speed,
    setSpeed,
    play,
    pause,
    toggle,
    seek,
    stepForward,
    stepBack,
    replay,
  };
}
