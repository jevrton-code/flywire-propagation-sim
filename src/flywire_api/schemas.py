"""Request and response models. These are the API contract and its documentation.

Two conventions run through everything here:

1. **``root_id`` is always a string.** FlyWire root ids are 18-digit integers,
   past the 2^53 exact range of a JavaScript ``Number``; sending one as a JSON
   number silently corrupts it in the browser. The simulation package already
   serialises them as strings and the API keeps that everywhere, in both
   directions -- requests accept a string (an integer is accepted too and
   normalised, but a client should not rely on it).
2. **Per-neuron values travel as arrays aligned to a single ordering**, sent
   once in the stream header (``neuron_ids``) and matching the ``index`` field
   of ``GET /api/circuit/neurons``. Frames are then flat arrays, not 153 objects
   with an id repeated in each.

Every numeric input has an explicit bound. The point is not paranoia about
malice, it is that ``steps=999999999`` or ``refractory_steps=-1`` should fail
fast with a readable message instead of hanging the server or blowing up deep
inside numpy.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from flywire_sim.graph import DEFAULT_CIRCUIT

#: Hard ceilings. A 153-neuron circuit at 500 steps is ~76k neuron-steps, which
#: streams in well under a second; the limits exist so a typo cannot turn into an
#: unbounded run holding a worker.
MAX_STEPS = 500
MAX_SOURCE_ROOT_IDS = 1000
MAX_AMPLITUDE = 100.0
#: Pacing is capped so a run cannot hold a concurrency slot indefinitely:
#: MAX_STEPS * MAX_FRAME_INTERVAL_MS is the worst-case wall time of one stream.
MAX_FRAME_INTERVAL_MS = 200

NtPolicy = Literal["known-first", "predicted"]
Normalisation = Literal["in-degree", "global-max", "none"]
FrameFormat = Literal["dense", "delta"]


def _to_root_id(value: Any) -> str:
    text = str(value).strip()
    if not text.isdigit():
        raise ValueError(
            f"{value!r} is not a FlyWire root_id; expected a decimal integer, "
            "sent as a string (18-digit ids do not survive a JavaScript Number)"
        )
    return text


RootId = Annotated[str, Field(examples=["720575940635461550"])]


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #


class SourceSelector(BaseModel):
    """Which neurons receive the stimulus.

    The selectors intersect: ``cell_types=["EPG"]`` with ``side="left"`` means
    left-hemisphere EPG neurons only. At least one selector must be given --
    defaulting to "the whole circuit" would make an empty form stimulate
    everything, which is never what a user meant.
    """

    model_config = ConfigDict(extra="forbid")

    root_ids: list[RootId] | None = Field(
        default=None,
        max_length=MAX_SOURCE_ROOT_IDS,
        description="Explicit FlyWire root ids, as strings. Unknown ids are a 404.",
    )
    cell_types: list[str] | None = Field(
        default=None,
        max_length=64,
        description="Cell types to stimulate, e.g. ['EPG']. See GET /api/circuit/cell-types.",
    )
    side: Literal["left", "right"] | None = Field(
        default=None, description="Restrict the selection to one hemisphere."
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=MAX_SOURCE_ROOT_IDS,
        description=(
            "Stimulate at most this many of the selected neurons. Deterministic: "
            "the first N in the circuit's canonical ordering."
        ),
    )

    @field_validator("root_ids", mode="before")
    @classmethod
    def _normalise_root_ids(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int)):
            raise ValueError("root_ids must be a list of root id strings, not a single value")
        return [_to_root_id(v) for v in value]

    @field_validator("cell_types", mode="before")
    @classmethod
    def _normalise_cell_types(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [value]
        return value

    @model_validator(mode="after")
    def _require_a_selector(self) -> "SourceSelector":
        if not self.root_ids and not self.cell_types and not self.side:
            raise ValueError(
                "give at least one of root_ids, cell_types or side; refusing to "
                "default to stimulating the entire circuit"
            )
        return self

    def as_int_root_ids(self) -> list[int] | None:
        return [int(r) for r in self.root_ids] if self.root_ids else None


class StimulusSpec(BaseModel):
    """Shape of the injected current.

    This stands in for input from outside the subgraph; it is an explicit
    experimental perturbation, not a model of a real input pathway (see
    :class:`flywire_sim.model.Stimulus`).
    """

    model_config = ConfigDict(extra="forbid")

    amplitude: float = Field(
        default=1.0,
        gt=0.0,
        le=MAX_AMPLITUDE,
        description="Current added per step, in the same units as synaptic drive.",
    )
    start: int = Field(default=1, ge=1, le=MAX_STEPS, description="First step (1-based).")
    duration: int = Field(default=6, ge=1, le=MAX_STEPS, description="Length in steps.")


class ModelParameters(BaseModel):
    """Overrides for :class:`flywire_sim.model.LIFParameters`. All optional.

    Unset fields keep the simulation package's defaults, which are engineering
    choices tuned for legible dynamics on this graph, not biological
    measurements. ``GET /api/model/defaults`` returns the current values.
    """

    model_config = ConfigDict(extra="forbid")

    threshold: float | None = Field(default=None, gt=0.0, le=100.0)
    leak: float | None = Field(default=None, ge=0.0, le=1.0)
    v_reset: float | None = Field(default=None, ge=-100.0, le=100.0)
    v_min: float | None = Field(default=None, ge=-100.0, le=0.0)
    v_max: float | None = Field(default=None, gt=0.0, le=1000.0)
    refractory_steps: int | None = Field(default=None, ge=0, le=MAX_STEPS)
    gain: float | None = Field(default=None, ge=0.0, le=1000.0)
    trace_decay: float | None = Field(default=None, ge=0.0, lt=1.0)
    noise_std: float | None = Field(default=None, ge=0.0, le=100.0)
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    weight_normalisation: Normalisation | None = None

    def overrides(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class SimulationRequest(BaseModel):
    """Everything needed to run one propagation.

    Sent as the JSON body of ``POST /api/simulations``, or as the first message
    on ``WS /ws/simulate`` (wrapped in ``{"action": "start", "request": {...}}``,
    though a bare request object is accepted too).
    """

    model_config = ConfigDict(extra="forbid")

    circuit: str = Field(default=DEFAULT_CIRCUIT, max_length=128)
    nt_policy: NtPolicy = Field(
        default="known-first",
        description=(
            "How each neuron's excitatory/inhibitory sign is decided. 'known-first' "
            "prefers the literature transmitter (Turner-Evans et al. 2020); "
            "'predicted' reproduces the dataset's automatic predictions."
        ),
    )
    source: SourceSelector
    stimulus: StimulusSpec = Field(default_factory=StimulusSpec)
    params: ModelParameters = Field(default_factory=ModelParameters)
    steps: int = Field(
        default=40, ge=1, le=MAX_STEPS, description="Number of update steps to simulate."
    )
    include_membrane: bool = Field(
        default=True,
        description="Include the membrane variable in each frame. Set false to halve frame size.",
    )
    frame_format: FrameFormat = Field(
        default="dense",
        description=(
            "'dense' sends every neuron's value in every frame. 'delta' sends only "
            "the entries that changed since the previous frame (frame 0 is always "
            "dense, as the baseline). See the /ws/simulate docs."
        ),
    )
    frame_interval_ms: int = Field(
        default=0,
        ge=0,
        le=MAX_FRAME_INTERVAL_MS,
        description=(
            "Optional server-side pacing between streamed frames, in milliseconds. "
            "0 (the default) streams as fast as the frames are computed and lets the "
            "client control playback speed, which is usually what you want. "
            "WebSocket only; ignored by POST /api/simulations."
        ),
    )

    @model_validator(mode="after")
    def _stimulus_must_fit_the_run(self) -> "SimulationRequest":
        if self.stimulus.start > self.steps:
            raise ValueError(
                f"stimulus.start ({self.stimulus.start}) is after the end of the run "
                f"(steps={self.steps}); no current would ever be injected"
            )
        return self


class StartCommand(BaseModel):
    """WebSocket control message that launches a run."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["start"] = "start"
    request: SimulationRequest


class CancelCommand(BaseModel):
    """WebSocket control message that stops the run in progress."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["cancel"] = "cancel"


# --------------------------------------------------------------------------- #
# Responses -- circuit
# --------------------------------------------------------------------------- #


class Position(BaseModel):
    """Soma position in FlyWire voxel coordinates (see ``coordinate_space``)."""

    x: int | None
    y: int | None
    z: int | None


class Neuron(BaseModel):
    index: int = Field(description="Position in every per-neuron array the simulation streams.")
    root_id: RootId
    cell_type: str | None
    side: str | None
    sign: int = Field(description="+1 excitatory, -1 inhibitory, 0 modulatory (weight 0).")
    polarity: str | None
    neurotransmitter: str | None
    neurotransmitter_source: str | None = Field(
        description="'known' (literature) or 'predicted' (Eckstein et al. 2024 classifier)."
    )
    position: Position
    in_degree: int
    out_degree: int
    in_synapses: int
    out_synapses: int


class Edge(BaseModel):
    pre_root_id: RootId
    post_root_id: RootId
    pre_index: int
    post_index: int
    syn_count: int = Field(description="Synapses in the connection, summed over neuropils.")
    sign: int
    weight: float = Field(description="Signed synapse count (sign * syn_count).")
    normalised_weight: float = Field(
        description="Weight under the default 'in-degree' normalisation, as integrated."
    )
    polarity: str | None
    pre_type: str | None
    post_type: str | None
    neuropils: str | None


class CellTypeOption(BaseModel):
    cell_type: str
    count: int
    count_by_side: dict[str, int]
    polarity: str = Field(description="'excitatory', 'inhibitory', 'modulatory' or 'mixed'.")
    root_ids: list[RootId]


class StimulusPreset(BaseModel):
    """A ready-made source selection for the frontend's picker."""

    id: str
    label: str
    description: str
    source: SourceSelector


class CoordinateSpace(BaseModel):
    space: str
    voxel_size_nm: list[int]
    note: str


class CircuitSummary(BaseModel):
    """Counts, provenance and honesty block for the loaded subgraph."""

    circuit: str
    title: str | None
    nt_policy: str
    nt_policy_note: str | None
    n_neurons: int
    n_connections: int
    n_synapses: int
    n_excitatory_neurons: int | None
    n_inhibitory_neurons: int | None
    n_modulatory_neurons: int | None
    cell_types: list[str]
    sides: list[str]
    coordinate_space: CoordinateSpace
    synapse_threshold: int | None
    citations: list[str]
    licensing: list[str]
    simplifications: list[str] = Field(
        description="What the model is NOT. Show this to the user; do not hide it."
    )
    disclaimer: str


class NeuronListResponse(BaseModel):
    circuit: str
    nt_policy: str
    n_neurons: int
    coordinate_space: CoordinateSpace
    neurons: list[Neuron]


class EdgeListResponse(BaseModel):
    circuit: str
    nt_policy: str
    n_connections: int
    weight_normalisation: str = Field(
        description="Normalisation used for 'normalised_weight' in each edge."
    )
    edges: list[Edge]


class GraphResponse(BaseModel):
    """Everything needed to draw the static graph in a single round trip."""

    summary: CircuitSummary
    neurons: list[Neuron]
    edges: list[Edge]


class CellTypeListResponse(BaseModel):
    circuit: str
    nt_policy: str
    cell_types: list[CellTypeOption]
    sides: list[str]
    presets: list[StimulusPreset]


class ProvenanceResponse(BaseModel):
    """Where the data came from, verbatim from the data layer's metadata."""

    circuit: str
    nt_policy: str
    provenance: dict[str, Any] = Field(
        description="GraphProvenance.to_dict() from flywire_sim, including the dataset block."
    )
    citations: list[str]
    licensing: list[str]
    simplifications: list[str]
    disclaimer: str


class LimitsBlock(BaseModel):
    max_steps: int
    max_source_root_ids: int
    max_amplitude: float
    max_concurrent_simulations: int


class ModelDefaultsResponse(BaseModel):
    parameters: dict[str, Any] = Field(
        description="LIFParameters().to_dict(): the defaults a request inherits."
    )
    limits: LimitsBlock
    simplifications: list[str]
    disclaimer: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    default_circuit: str
    available_circuits: list[str]
    loaded: list[str]


# --------------------------------------------------------------------------- #
# Responses -- simulation
# --------------------------------------------------------------------------- #


class StepSummary(BaseModel):
    """Aggregate statistics for one step (``StepState.summary()``)."""

    step: int
    n_spiked: int
    fraction_spiked: float
    total_activation: float
    mean_activation: float
    max_activation: float
    mean_membrane: float
    max_abs_membrane: float
    total_input_current: float


class SparseVector(BaseModel):
    """Changed entries of a per-neuron array: ``values[k]`` belongs to ``indices[k]``."""

    indices: list[int]
    values: list[float]


class DenseFrame(BaseModel):
    """One time step, with every neuron's value. Arrays align to ``neuron_ids``."""

    format: Literal["dense"]
    step: int = Field(description="0 is the resting state before any update.")
    activation: list[float] = Field(
        description="Exponentially filtered spike trace in [0, 1]: the display signal."
    )
    spiked: list[bool]
    membrane: list[float] | None = Field(
        default=None, description="Absent when the request set include_membrane=false."
    )
    summary: StepSummary


class DeltaFrame(BaseModel):
    """One time step, carrying only what changed since the previous frame.

    ``activation`` and ``membrane`` are diffs: apply ``values[k]`` at
    ``indices[k]`` to your local copy. ``spiked`` is *not* a diff -- it is the
    full list of indices spiking on this step, which is already sparse.
    Frame 0 of a stream is always a :class:`DenseFrame` baseline.
    """

    format: Literal["delta"]
    step: int
    activation: SparseVector
    spiked: list[int]
    membrane: SparseVector | None = None
    summary: StepSummary


Frame = Annotated[DenseFrame | DeltaFrame, Field(discriminator="format")]


class SimulationHeader(BaseModel):
    """Sent once, before any frame: the ordering and everything about the run."""

    n_neurons: int
    n_steps: int
    n_frames: int = Field(description="n_steps + 1: frame 0 is the resting state.")
    neuron_ids: list[RootId] = Field(
        description="Canonical ordering of every per-neuron array in every frame."
    )
    metadata: dict[str, Any] = Field(
        description=(
            "LIFSimulation.describe(): parameters, stimuli, graph provenance, "
            "simplifications and disclaimer."
        )
    )
    frame_format: FrameFormat
    include_membrane: bool
    stimulated_root_ids: list[RootId]
    stimulated_indices: list[int]


class SimulationReport(BaseModel):
    """What the run did, computed after the last frame."""

    steps: int
    neurons: int
    stimulated_neurons: int
    neurons_that_fired: int
    downstream_neurons_that_fired: int
    fraction_of_circuit_recruited: float
    total_spikes: int
    neurons_fired_by_cell_type: dict[str, int] = Field(
        description="Neurons of each cell type that fired at least once (not a spike count)."
    )
    first_spike_step_by_cell_type: dict[str, int] = Field(
        description="Earliest step at which any neuron of each cell type fired."
    )
    peak_step: int | None
    peak_n_spiked: int | None
    final_total_activation: float
    numerically_finite: bool = Field(
        description="False means the run produced NaN/inf; treat the result as invalid."
    )
    max_abs_membrane: float


class SimulationResponse(BaseModel):
    """Full non-streaming run: header, every frame, and the report."""

    header: SimulationHeader
    frames: list[Frame]
    report: SimulationReport
