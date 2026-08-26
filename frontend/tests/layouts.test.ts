import { describe, expect, it } from 'vitest';
import { anatomyLayout, computeLayout, ringLayout } from '../src/graph/layouts';
import { NEURONS, SUMMARY } from './fixtures';

describe('ringLayout', () => {
  const result = ringLayout(NEURONS, SUMMARY.cell_types);

  it('places every neuron exactly once, indexed by Neuron.index', () => {
    expect(result.positions).toHaveLength(NEURONS.length);
    for (const neuron of NEURONS) {
      expect(result.positions[neuron.index]).toBeDefined();
    }
    expect(result.unplaced).toEqual([]);
  });

  it('keeps every node on a single circle', () => {
    const radii = NEURONS.map((n) => {
      const p = result.positions[n.index];
      return Math.hypot(p.x, p.y);
    });
    for (const radius of radii) expect(radius).toBeCloseTo(radii[0], 6);
  });

  it('puts the left hemisphere on the left of the screen and the right on the right', () => {
    for (const neuron of NEURONS) {
      const { x } = result.positions[neuron.index];
      if (neuron.side === 'left') expect(x).toBeLessThan(0);
      if (neuron.side === 'right') expect(x).toBeGreaterThan(0);
    }
  });

  it('emits one labelled arc per (hemisphere, cell type) present in the data', () => {
    const keys = result.groups.map((g) => g.key).sort();
    expect(keys).toEqual([
      'left:Delta7',
      'left:EPG',
      'left:PEN_a(PEN1)',
      'right:Delta7',
      'right:EPG',
    ]);
    const total = result.groups.reduce((acc, g) => acc + g.count, 0);
    expect(total).toBe(NEURONS.length);
  });

  it('is deterministic — the same input gives byte-identical positions', () => {
    const again = ringLayout(NEURONS, SUMMARY.cell_types);
    expect(again.positions).toEqual(result.positions);
  });

  it('does not drop cell types missing from the canonical ordering', () => {
    // A type the summary forgot to list must still be laid out, not skipped.
    const partial = ringLayout(NEURONS, ['EPG']);
    expect(partial.unplaced).toEqual([]);
    expect(partial.groups.map((g) => g.cellType)).toContain('Delta7');
  });
});

describe('anatomyLayout', () => {
  it('projects soma positions preserving their relative order', () => {
    const result = anatomyLayout(NEURONS);
    const right = result.positions[0]; // soma x = 154720
    const left = result.positions[1]; // soma x = 109280
    expect(right.x).toBeGreaterThan(left.x);
  });

  it('reports neurons with no recorded position instead of inventing one', () => {
    // Fixture index 4 has position {null, null, null}.
    const result = anatomyLayout(NEURONS);
    expect(result.unplaced).toEqual([4]);
    // It still gets a slot so it can be drawn and labelled as unavailable,
    // but that slot is outside the projected extent, not inside it.
    const parked = result.positions[4];
    const placed = [0, 1, 2, 3].map((i) => result.positions[i].y);
    expect(parked.y).toBeGreaterThan(Math.max(...placed));
  });

  it('fits inside a bounded extent regardless of voxel magnitudes', () => {
    const result = anatomyLayout(NEURONS);
    for (const index of [0, 1, 2, 3]) {
      expect(Math.abs(result.positions[index].x)).toBeLessThanOrEqual(400);
      expect(Math.abs(result.positions[index].y)).toBeLessThanOrEqual(400);
    }
  });

  it('handles a circuit with no positions at all without throwing', () => {
    const none = NEURONS.map((n) => ({ ...n, position: { x: null, y: null, z: null } }));
    const result = anatomyLayout(none);
    expect(result.unplaced).toHaveLength(NEURONS.length);
    expect(result.positions.filter(Boolean)).toHaveLength(NEURONS.length);
  });
});

describe('computeLayout', () => {
  it('returns null for the force layout, which the engine owns', () => {
    expect(computeLayout('force', NEURONS, SUMMARY.cell_types)).toBeNull();
  });

  it('dispatches to the deterministic layouts', () => {
    expect(computeLayout('ring', NEURONS, SUMMARY.cell_types)?.groups.length).toBeGreaterThan(0);
    expect(computeLayout('anatomy', NEURONS, SUMMARY.cell_types)?.groups).toEqual([]);
  });
});
