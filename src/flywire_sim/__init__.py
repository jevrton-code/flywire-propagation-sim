"""Activation propagation over a real FlyWire connectome subgraph.

Pure Python, no web framework, no I/O beyond reading the committed CSVs. The
backend phase consumes :class:`~flywire_sim.result.SimulationResult`; nothing in
this package knows or cares how the result is displayed.

Quick start::

    from flywire_sim import load_graph, simulate

    graph = load_graph()                       # 153 neurons, 2695 connections
    result = simulate(graph, cell_type="EPG", side="left", steps=40)
    print(result.summary_frame())

CLI::

    python -m flywire_sim.run --source-type EPG --source-side left --steps 40

The model is a discrete-time leaky integrate-and-fire network. The wiring is
real; the dynamics are a caricature. Read the :mod:`flywire_sim.model` docstring
before describing this as "biologically realistic" -- it lists exactly what is
simplified away, and :data:`flywire_sim.model.SIMPLIFICATIONS` ships the same
list inside every result's metadata.
"""

from .graph import (
    KNOWN_NT_REFERENCE,
    GraphProvenance,
    SimulationGraph,
    UnknownNeurotransmitterError,
    build_graph,
    load_graph,
)
from .model import SIMPLIFICATIONS, LIFParameters, LIFSimulation, Stimulus, simulate
from .result import SimulationResult, StepState

__all__ = [
    "KNOWN_NT_REFERENCE",
    "SIMPLIFICATIONS",
    "GraphProvenance",
    "LIFParameters",
    "LIFSimulation",
    "SimulationGraph",
    "SimulationResult",
    "StepState",
    "Stimulus",
    "UnknownNeurotransmitterError",
    "build_graph",
    "load_graph",
    "simulate",
]
