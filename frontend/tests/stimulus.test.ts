import { describe, expect, it } from 'vitest';
import {
  buildRequest,
  buildSource,
  countSelected,
  DEFAULT_FORM,
  type StimulusForm,
} from '../src/state/stimulus';
import { CELL_TYPES } from './fixtures';

const presets = CELL_TYPES.presets;
const form = (overrides: Partial<StimulusForm>): StimulusForm => ({
  ...DEFAULT_FORM,
  ...overrides,
});

describe('buildSource', () => {
  it('uses the backend preset verbatim, without rebuilding the selector', () => {
    const result = buildSource(form({ mode: 'preset', presetId: 'epg_left' }), presets);
    expect(result).toEqual({ ok: true, source: presets[0].source });
  });

  it('refuses a preset mode with nothing chosen', () => {
    const result = buildSource(form({ mode: 'preset', presetId: null }), presets);
    expect(result.ok).toBe(false);
  });

  it('refuses an unknown preset id rather than sending it blindly', () => {
    const result = buildSource(form({ mode: 'preset', presetId: 'nope' }), presets);
    expect(result.ok).toBe(false);
  });

  it('builds a cell-type selector, with the hemisphere when one is chosen', () => {
    const result = buildSource(
      form({ mode: 'cell-type', cellTypes: ['EPG'], side: 'left' }),
      presets,
    );
    expect(result).toEqual({ ok: true, source: { cell_types: ['EPG'], side: 'left' } });
  });

  it('never sends an empty selector, which the backend would reject', () => {
    // The API refuses to default to "stimulate the whole circuit"; the form has
    // to catch that before a round trip.
    expect(buildSource(form({ mode: 'cell-type', cellTypes: [] }), presets).ok).toBe(false);
    expect(buildSource(form({ mode: 'neurons', rootIds: [] }), presets).ok).toBe(false);
  });

  it('passes root ids through as strings, untouched', () => {
    const rootIds = ['720575940613829900', '720575940604801993'];
    const result = buildSource(form({ mode: 'neurons', rootIds }), presets);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.source.root_ids).toEqual(rootIds);
      for (const id of result.source.root_ids ?? []) {
        expect(typeof id).toBe('string');
        expect(id).toHaveLength(18);
      }
    }
  });
});

describe('buildRequest', () => {
  const source = { cell_types: ['EPG'], side: 'left' as const };

  it('carries the form values the user set', () => {
    const request = buildRequest(
      form({ steps: 60, amplitude: 2.5, duration: 8 }),
      source,
      'known-first',
    );
    expect(request.steps).toBe(60);
    expect(request.stimulus).toEqual({ amplitude: 2.5, start: 1, duration: 8 });
    expect(request.nt_policy).toBe('known-first');
    expect(request.frame_format).toBe('dense');
    // No server pacing: the client's playback clock controls the speed.
    expect(request.frame_interval_ms).toBe(0);
  });

  it('omits the params block entirely when nothing was typed', () => {
    const request = buildRequest(form({ params: { threshold: '', leak: '  ' } }), source, 'known-first');
    expect(request).not.toHaveProperty('params');
  });

  it('sends only the model parameters the user actually filled in', () => {
    const request = buildRequest(
      form({ params: { threshold: '0.35', leak: '', seed: '7' } }),
      source,
      'known-first',
    );
    expect(request.params).toEqual({ threshold: 0.35, seed: 7 });
  });

  it('drops values that are not finite numbers instead of sending NaN', () => {
    const request = buildRequest(form({ params: { threshold: 'abc' } }), source, 'known-first');
    expect(request).not.toHaveProperty('params');
  });
});

describe('countSelected', () => {
  it('counts the whole population when no hemisphere is chosen', () => {
    expect(countSelected(['EPG', 'Delta7'], null, CELL_TYPES.cell_types)).toBe(4);
  });

  it('counts only the chosen hemisphere', () => {
    expect(countSelected(['EPG', 'Delta7'], 'left', CELL_TYPES.cell_types)).toBe(2);
  });

  it('is zero for a hemisphere a type has no neurons in', () => {
    expect(countSelected(['PEN_a(PEN1)'], 'right', CELL_TYPES.cell_types)).toBe(0);
  });
});
