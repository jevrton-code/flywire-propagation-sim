/**
 * Deterministic node layouts.
 *
 * Why not just force-directed: this circuit is not a generic network. It is the
 * head-direction system of the central complex, and what a reader needs to see
 * is *which cell type and which hemisphere* lights up at each step. A spring
 * layout hides exactly that, and it moves between runs, so two screenshots of
 * the same simulation do not compare. So the default is a deterministic ring
 * grouped by cell type and hemisphere.
 *
 * Honesty note, enforced by how these functions are named and labelled in the
 * UI: the ring layout is a *presentation* layout. It is not the anatomical
 * geometry of the ellipsoid body, and the dataset carries no per-neuron
 * angular/wedge annotation that could give us the real one — the only spatial
 * data available is the soma position, which is what the `anatomy` layout
 * shows. Nothing here fabricates a position.
 */

import type { Neuron } from '../api/types';

export type LayoutId = 'ring' | 'anatomy' | 'force';

export interface LayoutPoint {
  x: number;
  y: number;
}

/** A labelled arc of the ring layout: one cell type within one hemisphere. */
export interface GroupArc {
  key: string;
  cellType: string;
  side: string;
  label: string;
  /** Radians, canvas convention (0 = +x, growing towards +y which is down). */
  startAngle: number;
  endAngle: number;
  midAngle: number;
  radius: number;
  count: number;
}

export interface LayoutResult {
  /** Indexed by `Neuron.index`; entries are in graph-space units. */
  positions: LayoutPoint[];
  groups: GroupArc[];
  /** Indices the layout could not place from real data (missing position). */
  unplaced: number[];
}

export const LAYOUT_LABELS: Record<LayoutId, string> = {
  ring: 'Anel por tipo celular',
  anatomy: 'Posição do soma',
  force: 'Força (conectividade)',
};

export const LAYOUT_DESCRIPTIONS: Record<LayoutId, string> = {
  ring:
    'Layout de apresentação: os neurônios são dispostos em um anel, agrupados por hemisfério e ' +
    'tipo celular. Não é a geometria anatômica do ellipsoid body — o conjunto de dados não traz ' +
    'a posição angular de cada neurônio no anel.',
  anatomy:
    'Projeção XY das coordenadas de voxel do soma, como vêm do FlyWire. É a única posição ' +
    'espacial real disponível: a posição do corpo celular, não das arborizações.',
  force:
    'Layout dirigido por forças, calculado a partir das conexões. Revela agrupamentos de ' +
    'conectividade; as posições não têm significado anatômico e mudam a cada execução.',
};

const RING_RADIUS = 340;
const SIDE_GAP_DEG = 7;
const TYPE_GAP_DEG = 2.5;

function toRadians(deg: number): number {
  return (deg * Math.PI) / 180;
}

/**
 * Order hemispheres so that "left" lands on the left of the screen.
 *
 * Any side value the data contains but this list does not is appended in the
 * order it appears, rather than dropped.
 */
function orderSides(sides: string[]): string[] {
  const preferred = ['left', 'right'];
  const known = preferred.filter((s) => sides.includes(s));
  const rest = sides.filter((s) => !preferred.includes(s)).sort();
  return [...known, ...rest];
}

/**
 * Ring layout: one circle, split into a contiguous span per hemisphere, each
 * span subdivided into arcs proportional to each cell type's population.
 *
 * @param neurons     every neuron, in the circuit's canonical order
 * @param cellTypeOrder canonical cell-type ordering (the backend's own, so the
 *                      layout does not invent an ordering of its own)
 */
export function ringLayout(neurons: Neuron[], cellTypeOrder: string[]): LayoutResult {
  const positions: LayoutPoint[] = new Array(neurons.length);
  const groups: GroupArc[] = [];

  const sidesPresent = unique(neurons.map((n) => n.side ?? 'desconhecido'));
  const sides = orderSides(sidesPresent);
  const sideSpan = 360 / Math.max(1, sides.length);

  const typeOrder = [
    ...cellTypeOrder,
    ...unique(neurons.map((n) => n.cell_type ?? 'não disponível')).filter(
      (t) => !cellTypeOrder.includes(t),
    ),
  ];

  sides.forEach((side, sideIndex) => {
    // 90 deg puts the first side (left) on the screen-left half.
    const spanStart = 90 + sideIndex * sideSpan + SIDE_GAP_DEG / 2;
    const spanEnd = 90 + (sideIndex + 1) * sideSpan - SIDE_GAP_DEG / 2;

    const inSide = neurons.filter((n) => (n.side ?? 'desconhecido') === side);
    const byType = typeOrder
      .map((type) => ({
        type,
        members: inSide.filter((n) => (n.cell_type ?? 'não disponível') === type),
      }))
      .filter((g) => g.members.length > 0);

    const usable = spanEnd - spanStart - TYPE_GAP_DEG * Math.max(0, byType.length - 1);
    const total = inSide.length || 1;

    let cursor = spanStart;
    for (const group of byType) {
      const arc = (usable * group.members.length) / total;
      const start = cursor;
      const end = cursor + arc;

      group.members.forEach((neuron, i) => {
        // Half-step insets keep the first and last node off the arc boundary,
        // so adjacent groups do not visually merge.
        const t = (i + 0.5) / group.members.length;
        const angle = toRadians(start + arc * t);
        positions[neuron.index] = {
          x: Math.cos(angle) * RING_RADIUS,
          y: Math.sin(angle) * RING_RADIUS,
        };
      });

      groups.push({
        key: `${side}:${group.type}`,
        cellType: group.type,
        side,
        label: group.type,
        startAngle: toRadians(start),
        endAngle: toRadians(end),
        midAngle: toRadians((start + end) / 2),
        radius: RING_RADIUS,
        count: group.members.length,
      });

      cursor = end + TYPE_GAP_DEG;
    }
  });

  // Defensive: any neuron a group pass somehow missed still needs a position.
  const unplaced: number[] = [];
  neurons.forEach((n) => {
    if (!positions[n.index]) {
      positions[n.index] = { x: 0, y: 0 };
      unplaced.push(n.index);
    }
  });

  return { positions, groups, unplaced };
}

const ANATOMY_EXTENT = 720;

/**
 * Soma positions, projected on XY and scaled to fit, aspect ratio preserved.
 *
 * Neurons whose position the dataset does not carry are *not* invented: they
 * are reported in `unplaced` and parked on a row under the projection, where
 * the renderer labels them as unavailable.
 */
export function anatomyLayout(neurons: Neuron[]): LayoutResult {
  const positions: LayoutPoint[] = new Array(neurons.length);
  const unplaced: number[] = [];

  const placed = neurons.filter(
    (n) => n.position.x !== null && n.position.y !== null,
  );

  if (placed.length === 0) {
    neurons.forEach((n, i) => {
      positions[n.index] = { x: (i % 20) * 24 - 240, y: Math.floor(i / 20) * 24 };
      unplaced.push(n.index);
    });
    return { positions, groups: [], unplaced };
  }

  const xs = placed.map((n) => n.position.x as number);
  const ys = placed.map((n) => n.position.y as number);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  const scale = ANATOMY_EXTENT / Math.max(spanX, spanY);
  const centreX = (minX + maxX) / 2;
  const centreY = (minY + maxY) / 2;

  for (const neuron of neurons) {
    const { x, y } = neuron.position;
    if (x === null || y === null) {
      unplaced.push(neuron.index);
      continue;
    }
    // Voxel y is used as-is: the dataset's own orientation, not re-oriented by
    // us, because we have no citable basis for flipping it.
    positions[neuron.index] = { x: (x - centreX) * scale, y: (y - centreY) * scale };
  }

  const parkY = ANATOMY_EXTENT / 2 + 70;
  unplaced.forEach((index, i) => {
    positions[index] = { x: (i - (unplaced.length - 1) / 2) * 22, y: parkY };
  });

  return { positions, groups: [], unplaced };
}

export function computeLayout(
  layout: LayoutId,
  neurons: Neuron[],
  cellTypeOrder: string[],
): LayoutResult | null {
  if (layout === 'ring') return ringLayout(neurons, cellTypeOrder);
  if (layout === 'anatomy') return anatomyLayout(neurons);
  return null; // 'force' is computed by the graph engine, not here.
}

function unique<T>(values: T[]): T[] {
  return Array.from(new Set(values));
}
