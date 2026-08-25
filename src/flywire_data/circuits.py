"""Curated circuit definitions.

A circuit is a named set of cell types plus the rationale for picking it. Keeping
the rationale next to the selector means the justification cannot drift away from
the code that produces the data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class Circuit:
    slug: str
    title: str
    #: Exact values matched against the resolved cell-type column.
    cell_types: tuple[str, ...]
    #: Minimum number of synapses for a neuron pair to count as connected.
    synapse_threshold: int
    rationale: str
    references: tuple[str, ...]


RING_ATTRACTOR_CORE = Circuit(
    slug="ring_attractor_core",
    title="Central complex head-direction (ring attractor) core",
    cell_types=(
        "EPG",
        "EPGt",
        "PEN_a(PEN1)",
        "PEN_b(PEN2)",
        "PEG",
        "Delta7",
    ),
    synapse_threshold=5,
    rationale=(
        "The fly's head-direction system is the best-characterised recurrent "
        "circuit in the insect brain and the textbook example of a biological ring "
        "attractor: a single 'bump' of activity in the ellipsoid body tracks "
        "heading, EPG neurons carry the bump, PEN neurons shift it in proportion "
        "to angular velocity, PEG neurons feed it back, and Delta7 neurons provide "
        "the global inhibition that keeps exactly one bump alive. That makes it an "
        "unusually good target for a propagation demo: the circuit is strongly "
        "recurrent (so propagation does something more interesting than a "
        "feed-forward cascade), it mixes excitation and inhibition, and its "
        "expected qualitative behaviour is documented, so a viewer can sanity-check "
        "the simulation against published biology. It is also small enough "
        "(~150 neurons, ~2.7k edges) to render and simulate interactively in a "
        "browser, unlike the full ~140k-neuron connectome."
    ),
    references=(
        "Seelig, J.D. & Jayaraman, V. Neural dynamics for landmark orientation and "
        "angular path integration. Nature 521, 186-191 (2015). "
        "https://doi.org/10.1038/nature14446",
        "Green, J., Adachi, A., Shah, K.K. et al. A neural circuit architecture for "
        "angular integration in Drosophila. Nature 546, 101-106 (2017). "
        "https://doi.org/10.1038/nature22343",
        "Turner-Evans, D.B., Jensen, K.T., Ali, S. et al. The neuroanatomical "
        "ultrastructure and function of a biological ring attractor. Neuron 108, "
        "145-163 (2020). https://doi.org/10.1016/j.neuron.2020.08.006",
        "Hulse, B.K., Haberkern, H., Franconville, R. et al. A connectome of the "
        "Drosophila central complex reveals network motifs suitable for flexible "
        "navigation and context-dependent action selection. eLife 10, e66039 "
        "(2021). https://doi.org/10.7554/eLife.66039",
    ),
)


CIRCUITS: Mapping[str, Circuit] = {RING_ATTRACTOR_CORE.slug: RING_ATTRACTOR_CORE}


def get_circuit(slug: str) -> Circuit:
    try:
        return CIRCUITS[slug]
    except KeyError:
        raise KeyError(
            f"unknown circuit {slug!r}; available: {sorted(CIRCUITS)}"
        ) from None
