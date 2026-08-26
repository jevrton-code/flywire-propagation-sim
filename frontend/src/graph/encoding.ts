/**
 * The visual encoding, in one place.
 *
 * Canvas cannot read CSS custom properties, so the ramp and the polarity
 * colours are duplicated here as literals. They must stay in sync with
 * `src/styles/tokens.css` — the legend renders from *these* values via
 * {@link activationColor} and {@link polarityColor}, so the legend can never
 * silently disagree with the canvas.
 */

export type Polarity = 'excitatory' | 'inhibitory' | 'modulatory';

/** Activation ramp stops, dark (resting) to hot (fully active). */
export const ACTIVATION_RAMP: readonly [number, number, number][] = [
  [27, 34, 51], // #1b2233
  [36, 59, 107], // #243b6b
  [63, 77, 160], // #3f4da0
  [125, 79, 158], // #7d4f9e
  [194, 92, 120], // #c25c78
  [242, 140, 60], // #f28c3c
  [255, 217, 119], // #ffd977
];

/**
 * Map an activation value in [0, 1] to a CSS colour by linear interpolation
 * between ramp stops. Values outside the range are clamped rather than
 * extrapolated: the backend documents activation as a filtered spike trace in
 * [0, 1], and a colour that runs off the ramp would be a silent lie about it.
 */
export function activationColor(value: number, alpha = 1): string {
  const t = Math.min(1, Math.max(0, Number.isFinite(value) ? value : 0));
  const scaled = t * (ACTIVATION_RAMP.length - 1);
  const low = Math.floor(scaled);
  const high = Math.min(ACTIVATION_RAMP.length - 1, low + 1);
  const f = scaled - low;
  const a = ACTIVATION_RAMP[low];
  const b = ACTIVATION_RAMP[high];
  const r = Math.round(a[0] + (b[0] - a[0]) * f);
  const g = Math.round(a[1] + (b[1] - a[1]) * f);
  const bl = Math.round(a[2] + (b[2] - a[2]) * f);
  return alpha >= 1 ? `rgb(${r}, ${g}, ${bl})` : `rgba(${r}, ${g}, ${bl}, ${alpha})`;
}

export const POLARITY_COLORS: Record<Polarity, string> = {
  excitatory: '#46d39a',
  inhibitory: '#f2699f',
  modulatory: '#8f9bb3',
};

/** Sign as the backend defines it: +1 excitatory, -1 inhibitory, 0 modulatory. */
export function polarityOfSign(sign: number): Polarity {
  if (sign > 0) return 'excitatory';
  if (sign < 0) return 'inhibitory';
  return 'modulatory';
}

export function polarityColor(sign: number): string {
  return POLARITY_COLORS[polarityOfSign(sign)];
}

export const POLARITY_LABELS: Record<Polarity, string> = {
  excitatory: 'excitatório',
  inhibitory: 'inibitório',
  modulatory: 'modulatório',
};

/**
 * Node radius from total synapse count, on a log scale.
 *
 * Linear area-by-degree would make the two or three hub neurons swamp
 * everything else; the log keeps the smallest node visible and the largest
 * about three times its radius.
 */
export function nodeRadius(totalSynapses: number, minSyn: number, maxSyn: number): number {
  const MIN_R = 3.1;
  const MAX_R = 8.6;
  if (!(maxSyn > minSyn)) return (MIN_R + MAX_R) / 2;
  const lo = Math.log1p(minSyn);
  const hi = Math.log1p(maxSyn);
  const t = (Math.log1p(Math.max(0, totalSynapses)) - lo) / (hi - lo);
  return MIN_R + (MAX_R - MIN_R) * Math.min(1, Math.max(0, t));
}

/**
 * Draw the polarity glyph for a node, centred at (x, y).
 *
 * Shape, not colour, carries polarity: circle = excitatory, square =
 * inhibitory, triangle = modulatory.
 */
export function tracePolarityShape(
  ctx: CanvasRenderingContext2D,
  polarity: Polarity,
  x: number,
  y: number,
  r: number,
): void {
  ctx.beginPath();
  if (polarity === 'excitatory') {
    ctx.arc(x, y, r, 0, Math.PI * 2);
    return;
  }
  if (polarity === 'inhibitory') {
    // Slightly shrunk so a square and a circle of the same `r` read as the
    // same visual weight rather than the square looking bigger.
    const s = r * 0.88;
    ctx.rect(x - s, y - s, s * 2, s * 2);
    ctx.closePath();
    return;
  }
  const s = r * 1.18;
  ctx.moveTo(x, y - s);
  ctx.lineTo(x + s * 0.87, y + s * 0.5);
  ctx.lineTo(x - s * 0.87, y + s * 0.5);
  ctx.closePath();
}
