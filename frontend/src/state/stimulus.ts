/**
 * Turning the stimulus form into a `SourceSelector` the backend accepts.
 *
 * Kept pure and separate from the component so the rule that matters — the
 * backend refuses to default to "stimulate the whole circuit", so an empty
 * form must never be sent — is testable on its own.
 */

import type {
  CellTypeOption,
  RootId,
  SimulationRequest,
  SourceSelector,
  StimulusPreset,
} from '../api/types';

export type SourceMode = 'preset' | 'cell-type' | 'neurons';

export interface StimulusForm {
  mode: SourceMode;
  presetId: string | null;
  cellTypes: string[];
  side: 'left' | 'right' | null;
  /** Root ids picked by clicking nodes. Opaque strings, never numbers. */
  rootIds: RootId[];
  steps: number;
  amplitude: number;
  duration: number;
  /** Empty string means "use the backend default" — never a value we invented. */
  params: Record<string, string>;
}

export const DEFAULT_FORM: StimulusForm = {
  mode: 'preset',
  presetId: null,
  cellTypes: [],
  side: null,
  rootIds: [],
  steps: 40,
  amplitude: 1,
  duration: 6,
  params: {},
};

export type SourceValidation =
  | { ok: true; source: SourceSelector }
  | { ok: false; reason: string };

export function buildSource(
  form: StimulusForm,
  presets: StimulusPreset[],
): SourceValidation {
  if (form.mode === 'preset') {
    const preset = presets.find((p) => p.id === form.presetId);
    if (!preset) return { ok: false, reason: 'Escolha um estímulo pronto.' };
    return { ok: true, source: preset.source };
  }

  if (form.mode === 'cell-type') {
    if (form.cellTypes.length === 0) {
      return { ok: false, reason: 'Selecione ao menos um tipo celular.' };
    }
    return {
      ok: true,
      source: { cell_types: form.cellTypes, side: form.side ?? null },
    };
  }

  if (form.rootIds.length === 0) {
    return {
      ok: false,
      reason: 'Clique em neurônios no grafo para escolher a origem do estímulo.',
    };
  }
  return { ok: true, source: { root_ids: form.rootIds } };
}

const NUMERIC_PARAMS = [
  'threshold',
  'leak',
  'gain',
  'refractory_steps',
  'noise_std',
  'seed',
] as const;

export type NumericParam = (typeof NUMERIC_PARAMS)[number];
export const MODEL_PARAM_FIELDS: readonly NumericParam[] = NUMERIC_PARAMS;

/**
 * Build the request body.
 *
 * Only parameters the user actually typed are sent; blank fields are omitted so
 * the run inherits the server's defaults instead of a copy of them frozen into
 * this bundle.
 */
export function buildRequest(
  form: StimulusForm,
  source: SourceSelector,
  ntPolicy: 'known-first' | 'predicted',
): SimulationRequest {
  const params: Record<string, number> = {};
  for (const key of NUMERIC_PARAMS) {
    const raw = form.params[key];
    if (raw === undefined || raw.trim() === '') continue;
    const value = Number(raw);
    if (Number.isFinite(value)) params[key] = value;
  }

  return {
    nt_policy: ntPolicy,
    source,
    steps: form.steps,
    stimulus: { amplitude: form.amplitude, start: 1, duration: form.duration },
    ...(Object.keys(params).length ? { params } : {}),
    include_membrane: false,
    frame_format: 'dense',
    // No server-side pacing: stream as fast as it computes, let the playback
    // clock decide how fast the user sees it.
    frame_interval_ms: 0,
  };
}

/** How many neurons a cell-type selection would stimulate, for the form's hint. */
export function countSelected(
  cellTypes: string[],
  side: 'left' | 'right' | null,
  options: CellTypeOption[],
): number {
  let total = 0;
  for (const option of options) {
    if (!cellTypes.includes(option.cell_type)) continue;
    total += side ? option.count_by_side[side] ?? 0 : option.count;
  }
  return total;
}
