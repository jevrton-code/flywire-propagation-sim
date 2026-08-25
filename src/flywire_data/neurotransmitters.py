"""Mapping from predicted neurotransmitter to a connection sign.

The rule is taken verbatim from Dorkenwald et al., Nature 634, 124-138 (2024):

    "As a rule, we assume that cholinergic neurons are excitatory and GABAergic
    and glutamatergic neurons are inhibitory."

(supported there by Molina-Obando et al., eLife 8, e49373 (2019) and
Liu & Wilson, PNAS 110, 10294-10299 (2013).)

The paper states the rule only for those three fast transmitters. The remaining
three transmitters that Eckstein et al. (2024) predict -- serotonin, dopamine
and octopamine -- are neuromodulators whose postsynaptic effect depends on the
receptor expressed by the target neuron and is therefore *not* determined by the
transmitter identity alone. We refuse to guess a sign for them: they are tagged
``modulatory`` and carry weight 0, which makes the assumption auditable instead
of hidden.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Final


class Polarity(IntEnum):
    """Sign applied to every outgoing connection of a neuron."""

    INHIBITORY = -1
    MODULATORY = 0
    EXCITATORY = 1

    @property
    def label(self) -> str:
        return self.name.lower()


#: Fast transmitters with a sign asserted by Dorkenwald et al. (2024).
SIGNED_TRANSMITTERS: Final[dict[str, Polarity]] = {
    "acetylcholine": Polarity.EXCITATORY,
    "gaba": Polarity.INHIBITORY,
    "glutamate": Polarity.INHIBITORY,
}

#: Transmitters predicted by Eckstein et al. (2024) for which the paper asserts
#: no sign. Listed explicitly so an unexpected value raises instead of silently
#: becoming "modulatory".
MODULATORY_TRANSMITTERS: Final[frozenset[str]] = frozenset(
    {"serotonin", "dopamine", "octopamine"}
)

KNOWN_TRANSMITTERS: Final[frozenset[str]] = frozenset(SIGNED_TRANSMITTERS) | MODULATORY_TRANSMITTERS


class UnknownTransmitterError(ValueError):
    """Raised when the annotation table contains a transmitter we cannot classify."""


def polarity_of(top_nt: str | None) -> Polarity:
    """Return the connection sign implied by a neuron's top predicted transmitter.

    Raises:
        UnknownTransmitterError: if ``top_nt`` is empty or not one of the six
            transmitters predicted by Eckstein et al. (2024). We deliberately do
            not fall back to a default sign.
    """
    key = (top_nt or "").strip().lower()
    if not key:
        raise UnknownTransmitterError(
            "neuron has no top_nt prediction; refusing to assign a sign"
        )
    if key in SIGNED_TRANSMITTERS:
        return SIGNED_TRANSMITTERS[key]
    if key in MODULATORY_TRANSMITTERS:
        return Polarity.MODULATORY
    raise UnknownTransmitterError(
        f"unrecognised neurotransmitter {top_nt!r}; expected one of "
        f"{sorted(KNOWN_TRANSMITTERS)}"
    )


def primary_known_transmitter(known_nt: str | None) -> str | None:
    """Extract the small-molecule transmitter from the free-text ``known_nt`` field.

    ``known_nt`` records transmitters and neuropeptides established in the
    literature, as a comma/semicolon separated list, e.g.
    ``"glutamate, proctolin, ecdysis- triggering hormone, bursicon"`` or
    ``"acetylcholine, space blanket"``. We return the first token that is one of
    the six transmitters Eckstein et al. predict, so it is comparable with
    ``top_nt``; neuropeptides and ``*-negative`` assertions are ignored.

    Returns ``None`` when the field is empty or names no such transmitter.
    """
    if not known_nt:
        return None
    for chunk in str(known_nt).replace(";", ",").split(","):
        token = chunk.strip().lower()
        if token in KNOWN_TRANSMITTERS:
            return token
    return None
