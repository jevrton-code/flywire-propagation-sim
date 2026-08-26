import { describe, expect, it } from 'vitest';
import {
  initialRunState,
  materialiseFrame,
  parseServerMessage,
  runReducer,
  type RunState,
} from '../src/api/protocol';
import type { DeltaFrameMessage, FrameMessage } from '../src/api/types';
import { denseFrame, headerMessage, REPORT } from './fixtures';

const summary = denseFrame(1, [0, 0, 0], [false, false, false]).summary;

describe('parseServerMessage', () => {
  it('accepts every message type the backend documents', () => {
    for (const type of ['ready', 'header', 'frame', 'complete', 'cancelled', 'error']) {
      const result = parseServerMessage(JSON.stringify({ type }));
      expect(result.ok, type).toBe(true);
    }
  });

  it('rejects malformed JSON without throwing', () => {
    const result = parseServerMessage('{not json');
    expect(result).toEqual({ ok: false, reason: expect.stringContaining('JSON válido') });
  });

  it('rejects a JSON array or scalar', () => {
    expect(parseServerMessage('[1,2]').ok).toBe(false);
    expect(parseServerMessage('42').ok).toBe(false);
  });

  it('rejects an unknown message type', () => {
    const result = parseServerMessage(JSON.stringify({ type: 'teleport' }));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.reason).toContain('teleport');
  });

  it('rejects a non-string payload (e.g. a Blob from a binary frame)', () => {
    expect(parseServerMessage(new ArrayBuffer(4)).ok).toBe(false);
  });
});

describe('materialiseFrame', () => {
  it('expands a dense frame into typed arrays', () => {
    const frame = materialiseFrame(
      denseFrame(1, [0.1, 0.2, 0.3], [false, true, false]) as unknown as FrameMessage,
      null,
      3,
    );
    expect(Array.from(frame.activation)).toEqual([
      expect.closeTo(0.1),
      expect.closeTo(0.2),
      expect.closeTo(0.3),
    ]);
    expect(Array.from(frame.spiked)).toEqual([0, 1, 0]);
    expect(frame.membrane).toBeNull();
  });

  it('folds a delta frame onto the previous one', () => {
    const baseline = materialiseFrame(
      denseFrame(0, [0.5, 0.5, 0.5], [false, false, false]) as unknown as FrameMessage,
      null,
      3,
    );
    const delta: DeltaFrameMessage = {
      type: 'frame',
      format: 'delta',
      step: 1,
      activation: { indices: [1], values: [0.9] },
      spiked: [2],
      summary,
    };

    const next = materialiseFrame(delta, baseline, 3);

    // Unchanged entries carry over; the changed one is replaced.
    expect(Array.from(next.activation)).toEqual([
      expect.closeTo(0.5),
      expect.closeTo(0.9),
      expect.closeTo(0.5),
    ]);
    // `spiked` in a delta frame is the full set for that step, not a diff.
    expect(Array.from(next.spiked)).toEqual([0, 0, 1]);
    // The baseline must not be mutated: playback scrubs backwards through it.
    expect(Array.from(baseline.activation)).toEqual([
      expect.closeTo(0.5),
      expect.closeTo(0.5),
      expect.closeTo(0.5),
    ]);
  });

  it('refuses a delta frame with no baseline instead of guessing zeros', () => {
    const delta: DeltaFrameMessage = {
      type: 'frame',
      format: 'delta',
      step: 3,
      activation: { indices: [0], values: [1] },
      spiked: [],
      summary,
    };
    expect(() => materialiseFrame(delta, null, 3)).toThrow(/sem um frame anterior/);
  });

  it('ignores sparse indices outside the neuron array', () => {
    const baseline = materialiseFrame(
      denseFrame(0, [0, 0], [false, false]) as unknown as FrameMessage,
      null,
      2,
    );
    const delta: DeltaFrameMessage = {
      type: 'frame',
      format: 'delta',
      step: 1,
      activation: { indices: [99], values: [1] },
      spiked: [99, -1],
      summary,
    };
    const next = materialiseFrame(delta, baseline, 2);
    expect(Array.from(next.activation)).toEqual([0, 0]);
    expect(Array.from(next.spiked)).toEqual([0, 0]);
  });
});

describe('runReducer', () => {
  const feed = (state: RunState, message: unknown): RunState =>
    runReducer(state, { kind: 'server-message', raw: JSON.stringify(message) });

  it('walks a full run: ready -> header -> frames -> complete', () => {
    let state = runReducer(initialRunState, { kind: 'connecting' });
    expect(state.connection).toBe('connecting');

    state = runReducer(state, { kind: 'socket-open' });
    state = feed(state, { type: 'ready', protocol_version: 1, limits: {} });
    expect(state.connection).toBe('open');

    state = runReducer(state, { kind: 'start-requested' });
    expect(state.run).toBe('starting');

    state = feed(state, headerMessage());
    expect(state.run).toBe('streaming');
    expect(state.header?.stimulated_indices).toEqual([2]);
    // root ids survive as strings; 18 digits are past Number's exact range.
    expect(state.header?.neuron_ids[0]).toBe('720575940606137004');

    state = feed(state, denseFrame(0, [0, 0, 0, 0, 0], [false, false, false, false, false]));
    state = feed(state, denseFrame(1, [0, 0, 1, 0, 0], [false, false, true, false, false]));
    expect(state.frames).toHaveLength(2);
    expect(state.frames[1].summary.n_spiked).toBe(1);

    state = feed(state, { type: 'complete', report: REPORT });
    expect(state.run).toBe('complete');
    expect(state.report?.fraction_of_circuit_recruited).toBe(0.6);
  });

  it('clears the previous run when a new header arrives', () => {
    let state = feed(initialRunState, headerMessage());
    state = feed(state, denseFrame(0, [0, 0, 0, 0, 0], [false, false, false, false, false]));
    state = feed(state, { type: 'complete', report: REPORT });

    state = feed(state, headerMessage({ n_steps: 5, n_frames: 6 }));
    expect(state.frames).toHaveLength(0);
    expect(state.report).toBeNull();
    expect(state.run).toBe('streaming');
  });

  it('keeps the connection usable after a server error, because the socket stays open', () => {
    let state = runReducer(initialRunState, { kind: 'socket-open' });
    state = runReducer(state, { kind: 'start-requested' });
    state = feed(state, {
      type: 'error',
      status: 422,
      error: { code: 'unknown_cell_type', message: "unknown cell_type(s) ['EPGx']" },
    });

    expect(state.run).toBe('failed');
    expect(state.error?.code).toBe('unknown_cell_type');
    // The important part: the connection is untouched, so the user can retry.
    expect(state.connection).toBe('open');

    state = runReducer(state, { kind: 'start-requested' });
    expect(state.error).toBeNull();
    expect(state.run).toBe('starting');
  });

  it('reports a socket that dies mid-stream instead of hanging', () => {
    let state = feed(runReducer(initialRunState, { kind: 'socket-open' }), headerMessage());
    state = feed(state, denseFrame(0, [0, 0, 0, 0, 0], [false, false, false, false, false]));
    state = runReducer(state, { kind: 'socket-closed', clean: false });

    expect(state.run).toBe('failed');
    expect(state.error?.code).toBe('connection_lost');
    // Frames already received stay replayable.
    expect(state.frames).toHaveLength(1);
  });

  it('does not invent an error when an idle socket closes', () => {
    const state = runReducer(
      runReducer(initialRunState, { kind: 'socket-open' }),
      { kind: 'socket-closed', clean: true },
    );
    expect(state.error).toBeNull();
    expect(state.run).toBe('idle');
  });

  it('ignores "nothing_to_cancel" once the run already finished', () => {
    // The race the user hits constantly: a 200-step run on localhost ends in
    // under a second, so "stop" often arrives after `complete`. That must not
    // paint a red banner over a perfectly good result.
    let state = feed(runReducer(initialRunState, { kind: 'socket-open' }), headerMessage());
    state = feed(state, { type: 'complete', report: REPORT });
    const after = feed(state, {
      type: 'error',
      status: 422,
      error: { code: 'nothing_to_cancel', message: 'no simulation is running' },
    });

    expect(after.error).toBeNull();
    expect(after.run).toBe('complete');
    expect(after.report).not.toBeNull();
  });

  it('still mentions "nothing_to_cancel" if it arrives mid-stream', () => {
    let state = feed(runReducer(initialRunState, { kind: 'socket-open' }), headerMessage());
    state = feed(state, {
      type: 'error',
      error: { code: 'nothing_to_cancel', message: 'no simulation is running' },
    });
    expect(state.notice).toContain('no simulation is running');
    expect(state.run).toBe('streaming');
  });

  it('records a cancelled run with its partial report and stop step', () => {
    let state = feed(runReducer(initialRunState, { kind: 'socket-open' }), headerMessage());
    state = feed(state, { type: 'cancelled', step: 12, report: REPORT });
    expect(state.run).toBe('cancelled');
    expect(state.cancelledAtStep).toBe(12);
    expect(state.report).not.toBeNull();
  });

  it('surfaces an unparsable message as a notice, not a crash', () => {
    const state = runReducer(initialRunState, {
      kind: 'server-message',
      raw: 'definitely not json',
    });
    expect(state.notice).toContain('JSON');
    expect(state.run).toBe('idle');
  });

  it('flags a frame that arrives before the header', () => {
    const state = feed(initialRunState, denseFrame(0, [0], [false]));
    expect(state.notice).toContain('antes do cabeçalho');
    expect(state.frames).toHaveLength(0);
  });

  it('turns an undecodable frame into a failed run with a readable message', () => {
    let state = feed(initialRunState, headerMessage({ frame_format: 'delta' }));
    state = feed(state, {
      type: 'frame',
      format: 'delta',
      step: 1,
      activation: { indices: [0], values: [1] },
      spiked: [],
      summary,
    });
    expect(state.run).toBe('failed');
    expect(state.error?.code).toBe('frame_decode_failed');
  });
});
