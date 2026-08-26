/**
 * Fixtures shaped exactly like the real API responses.
 *
 * This is a hand-built 5-neuron toy circuit, not a captured API response: the
 * degrees, positions, weights and edges below are invented for test coverage
 * and do not describe the real ring-attractor subgraph (some of these
 * root_ids' real attributes differ). What *is* real is the `root_id` values
 * themselves -- five genuine 18-digit FlyWire ids from the ring attractor
 * core, kept as strings throughout, so the tests catch any accidental
 * `Number()` coercion on the way through the app (which would silently lose
 * precision on ids this large).
 */

import type {
  CellTypeListResponse,
  CircuitSummary,
  Edge,
  GraphResponse,
  ModelDefaultsResponse,
  Neuron,
  ProvenanceResponse,
  SimulationReport,
} from '../src/api/types';

export const NEURONS: Neuron[] = [
  {
    index: 0,
    root_id: '720575940606137004',
    cell_type: 'Delta7',
    side: 'right',
    sign: -1,
    polarity: 'inhibitory',
    neurotransmitter: 'glutamate',
    neurotransmitter_source: 'known',
    position: { x: 154720, y: 48176, z: 4871 },
    in_degree: 6,
    out_degree: 8,
    in_synapses: 43,
    out_synapses: 81,
  },
  {
    index: 1,
    root_id: '720575940609924875',
    cell_type: 'Delta7',
    side: 'left',
    sign: -1,
    polarity: 'inhibitory',
    neurotransmitter: 'glutamate',
    neurotransmitter_source: 'known',
    position: { x: 109280, y: 49368, z: 5650 },
    in_degree: 6,
    out_degree: 17,
    in_synapses: 42,
    out_synapses: 171,
  },
  {
    index: 2,
    root_id: '720575940613829900',
    cell_type: 'EPG',
    side: 'left',
    sign: 1,
    polarity: 'excitatory',
    neurotransmitter: 'acetylcholine',
    neurotransmitter_source: 'known',
    position: { x: 120000, y: 30000, z: 4000 },
    in_degree: 12,
    out_degree: 20,
    in_synapses: 120,
    out_synapses: 260,
  },
  {
    index: 3,
    root_id: '720575940604801993',
    cell_type: 'EPG',
    side: 'right',
    sign: 1,
    polarity: 'excitatory',
    neurotransmitter: 'acetylcholine',
    neurotransmitter_source: 'known',
    position: { x: 145000, y: 31000, z: 4200 },
    in_degree: 10,
    out_degree: 14,
    in_synapses: 90,
    out_synapses: 150,
  },
  {
    index: 4,
    root_id: '720575940603823462',
    cell_type: 'PEN_a(PEN1)',
    side: 'left',
    sign: 1,
    polarity: 'excitatory',
    // Nulled out here on purpose (this neuron has real values in the actual
    // dataset) to exercise the "não disponível" UI path instead of filling in
    // something plausible.
    neurotransmitter: null,
    neurotransmitter_source: null,
    position: { x: null, y: null, z: null },
    in_degree: 4,
    out_degree: 5,
    in_synapses: 30,
    out_synapses: 40,
  },
];

export const EDGES: Edge[] = [
  {
    pre_root_id: '720575940613829900',
    post_root_id: '720575940604801993',
    pre_index: 2,
    post_index: 3,
    syn_count: 32,
    sign: 1,
    weight: 32,
    normalised_weight: 0.21,
    polarity: 'excitatory',
    pre_type: 'EPG',
    post_type: 'EPG',
    neuropils: 'EB',
  },
  {
    pre_root_id: '720575940606137004',
    post_root_id: '720575940613829900',
    pre_index: 0,
    post_index: 2,
    syn_count: 8,
    sign: -1,
    weight: -8,
    normalised_weight: -0.03,
    polarity: 'inhibitory',
    pre_type: 'Delta7',
    post_type: 'EPG',
    neuropils: 'PB',
  },
  {
    pre_root_id: '720575940609924875',
    post_root_id: '720575940603823462',
    pre_index: 1,
    post_index: 4,
    syn_count: 6,
    sign: -1,
    weight: -6,
    normalised_weight: -0.034,
    polarity: 'inhibitory',
    pre_type: 'Delta7',
    post_type: 'PEN_a(PEN1)',
    neuropils: 'PB',
  },
];

export const SUMMARY: CircuitSummary = {
  circuit: 'ring_attractor_core',
  title: 'Central complex head-direction (ring attractor) core',
  nt_policy: 'known-first',
  nt_policy_note:
    'Neuron sign prefers the literature-established transmitter (known_nt_primary).',
  n_neurons: 5,
  n_connections: 3,
  n_synapses: 46,
  n_excitatory_neurons: 3,
  n_inhibitory_neurons: 2,
  n_modulatory_neurons: 0,
  cell_types: ['Delta7', 'EPG', 'PEN_a(PEN1)'],
  sides: ['left', 'right'],
  coordinate_space: {
    space: 'FlyWire (FAFB v14.1) voxel coordinates',
    voxel_size_nm: [4, 4, 40],
    note: 'Soma positions from the FlyWire annotation release.',
  },
  synapse_threshold: 5,
  citations: [
    'Dorkenwald, S., Matsliah, A., Sterling, A.R. et al. Neuronal wiring diagram of an adult brain. Nature 634, 124-138 (2024). https://doi.org/10.1038/s41586-024-07558-y',
  ],
  licensing: ['Connectivity dump (Zenodo 10.5281/zenodo.10676866): CC-BY-4.0.'],
  simplifications: [
    'Time is dimensionless: one step is one round of synaptic transmission, not a millisecond.',
    'No conduction delays: every connection transmits in exactly one step.',
    'The circuit is isolated: all input from outside these neurons is absent.',
  ],
  disclaimer:
    'Real connectivity (FlyWire v783), toy dynamics. This model shows how activity can spread through the measured wiring.',
};

export const GRAPH: GraphResponse = { summary: SUMMARY, neurons: NEURONS, edges: EDGES };

export const CELL_TYPES: CellTypeListResponse = {
  circuit: 'ring_attractor_core',
  nt_policy: 'known-first',
  sides: ['left', 'right'],
  cell_types: [
    {
      cell_type: 'Delta7',
      count: 2,
      count_by_side: { left: 1, right: 1 },
      polarity: 'inhibitory',
      root_ids: ['720575940606137004', '720575940609924875'],
    },
    {
      cell_type: 'EPG',
      count: 2,
      count_by_side: { left: 1, right: 1 },
      polarity: 'excitatory',
      root_ids: ['720575940613829900', '720575940604801993'],
    },
    {
      cell_type: 'PEN_a(PEN1)',
      count: 1,
      count_by_side: { left: 1, right: 0 },
      polarity: 'excitatory',
      root_ids: ['720575940603823462'],
    },
  ],
  presets: [
    {
      id: 'epg_left',
      label: 'EPG population (left hemisphere)',
      description: 'The neurons that carry the head-direction bump.',
      source: { root_ids: null, cell_types: ['EPG'], side: 'left', limit: null },
    },
    {
      id: 'delta7',
      label: 'Delta7 population (inhibitory)',
      description: "The circuit's inhibitory population.",
      source: { root_ids: null, cell_types: ['Delta7'], side: null, limit: null },
    },
  ],
};

export const MODEL_DEFAULTS: ModelDefaultsResponse = {
  parameters: {
    model: 'discrete-time leaky integrate-and-fire',
    threshold: 0.2,
    leak: 0.9,
    gain: 1.0,
    refractory_steps: 3,
    noise_std: 0.0,
    seed: 0,
  },
  limits: {
    max_steps: 500,
    max_source_root_ids: 1000,
    max_amplitude: 100,
    max_concurrent_simulations: 4,
  },
  simplifications: SUMMARY.simplifications,
  disclaimer: SUMMARY.disclaimer,
};

export const PROVENANCE: ProvenanceResponse = {
  circuit: 'ring_attractor_core',
  nt_policy: 'known-first',
  provenance: {
    dataset: {
      connectivity: {
        version: '783.0',
        license: 'CC-BY-4.0',
        url: 'https://zenodo.org/records/10676866',
      },
      annotations: {
        repo: 'flyconnectome/flywire_annotations',
        tag: 'v2.1.0',
        url: 'https://github.com/flyconnectome/flywire_annotations/releases/tag/v2.1.0',
      },
    },
  },
  citations: SUMMARY.citations,
  licensing: SUMMARY.licensing,
  simplifications: SUMMARY.simplifications,
  disclaimer: SUMMARY.disclaimer,
};

export const REPORT: SimulationReport = {
  steps: 2,
  neurons: 5,
  stimulated_neurons: 1,
  neurons_that_fired: 3,
  downstream_neurons_that_fired: 2,
  fraction_of_circuit_recruited: 0.6,
  total_spikes: 4,
  neurons_fired_by_cell_type: { EPG: 2, Delta7: 1 },
  first_spike_step_by_cell_type: { EPG: 1, Delta7: 2 },
  peak_step: 2,
  peak_n_spiked: 2,
  final_total_activation: 0.42,
  numerically_finite: true,
  max_abs_membrane: 1.1,
};

export function headerMessage(overrides: Record<string, unknown> = {}) {
  return {
    type: 'header',
    n_neurons: NEURONS.length,
    n_steps: 2,
    n_frames: 3,
    neuron_ids: NEURONS.map((n) => n.root_id),
    metadata: {},
    frame_format: 'dense',
    include_membrane: false,
    stimulated_root_ids: ['720575940613829900'],
    stimulated_indices: [2],
    ...overrides,
  };
}

export function denseFrame(step: number, activation: number[], spiked: boolean[]) {
  return {
    type: 'frame',
    format: 'dense',
    step,
    activation,
    spiked,
    summary: {
      step,
      n_spiked: spiked.filter(Boolean).length,
      fraction_spiked: spiked.filter(Boolean).length / spiked.length,
      total_activation: activation.reduce((a, b) => a + b, 0),
      mean_activation: activation.reduce((a, b) => a + b, 0) / activation.length,
      max_activation: Math.max(...activation),
      mean_membrane: 0,
      max_abs_membrane: 0,
      total_input_current: 0,
    },
  };
}
