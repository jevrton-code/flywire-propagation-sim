import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { usePlayback } from '../src/state/usePlayback';

/**
 * The playback clock runs on requestAnimationFrame and `performance.now`, so
 * both are faked here; advancing timers is what makes "one second passed" mean
 * something deterministic.
 */
beforeEach(() => {
  vi.useFakeTimers({
    toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance', 'Date'],
  });
});

afterEach(() => {
  vi.useRealTimers();
});

const advance = async (ms: number) => {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
};

describe('usePlayback', () => {
  it('auto-plays a new run and advances at the chosen steps per second', async () => {
    const { result, rerender } = renderHook(
      (props: { frameCount: number; isStreaming: boolean; runKey: number }) =>
        usePlayback(props),
      { initialProps: { frameCount: 0, isStreaming: true, runKey: 1 } },
    );

    expect(result.current.isPlaying).toBe(true);
    expect(result.current.step).toBe(0);

    rerender({ frameCount: 41, isStreaming: false, runKey: 1 });
    // Default speed is 8 steps/s. The bounds allow for the 16 ms animation
    // frame granularity: a whole step can be pending when the clock stops.
    await advance(1000);
    expect(result.current.step).toBeGreaterThanOrEqual(7);
    expect(result.current.step).toBeLessThanOrEqual(8);
  });

  it('honours a speed change', async () => {
    const { result, rerender } = renderHook(
      (props: { frameCount: number; isStreaming: boolean; runKey: number }) =>
        usePlayback(props),
      { initialProps: { frameCount: 41, isStreaming: false, runKey: 1 } },
    );

    act(() => result.current.setSpeed(2));
    rerender({ frameCount: 41, isStreaming: false, runKey: 1 });
    await advance(1000);
    // Four times slower than the default: one or two steps, never eight.
    expect(result.current.step).toBeGreaterThanOrEqual(1);
    expect(result.current.step).toBeLessThanOrEqual(2);

    act(() => result.current.setSpeed(16));
    await advance(1000);
    expect(result.current.step).toBeGreaterThanOrEqual(15);
  });

  it('freezes on pause and resumes from the same step', async () => {
    const { result } = renderHook(() =>
      usePlayback({ frameCount: 41, isStreaming: false, runKey: 1 }),
    );

    await advance(500);
    const paused = result.current.step;
    act(() => result.current.pause());
    await advance(2000);
    expect(result.current.step).toBe(paused);

    act(() => result.current.play());
    await advance(500);
    expect(result.current.step).toBeGreaterThan(paused);
  });

  it('waits, rather than stalling silently, when playback catches the stream', async () => {
    const { result } = renderHook(() =>
      usePlayback({ frameCount: 3, isStreaming: true, runKey: 1 }),
    );

    await advance(2000);
    expect(result.current.step).toBe(2); // the last buffered frame
    expect(result.current.waiting).toBe(true);
    expect(result.current.isPlaying).toBe(true); // still playing, just starved
  });

  it('stops at the end once the run is over', async () => {
    const { result } = renderHook(() =>
      usePlayback({ frameCount: 3, isStreaming: false, runKey: 1 }),
    );

    await advance(2000);
    expect(result.current.step).toBe(2);
    expect(result.current.isPlaying).toBe(false);
    expect(result.current.waiting).toBe(false);
  });

  it('replays the buffered run from the start without a new request', async () => {
    const { result } = renderHook(() =>
      usePlayback({ frameCount: 41, isStreaming: false, runKey: 1 }),
    );

    await advance(1000);
    expect(result.current.step).toBeGreaterThan(0);

    act(() => result.current.replay());
    expect(result.current.step).toBe(0);
    expect(result.current.isPlaying).toBe(true);
  });

  it('pauses when the user scrubs or steps manually', async () => {
    const { result } = renderHook(() =>
      usePlayback({ frameCount: 41, isStreaming: false, runKey: 1 }),
    );

    act(() => result.current.seek(20));
    expect(result.current.step).toBe(20);
    expect(result.current.isPlaying).toBe(false);

    act(() => result.current.stepForward());
    expect(result.current.step).toBe(21);
    act(() => result.current.stepBack());
    expect(result.current.step).toBe(20);
  });

  it('clamps seeking to the frames actually received', async () => {
    const { result } = renderHook(() =>
      usePlayback({ frameCount: 5, isStreaming: true, runKey: 1 }),
    );

    act(() => result.current.seek(999));
    expect(result.current.step).toBe(4);
    act(() => result.current.seek(-3));
    expect(result.current.step).toBe(0);
  });

  it('rewinds when a new run starts', async () => {
    const { result, rerender } = renderHook(
      (props: { frameCount: number; isStreaming: boolean; runKey: number }) =>
        usePlayback(props),
      { initialProps: { frameCount: 41, isStreaming: false, runKey: 1 } },
    );

    await advance(1000);
    expect(result.current.step).toBeGreaterThan(0);

    rerender({ frameCount: 0, isStreaming: true, runKey: 2 });
    expect(result.current.step).toBe(0);
    expect(result.current.isPlaying).toBe(true);
  });
});
