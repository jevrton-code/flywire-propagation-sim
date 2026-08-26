"""Guards against the sign rule silently drifting between data and simulation.

`flywire_sim.graph` restates the excitatory/inhibitory/modulatory rule from
`flywire_data.neurotransmitters` instead of importing it, so that the
simulation layer does not depend on the "sign" column a CSV happens to carry
(see the comment above `_SIGN_BY_TRANSMITTER`). That duplication is
deliberate, but nothing else enforces that the two copies agree. If the data
layer ever gains a new recognised transmitter without a matching update here,
the simulation would start raising `UnknownNeurotransmitterError` on
previously valid data instead of failing loudly at import time.
"""

from __future__ import annotations

from flywire_data.neurotransmitters import (
    MODULATORY_TRANSMITTERS,
    SIGNED_TRANSMITTERS,
    Polarity,
)
from flywire_sim.graph import _SIGN_BY_TRANSMITTER


def test_simulation_sign_table_matches_data_layer():
    expected = {name: int(polarity) for name, polarity in SIGNED_TRANSMITTERS.items()}
    expected.update({name: int(Polarity.MODULATORY) for name in MODULATORY_TRANSMITTERS})

    assert _SIGN_BY_TRANSMITTER == expected
