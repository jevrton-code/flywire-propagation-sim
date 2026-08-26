/**
 * TypeScript mirror of `src/flywire_api/schemas.py`.
 *
 * Two rules carried over from the backend contract:
 *
 * 1. **`root_id` is always a `string`.** FlyWire root ids are 18-digit
 *    integers, well past `Number.MAX_SAFE_INTEGER`. Anything in this app that
 *    touches a root id treats it as an opaque key — never `Number()`,
 *    never `parseInt`, never arithmetic.
 * 2. **Per-neuron values are flat arrays aligned to a single ordering**, given
 *    once in the stream header as `neuron_ids` and matching each neuron's
 *    `index` from `GET /api/circuit/graph`.
 */

/** Opaque 18-digit FlyWire identifier. Kept as a string, always. */
export type RootId = string;

export type NtPolicy = 'known-first' | 'predicted';
export type FrameFormat = 'dense' | 'delta';
export type Side = 'left' | 'right';

export interface Position {
  x: number | null;
  y: number | null;
  z: number | null;
}

export interface Neuron {
  index: number;
  root_id: RootId;
  cell_type: string | null;
  side: string | null;
  /** +1 excitatory, -1 inhibitory, 0 modulatory. */
  sign: number;
  polarity: string | null;
  neurotransmitter: string | null;
  /** 'known' (literature) or 'predicted' (Eckstein et al. 2024 classifier). */
  neurotransmitter_source: string | null;
  position: Position;
  in_degree: number;
  out_degree: number;
  in_synapses: number;
  out_synapses: number;
}

export interface Edge {
  pre_root_id: RootId;
  post_root_id: RootId;
  pre_index: number;
  post_index: number;
  syn_count: number;
  sign: number;
  weight: number;
  normalised_weight: number;
  polarity: string | null;
  pre_type: string | null;
  post_type: string | null;
  neuropils: string | null;
}

export interface SourceSelector {
  root_ids?: RootId[] | null;
  cell_types?: string[] | null;
  side?: Side | null;
  limit?: number | null;
}

export interface CellTypeOption {
  cell_type: string;
  count: number;
  count_by_side: Record<string, number>;
  polarity: string;
  root_ids: RootId[];
}

export interface StimulusPreset {
  id: string;
  label: string;
  description: string;
  source: SourceSelector;
}

export interface CoordinateSpace {
  space: string;
  voxel_size_nm: number[];
  note: string;
}

export interface CircuitSummary {
  circuit: string;
  title: string | null;
  nt_policy: string;
  nt_policy_note: string | null;
  n_neurons: number;
  n_connections: number;
  n_synapses: number;
  n_excitatory_neurons: number | null;
  n_inhibitory_neurons: number | null;
  n_modulatory_neurons: number | null;
  cell_types: string[];
  sides: string[];
  coordinate_space: CoordinateSpace;
  synapse_threshold: number | null;
  citations: string[];
  licensing: string[];
  /** What the model is NOT. The project requires this to be visible, not hidden. */
  simplifications: string[];
  disclaimer: string;
}

export interface GraphResponse {
  summary: CircuitSummary;
  neurons: Neuron[];
  edges: Edge[];
}

export interface CellTypeListResponse {
  circuit: string;
  nt_policy: string;
  cell_types: CellTypeOption[];
  sides: string[];
  presets: StimulusPreset[];
}

export interface LimitsBlock {
  max_steps: number;
  max_source_root_ids: number;
  max_amplitude: number;
  max_concurrent_simulations: number;
}

export interface ProvenanceResponse {
  circuit: string;
  nt_policy: string;
  /** `GraphProvenance.to_dict()`, including the nested `dataset` block. */
  provenance: Record<string, any>;
  citations: string[];
  licensing: string[];
  simplifications: string[];
  disclaimer: string;
}

export interface ModelDefaultsResponse {
  parameters: Record<string, unknown>;
  limits: LimitsBlock;
  simplifications: string[];
  disclaimer: string;
}

// --------------------------------------------------------------------------- //
// Simulation request
// --------------------------------------------------------------------------- //

export interface StimulusSpec {
  amplitude: number;
  start: number;
  duration: number;
}

export interface ModelParameters {
  threshold?: number;
  leak?: number;
  gain?: number;
  refractory_steps?: number;
  noise_std?: number;
  seed?: number;
}

export interface SimulationRequest {
  circuit?: string;
  nt_policy?: NtPolicy;
  source: SourceSelector;
  stimulus?: StimulusSpec;
  params?: ModelParameters;
  steps?: number;
  include_membrane?: boolean;
  frame_format?: FrameFormat;
  frame_interval_ms?: number;
}

// --------------------------------------------------------------------------- //
// WebSocket messages (server -> client)
// --------------------------------------------------------------------------- //

export interface StepSummary {
  step: number;
  n_spiked: number;
  fraction_spiked: number;
  total_activation: number;
  mean_activation: number;
  max_activation: number;
  mean_membrane: number;
  max_abs_membrane: number;
  total_input_current: number;
}

export interface SparseVector {
  indices: number[];
  values: number[];
}

export interface DenseFrameMessage {
  type: 'frame';
  format: 'dense';
  step: number;
  activation: number[];
  spiked: boolean[];
  membrane?: number[] | null;
  summary: StepSummary;
}

export interface DeltaFrameMessage {
  type: 'frame';
  format: 'delta';
  step: number;
  activation: SparseVector;
  /** Full list of indices spiking on this step — not a diff. */
  spiked: number[];
  membrane?: SparseVector | null;
  summary: StepSummary;
}

export type FrameMessage = DenseFrameMessage | DeltaFrameMessage;

export interface ReadyMessage {
  type: 'ready';
  protocol_version: number;
  limits: LimitsBlock & { max_frame_interval_ms: number };
}

export interface HeaderMessage {
  type: 'header';
  n_neurons: number;
  n_steps: number;
  n_frames: number;
  neuron_ids: RootId[];
  metadata: Record<string, unknown>;
  frame_format: FrameFormat;
  include_membrane: boolean;
  stimulated_root_ids: RootId[];
  stimulated_indices: number[];
}

export interface SimulationReport {
  steps: number;
  neurons: number;
  stimulated_neurons: number;
  neurons_that_fired: number;
  downstream_neurons_that_fired: number;
  fraction_of_circuit_recruited: number;
  total_spikes: number;
  neurons_fired_by_cell_type: Record<string, number>;
  first_spike_step_by_cell_type: Record<string, number>;
  peak_step: number | null;
  peak_n_spiked: number | null;
  final_total_activation: number;
  /** False means the run produced NaN/inf; the result must be treated as invalid. */
  numerically_finite: boolean;
  max_abs_membrane: number;
}

export interface CompleteMessage {
  type: 'complete';
  report: SimulationReport;
}

export interface CancelledMessage {
  type: 'cancelled';
  step: number;
  report: SimulationReport;
}

export interface ErrorMessage {
  type: 'error';
  status?: number;
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown> | null;
  };
}

export type ServerMessage =
  | ReadyMessage
  | HeaderMessage
  | FrameMessage
  | CompleteMessage
  | CancelledMessage
  | ErrorMessage;
