"""Structured, serialisable output of a propagation run.

The simulation is deliberately agnostic about how it will be displayed. What it
produces is a **time series of per-neuron state**, offered in three shapes so
that a consumer can pick the cheapest one:

``result.step_payloads()``
    One JSON-ready dict per time step, with per-neuron values as parallel arrays
    aligned to ``result.neuron_ids``. This is the shape a WebSocket stream wants:
    the neuron ordering is sent once in the header, and each frame is a handful
    of flat arrays.

``result.to_frame()`` / ``result.to_records()``
    Long format, one row per ``(step, neuron)``. Convenient for analysis and for
    dumping to CSV; roughly ``n_steps * n_neurons`` rows, so it is the expensive
    option (a 50-step run over 153 neurons gives 7,803 rows).

``result.summary_frame()`` / ``result.summaries()``
    One row per time step with aggregate statistics. This is what a CLI or a
    plot header should use.

A note on ``root_id`` and JSON: FlyWire root IDs are 18-digit integers, which
exceed the 2^53 exact-integer range of a JavaScript ``Number``. Every JSON
payload therefore emits them as **strings**. The Python objects keep them as
``int``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StepState:
    """State of every neuron at one time step.

    All arrays are aligned to :attr:`SimulationResult.neuron_ids`.

    Attributes:
        step: 0 for the resting state, then 1..N for each update step.
        membrane: Membrane variable after the update (dimensionless).
        spiked: ``True`` for neurons that crossed threshold on this step.
        activation: Exponentially filtered spike trace in [0, 1]. This is the
            display-friendly signal: bounded by construction, smooth over time,
            and with no feedback into the dynamics.
        input_current: Total current the neuron received on this step (synaptic
            drive + stimulus + noise). Useful for debugging why something did or
            did not fire.
    """

    step: int
    membrane: np.ndarray
    spiked: np.ndarray
    activation: np.ndarray
    input_current: np.ndarray

    def n_spiked(self) -> int:
        return int(self.spiked.sum())

    def summary(self) -> dict[str, float | int]:
        """Aggregate statistics for this step."""
        return {
            "step": self.step,
            "n_spiked": self.n_spiked(),
            "fraction_spiked": float(self.spiked.mean()) if self.spiked.size else 0.0,
            # "total_activation" is the network-wide sum of the display trace.
            # Calling it 'energy' would imply a physical quantity it is not.
            "total_activation": float(self.activation.sum()),
            "mean_activation": float(self.activation.mean()) if self.activation.size else 0.0,
            "max_activation": float(self.activation.max()) if self.activation.size else 0.0,
            "mean_membrane": float(self.membrane.mean()) if self.membrane.size else 0.0,
            "max_abs_membrane": float(np.abs(self.membrane).max()) if self.membrane.size else 0.0,
            "total_input_current": float(self.input_current.sum()),
        }


class SimulationResult:
    """Everything a run produced: the neuron ordering, the states, the metadata."""

    def __init__(
        self,
        neuron_ids: Sequence[int],
        steps: Sequence[StepState],
        metadata: dict | None = None,
    ):
        self.neuron_ids: tuple[int, ...] = tuple(int(n) for n in neuron_ids)
        self.steps: tuple[StepState, ...] = tuple(steps)
        self.metadata: dict = metadata or {}

    # -- basics ------------------------------------------------------------ #

    def __len__(self) -> int:
        return len(self.steps)

    @property
    def n_steps(self) -> int:
        """Number of update steps (excludes the resting state at index 0)."""
        return max(len(self.steps) - 1, 0)

    @property
    def n_neurons(self) -> int:
        return len(self.neuron_ids)

    def __iter__(self) -> Iterator[StepState]:
        return iter(self.steps)

    # -- matrices ---------------------------------------------------------- #

    def activation_matrix(self) -> np.ndarray:
        """``(n_frames, n_neurons)`` array of the activation trace."""
        return np.vstack([s.activation for s in self.steps]) if self.steps else np.zeros((0, 0))

    def membrane_matrix(self) -> np.ndarray:
        return np.vstack([s.membrane for s in self.steps]) if self.steps else np.zeros((0, 0))

    def spike_matrix(self) -> np.ndarray:
        return (
            np.vstack([s.spiked for s in self.steps])
            if self.steps
            else np.zeros((0, 0), dtype=bool)
        )

    def spike_counts(self) -> dict[int, int]:
        """Total spikes per neuron over the whole run."""
        counts = self.spike_matrix().sum(axis=0)
        return {nid: int(c) for nid, c in zip(self.neuron_ids, counts)}

    def neurons_that_fired(self) -> list[int]:
        fired = self.spike_matrix().any(axis=0)
        return [nid for nid, f in zip(self.neuron_ids, fired) if f]

    def first_spike_step(self) -> dict[int, int]:
        """Step at which each neuron first fired; absent if it never did."""
        matrix = self.spike_matrix()
        out: dict[int, int] = {}
        for column, nid in enumerate(self.neuron_ids):
            hits = np.flatnonzero(matrix[:, column])
            if hits.size:
                out[nid] = int(self.steps[hits[0]].step)
        return out

    # -- summaries --------------------------------------------------------- #

    def summaries(self) -> list[dict[str, float | int]]:
        return [s.summary() for s in self.steps]

    def summary_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.summaries())

    def is_finite(self) -> bool:
        """False if any state ever became NaN or infinite."""
        return bool(
            np.isfinite(self.membrane_matrix()).all()
            and np.isfinite(self.activation_matrix()).all()
        )

    # -- serialisation ----------------------------------------------------- #

    def header(self) -> dict[str, Any]:
        """Sent once before streaming frames: ordering, metadata, static attributes."""
        return {
            "n_neurons": self.n_neurons,
            "n_steps": self.n_steps,
            "n_frames": len(self.steps),
            # Strings: 18-digit FlyWire IDs do not survive a JS Number.
            "neuron_ids": [str(n) for n in self.neuron_ids],
            "metadata": self.metadata,
        }

    def step_payloads(self, include_membrane: bool = True) -> list[dict[str, Any]]:
        """One compact, JSON-ready dict per frame, arrays aligned to ``neuron_ids``."""
        payloads = []
        for state in self.steps:
            payload: dict[str, Any] = {
                "step": state.step,
                "activation": [round(float(v), 6) for v in state.activation],
                "spiked": [bool(v) for v in state.spiked],
                "summary": state.summary(),
            }
            if include_membrane:
                payload["membrane"] = [round(float(v), 6) for v in state.membrane]
            payloads.append(payload)
        return payloads

    def to_dict(self, include_membrane: bool = True) -> dict[str, Any]:
        return {
            **self.header(),
            "frames": self.step_payloads(include_membrane=include_membrane),
        }

    def to_json(self, indent: int | None = None, include_membrane: bool = True) -> str:
        return json.dumps(self.to_dict(include_membrane=include_membrane), indent=indent)

    def to_records(self, only_active: bool = False) -> list[dict[str, Any]]:
        """Long format: one dict per ``(step, neuron)``.

        Args:
            only_active: skip rows where the neuron neither spiked nor carries
                any residual activation. Cuts the row count substantially on
                sparse runs.
        """
        records = []
        for state in self.steps:
            for i, nid in enumerate(self.neuron_ids):
                activation = float(state.activation[i])
                spiked = bool(state.spiked[i])
                if only_active and not spiked and activation == 0.0:
                    continue
                records.append(
                    {
                        "step": state.step,
                        "root_id": nid,
                        "activation": activation,
                        "spiked": spiked,
                        "membrane": float(state.membrane[i]),
                        "input_current": float(state.input_current[i]),
                    }
                )
        return records

    def to_frame(self, only_active: bool = False) -> pd.DataFrame:
        return pd.DataFrame(self.to_records(only_active=only_active))

    def save_json(self, path: Path | str, indent: int | None = 2) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(indent=indent) + "\n", encoding="utf-8")
        return path

    def save_csv(self, path: Path | str, only_active: bool = False) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.to_frame(only_active=only_active).to_csv(path, index=False)
        return path
