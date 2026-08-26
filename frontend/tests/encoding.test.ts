import { describe, expect, it } from 'vitest';
import {
  activationColor,
  nodeRadius,
  polarityColor,
  polarityOfSign,
  POLARITY_COLORS,
} from '../src/graph/encoding';

function luminance(css: string): number {
  const [r, g, b] = css.match(/\d+(\.\d+)?/g)!.map(Number);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

describe('activationColor', () => {
  it('gets monotonically brighter with activation, so it reads as intensity', () => {
    const samples = [0, 0.2, 0.4, 0.6, 0.8, 1].map((t) => luminance(activationColor(t)));
    for (let i = 1; i < samples.length; i += 1) {
      expect(samples[i]).toBeGreaterThan(samples[i - 1]);
    }
  });

  it('clamps out-of-range values instead of extrapolating off the ramp', () => {
    expect(activationColor(-5)).toBe(activationColor(0));
    expect(activationColor(12)).toBe(activationColor(1));
  });

  it('treats NaN as resting rather than producing "rgb(NaN, ...)"', () => {
    expect(activationColor(Number.NaN)).toBe(activationColor(0));
  });

  it('emits rgba only when an alpha was asked for', () => {
    expect(activationColor(0.5)).toMatch(/^rgb\(/);
    expect(activationColor(0.5, 0.4)).toMatch(/^rgba\(.*0\.4\)$/);
  });
});

describe('polarity', () => {
  it('follows the backend sign convention: +1 / -1 / 0', () => {
    expect(polarityOfSign(1)).toBe('excitatory');
    expect(polarityOfSign(-1)).toBe('inhibitory');
    expect(polarityOfSign(0)).toBe('modulatory');
  });

  it('gives each polarity a distinct colour', () => {
    const colors = new Set(Object.values(POLARITY_COLORS));
    expect(colors.size).toBe(3);
    expect(polarityColor(-1)).toBe(POLARITY_COLORS.inhibitory);
  });
});

describe('nodeRadius', () => {
  it('is bounded, so one hub neuron cannot swamp the view', () => {
    const r = nodeRadius(100000, 10, 400);
    expect(r).toBeLessThanOrEqual(8.6);
    expect(nodeRadius(0, 10, 400)).toBeGreaterThanOrEqual(3.1);
  });

  it('grows with synapse count', () => {
    expect(nodeRadius(300, 10, 400)).toBeGreaterThan(nodeRadius(20, 10, 400));
  });

  it('falls back to a mid size when every neuron has the same count', () => {
    expect(nodeRadius(50, 50, 50)).toBeCloseTo((3.1 + 8.6) / 2);
  });
});
