"""Discrete-time leaky integrate-and-fire propagation over the connectome subgraph.

What this is
------------
A **discrete-time, dimensionless, leaky integrate-and-fire (LIF) network**. Each
neuron holds a scalar membrane variable ``V``. On every step it leaks a fixed
fraction of ``V``, adds the synaptic drive from whichever neurons fired on the
previous step, and emits a binary spike if ``V`` crosses a threshold, after
which ``V`` is reset and the neuron is briefly refractory.

Why LIF and not a linear propagation model
-------------------------------------------
A linear model (``a[t+1] = leak * a[t] + W @ a[t]``) is simpler to write, but on
a *recurrent* graph its fate is decided entirely by the spectral radius of
``W``: slightly too large and activation diverges exponentially, slightly too
small and it dies out. There is no interesting middle. Since the whole point of
choosing the head-direction circuit was that it is strongly recurrent (49% of
its edges are reciprocal), a linear model would have to be tuned right at the
edge of instability to show anything, and any change to the data would push it
off that edge.

LIF is barely more complex and is bounded *structurally* rather than by tuning:
the only thing a neuron transmits is a binary spike, so the drive arriving at
neuron ``j`` on any step is at most ``gain * sum_i |w[i, j]|`` no matter what
the rest of the network is doing. With the default in-degree normalisation that
ceiling is exactly ``gain``. Combined with the reset and the explicit clamp on
``V``, the state cannot run away. Spikes also give the frontend a natural
discrete event ("this neuron fired at step t") instead of a continuous number
that needs a colour scale invented for it.

What this is NOT -- read before describing this as "biologically realistic"
---------------------------------------------------------------------------
The connectivity is real. The dynamics are a caricature. Specifically:

1. **Time is dimensionless.** One step is "one round of synaptic transmission",
   not a millisecond. Nothing here is calibrated against recorded fly data, so
   the simulation cannot make claims about real timescales.
2. **No conduction delays.** Every connection transmits in exactly one step.
   Real axonal and synaptic delays differ between pathways.
3. **No real membrane time constant.** ``leak`` is a per-step decay factor
   chosen for stable, watchable dynamics, not a measured tau_m. It is exposed as
   a parameter precisely so nobody mistakes it for a measured constant.
4. **No synaptic plasticity.** Weights are fixed for the whole run: no
   short-term depression/facilitation, no STDP, no homeostasis.
5. **No neurotransmitter-specific or receptor-specific effects.** Inhibition is
   purely subtractive current. Real fly inhibition can be shunting, and receptor
   kinetics (nicotinic vs. muscarinic, GluCl, GABA-A/B) differ in sign duration
   and timescale. All of that collapses into one signed scalar.
6. **No dendritic structure, no spatial compartments, no ion channels.** Each
   neuron is a single scalar. There is no spike generation mechanism beyond a
   threshold comparison.
7. **No spontaneous/background activity** unless ``noise_std`` is set, and the
   noise is plain Gaussian current with no biophysical justification.
8. **No adaptation or bursting.**
9. **Rate coding is not modelled.** A spike is an event, not a firing rate; the
   ``activation`` trace in the output is a smoothing filter for visualisation,
   not a physiological firing rate in Hz.
10. The circuit is isolated from the rest of the brain, and all the dataset-level
    simplifications in ``data/README.md`` §6.2 still apply.

The honest one-line summary: *real wiring, toy dynamics.* This can show how
activity spreads through the measured connectivity. It cannot predict what a
fly's neurons actually do.

Parameter choices
-----------------
Every default below is an **engineering choice tuned for stable, legible
dynamics on this graph**, not a biological measurement. None of them are
presented as measured constants, and all are overridable. The rationale for each
is in :class:`LIFParameters`.

They were picked by sweeping ``threshold`` x ``leak`` x ``refractory_steps`` and
looking for the regime described below. The sweep is reproducible from the CLI;
nothing was fitted to data.

What the defaults actually do on this circuit
----------------------------------------------
Measured, not asserted -- these are outputs of the code in this file with
``LIFParameters()`` and the default 6-step, amplitude-1.0 stimulus:

* Stimulating the **24 left-hemisphere** ``EPG`` neurons recruits 146 of the 153
  neurons and every one of the six cell types. Downstream types (``PEG``,
  ``PEN_a``, ``PEN_b``, ``Delta7``) first fire at step 2, activity reverberates
  for about 30 steps, and the circuit falls completely silent by step ~32.
* Stimulating **one** ``EPG`` neuron is much weaker, and that is a real property
  of the normalisation rather than a bug: with in-degree normalisation a single
  presynaptic partner carries a median 4% of its target's synaptic input, so it
  can only recruit partners for which that one connection is a large fraction of
  their input. 41 of the 47 ``EPG`` neurons recruit at least one direct partner
  (median 2, usually ``PEG`` and ``Delta7``); the other 6 recruit none. A handful
  of well-connected ``EPG`` neurons do set off the full cascade.
* Lowering ``refractory_steps`` to 0 or 1, or ``threshold`` below ~0.15 while
  keeping a short refractory period, pushes the circuit into a self-sustaining
  saturated regime where a large fraction of neurons fire every other step
  indefinitely. It stays bounded -- it just stops being interesting.

The saturating regime is not a bug, and it is worth being explicit about why it
exists: the subgraph holds 113 excitatory neurons against 40 inhibitory ones and
is cut off from every input outside it, including the ``ER`` ring neurons that
drive and constrain the real circuit. An isolated, excitation-dominated
recurrent network saturating is the expected outcome.

**This model does not reproduce the ring-attractor bump.** A single localised
activity bump is the circuit's actual function, and getting one requires tuning
the excitation/inhibition balance far more carefully than a simple, auditable
propagation model should. What is shown here is how activation spreads through
the measured wiring, nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

import numpy as np

from .graph import Normalisation, SimulationGraph
from .result import SimulationResult, StepState

# --------------------------------------------------------------------------- #
# Parameters
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LIFParameters:
    """Tunable constants of the discrete-time LIF model.

    None of these are biological measurements. They are dimensionless
    engineering parameters, chosen so the model is stable and its behaviour is
    easy to reason about on this particular graph.

    Attributes:
        threshold: Membrane level at which a neuron fires. With the default
            ``"in-degree"`` normalisation and ``gain=1``, synaptic drive is
            literally "the fraction of this neuron's total synaptic input that is
            active this step", so ``threshold`` reads as *"fire when this much of
            my input is simultaneously active"* (possibly summed over a few steps
            thanks to the leak). Default 0.2: in this graph a single connection
            carries a median 0.04 and at most 0.55 of its target's input, so 0.2
            sits above "one average partner fired once" and below "one unusually
            strong partner fired once" -- weak inputs must summate, exceptionally
            strong ones can act alone. Not a measured spike threshold in mV.
        leak: Fraction of the membrane variable carried over to the next step.
            0.0 means no temporal summation at all (pure one-step propagation),
            1.0 means a perfect integrator that never forgets. Default 0.9
            decays to ~1/e over roughly 9.5 steps, so subthreshold input from a
            weak connection can summate over several steps instead of being
            forgotten immediately -- which is what lets a *single* stimulated
            neuron recruit anything at all in this graph. This is a *per-step
            decay factor*, not a membrane time constant tau_m in ms.
        v_reset: Membrane value after a spike. Default 0.0 (reset to rest).
        v_min: Floor on the membrane variable. Without it, a neuron sitting under
            heavy Delta7 inhibition would drift arbitrarily negative and be
            silenced for the rest of the run, which is a numerical artefact, not
            biology. Default -1.0 bounds hyperpolarisation to roughly the same
            scale as maximal excitation.
        v_max: Ceiling on the membrane variable, purely a numerical guard. In
            normal operation a neuron spikes and resets long before reaching it;
            if it is ever hit, something upstream is wrong. Default 10.0.
        refractory_steps: Steps a neuron cannot fire for after firing. Default 3.
            This is the single most important knob for keeping the circuit out of
            runaway self-excitation, and that is exactly why it is not 1: this
            subgraph is 113 excitatory neurons against 40 inhibitory ones, cut
            off from every inhibitory input outside it, so without a duty-cycle
            limit a strong enough stimulus drives it into permanent saturation.
            Read 3 as a stand-in for all the mechanisms this model does not
            have (spike-frequency adaptation, short-term synaptic depression,
            and the missing external inhibition), not as a measured absolute
            refractory period. Set it to 0 or 1 to see the saturating regime.
        gain: Global multiplier on synaptic drive. Default 1.0, so ``threshold``
            carries the interpretation described above. Raise it to make the
            circuit more excitable without touching the threshold.
        trace_decay: Decay of the visualisation ``activation`` trace, an
            exponentially filtered spike train in [0, 1]. Default 0.6 (a spike
            stays visible for ~4-5 steps). Affects the reported ``activation``
            only; it never feeds back into the dynamics.
        noise_std: Standard deviation of optional Gaussian current injected into
            every neuron every step. Default 0.0, which makes the whole
            simulation deterministic. Any non-zero value uses ``seed``, so runs
            stay reproducible.
        seed: RNG seed used when ``noise_std > 0``.
        weight_normalisation: How raw synapse counts are rescaled; see
            :meth:`flywire_sim.graph.SimulationGraph.normalised_weights`.
    """

    threshold: float = 0.20
    leak: float = 0.9
    v_reset: float = 0.0
    v_min: float = -1.0
    v_max: float = 10.0
    refractory_steps: int = 3
    gain: float = 1.0
    trace_decay: float = 0.6
    noise_std: float = 0.0
    seed: int = 0
    weight_normalisation: Normalisation = "in-degree"

    def __post_init__(self) -> None:
        if self.threshold <= 0:
            raise ValueError("threshold must be > 0")
        if not 0.0 <= self.leak <= 1.0:
            raise ValueError("leak must be in [0, 1]; >1 would integrate divergently")
        if not 0.0 <= self.trace_decay < 1.0:
            raise ValueError("trace_decay must be in [0, 1)")
        if self.refractory_steps < 0:
            raise ValueError("refractory_steps must be >= 0")
        if self.gain < 0:
            raise ValueError("gain must be >= 0")
        if self.noise_std < 0:
            raise ValueError("noise_std must be >= 0")
        if self.v_min > self.v_reset:
            raise ValueError("v_min must be <= v_reset")
        if self.v_max <= self.threshold:
            raise ValueError("v_max must exceed threshold, it is only a numerical guard")

    def to_dict(self) -> dict:
        return {
            "model": "discrete-time leaky integrate-and-fire",
            "threshold": self.threshold,
            "leak": self.leak,
            "v_reset": self.v_reset,
            "v_min": self.v_min,
            "v_max": self.v_max,
            "refractory_steps": self.refractory_steps,
            "gain": self.gain,
            "trace_decay": self.trace_decay,
            "noise_std": self.noise_std,
            "seed": self.seed,
            "weight_normalisation": self.weight_normalisation,
            "units": (
                "dimensionless; one step is one round of synaptic transmission, "
                "not a millisecond"
            ),
        }

    def with_(self, **changes) -> "LIFParameters":
        return replace(self, **changes)


@dataclass(frozen=True)
class Stimulus:
    """External current injected into a set of neurons over a window of steps.

    This stands in for everything outside the subgraph -- in the real fly, the
    head-direction bump is set by ``ER`` ring neurons carrying visual landmark
    information, and none of those neurons are in this graph (``data/README.md``
    §6.2, item 6). The stimulus is therefore an explicit experimental
    perturbation, not a model of a real input pathway.

    Attributes:
        targets: ``root_id`` values receiving the current.
        amplitude: Current added per step, in the same units as synaptic drive.
            The default 1.0 exceeds the default threshold, so a stimulated neuron
            fires on the first step it is stimulated.
        start: First update step (1-based) at which the current is applied.
        duration: Number of consecutive steps the current is applied for.
    """

    targets: tuple[int, ...]
    amplitude: float = 1.0
    start: int = 1
    duration: int = 6

    def __post_init__(self) -> None:
        if not self.targets:
            raise ValueError("stimulus has no targets")
        if self.start < 1:
            raise ValueError("stimulus start is 1-based; must be >= 1")
        if self.duration < 1:
            raise ValueError("stimulus duration must be >= 1")

    def is_active(self, step: int) -> bool:
        return self.start <= step < self.start + self.duration

    def to_dict(self) -> dict:
        return {
            "targets": [str(t) for t in self.targets],
            "amplitude": self.amplitude,
            "start": self.start,
            "duration": self.duration,
        }


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #


@dataclass
class _State:
    membrane: np.ndarray
    spiked: np.ndarray
    activation: np.ndarray
    refractory: np.ndarray


class LIFSimulation:
    """Runs :class:`LIFParameters` dynamics over a :class:`SimulationGraph`.

    The update applied on every step ``t``, with ``s`` the previous step's spike
    vector and ``W`` the normalised signed weight matrix::

        I[j]  = gain * sum_i W[i, j] * s[i]  +  stimulus[j, t]  +  noise
        V[j]  = clip(leak * V[j] + I[j], v_min, v_max)
        V[j]  = v_reset                       if j is refractory
        s'[j] = (V[j] >= threshold) and not refractory
        V[j]  = v_reset                       if s'[j]
        a[j]  = trace_decay * a[j] + (1 - trace_decay) * s'[j]

    ``a`` is the visualisation trace only; it never feeds back.

    Use :meth:`run` for a complete run, or :meth:`iter_steps` to consume states
    one at a time (which is what a streaming backend will want).
    """

    def __init__(
        self,
        graph: SimulationGraph,
        params: LIFParameters | None = None,
    ):
        self.graph = graph
        self.params = params or LIFParameters()
        self._weights = graph.normalised_weights(self.params.weight_normalisation)
        # Pre-transpose once: incoming[j] = sum_i W[i, j] * s[i] == (W.T @ s)[j].
        self._weights_in = np.ascontiguousarray(self._weights.T)

    # -- stimulus resolution ---------------------------------------------- #

    def make_stimulus(
        self,
        *,
        root_ids: Sequence[int] | None = None,
        cell_type: str | Sequence[str] | None = None,
        side: str | None = None,
        amplitude: float = 1.0,
        start: int = 1,
        duration: int = 3,
    ) -> Stimulus:
        """Build a :class:`Stimulus` from a user-facing selector."""
        targets = self.graph.select(root_ids=root_ids, cell_type=cell_type, side=side)
        return Stimulus(
            targets=tuple(targets),
            amplitude=amplitude,
            start=start,
            duration=duration,
        )

    # -- integration ------------------------------------------------------- #

    def iter_steps(self, stimuli: Sequence[Stimulus], steps: int):
        """Yield one :class:`StepState` per time step, starting at the rest state.

        Yields ``steps + 1`` states: index 0 is the resting state before any
        update (all zeros), then one state per update step.
        """
        if steps < 0:
            raise ValueError("steps must be >= 0")
        p = self.params
        n = self.graph.n_neurons

        state = _State(
            membrane=np.zeros(n),
            spiked=np.zeros(n, dtype=bool),
            activation=np.zeros(n),
            refractory=np.zeros(n, dtype=int),
        )
        rng = np.random.default_rng(p.seed)

        stimulus_vectors = self._stimulus_vectors(stimuli, steps)

        yield self._snapshot(0, state, np.zeros(n))

        for t in range(1, steps + 1):
            drive = p.gain * (self._weights_in @ state.spiked.astype(np.float64))
            current = drive + stimulus_vectors[t]
            if p.noise_std > 0:
                current = current + rng.normal(0.0, p.noise_std, size=n)

            membrane = np.clip(p.leak * state.membrane + current, p.v_min, p.v_max)

            refractory_now = state.refractory > 0
            membrane[refractory_now] = p.v_reset

            spiked = (membrane >= p.threshold) & ~refractory_now
            membrane[spiked] = p.v_reset

            refractory = np.maximum(state.refractory - 1, 0)
            refractory[spiked] = p.refractory_steps

            activation = p.trace_decay * state.activation + (1.0 - p.trace_decay) * spiked

            state = _State(membrane, spiked, activation, refractory)
            yield self._snapshot(t, state, current)

    def run(self, stimuli: Sequence[Stimulus] | Stimulus, steps: int = 50) -> SimulationResult:
        """Run the full simulation and return every step in one object."""
        if isinstance(stimuli, Stimulus):
            stimuli = [stimuli]
        states = list(self.iter_steps(stimuli, steps))
        return SimulationResult(
            neuron_ids=self.graph.neuron_ids,
            steps=states,
            metadata=self.describe(stimuli, steps),
        )

    # -- helpers ----------------------------------------------------------- #

    def _stimulus_vectors(self, stimuli: Sequence[Stimulus], steps: int) -> np.ndarray:
        """Dense ``(steps + 1, n)`` array of injected current. Row 0 is unused."""
        vectors = np.zeros((steps + 1, self.graph.n_neurons))
        for stimulus in stimuli:
            idx = self.graph.indices_of(stimulus.targets)
            for t in range(1, steps + 1):
                if stimulus.is_active(t):
                    vectors[t, idx] += stimulus.amplitude
        return vectors

    def _snapshot(self, step: int, state: _State, current: np.ndarray) -> StepState:
        return StepState(
            step=step,
            membrane=state.membrane.copy(),
            spiked=state.spiked.copy(),
            activation=state.activation.copy(),
            input_current=current.copy(),
        )

    def describe(self, stimuli: Sequence[Stimulus], steps: int) -> dict:
        """Metadata block shipped alongside the time series."""
        provenance = self.graph.provenance
        return {
            "parameters": self.params.to_dict(),
            "stimuli": [s.to_dict() for s in stimuli],
            "steps": steps,
            "graph": provenance.to_dict() if provenance is not None else {},
            "simplifications": list(SIMPLIFICATIONS),
            "disclaimer": (
                "Real connectivity (FlyWire v783), toy dynamics. This model shows "
                "how activity can spread through the measured wiring; it is not "
                "calibrated against physiological recordings and does not predict "
                "what real neurons do."
            ),
        }


#: Machine-readable version of the "what this is NOT" list in the module
#: docstring, so the honesty travels with the output instead of living only in
#: a docstring the frontend never reads.
SIMPLIFICATIONS: tuple[str, ...] = (
    "Time is dimensionless: one step is one round of synaptic transmission, not a millisecond.",
    "No conduction delays: every connection transmits in exactly one step.",
    "'leak' is a per-step decay factor chosen for stable dynamics, not a measured membrane time constant.",
    "No synaptic plasticity: weights are fixed (no short-term depression/facilitation, no STDP).",
    "No receptor- or neurotransmitter-specific effects: inhibition is purely subtractive, never shunting.",
    "Excitatory and inhibitory synapses are weighted identically per synapse, although inhibitory "
    "conductances in the fly can be substantially larger (data/README.md section 6.2, item 3).",
    "The model does not reproduce the ring-attractor bump; it shows how activation spreads through the "
    "measured wiring, not the circuit's computational function.",
    "Each neuron is a single scalar: no dendritic compartments, no ion channels, no spike-generation biophysics.",
    "No spontaneous background activity unless noise_std > 0, and that noise has no biophysical justification.",
    "No spike-frequency adaptation and no bursting.",
    "The reported 'activation' is a smoothing filter over spikes for visualisation, not a firing rate in Hz.",
    "The circuit is isolated: all input from outside these neurons (e.g. ER ring neurons) is absent.",
    "Dataset-level simplifications still apply: 5-synapse threshold, Dale's law, weight = synapse count "
    "(see data/README.md section 6.2).",
)


def simulate(
    graph: SimulationGraph,
    *,
    root_ids: Sequence[int] | None = None,
    cell_type: str | Sequence[str] | None = None,
    side: str | None = None,
    steps: int = 50,
    params: LIFParameters | None = None,
    amplitude: float = 1.0,
    stim_start: int = 1,
    stim_duration: int = 6,
) -> SimulationResult:
    """One-call convenience wrapper: select a source, stimulate it, run.

    Example::

        graph = load_graph()
        result = simulate(graph, cell_type="EPG", side="left", steps=40)
        print(result.summary_frame())
    """
    simulation = LIFSimulation(graph, params)
    stimulus = simulation.make_stimulus(
        root_ids=root_ids,
        cell_type=cell_type,
        side=side,
        amplitude=amplitude,
        start=stim_start,
        duration=stim_duration,
    )
    return simulation.run(stimulus, steps=steps)
