"""Unit tests for the excitatory/inhibitory assignment rule."""

from __future__ import annotations

import pytest

from flywire_data.neurotransmitters import (
    Polarity,
    UnknownTransmitterError,
    polarity_of,
    primary_known_transmitter,
)


@pytest.mark.parametrize(
    ("transmitter", "expected"),
    [
        ("acetylcholine", Polarity.EXCITATORY),
        ("gaba", Polarity.INHIBITORY),
        ("glutamate", Polarity.INHIBITORY),
        ("serotonin", Polarity.MODULATORY),
        ("dopamine", Polarity.MODULATORY),
        ("octopamine", Polarity.MODULATORY),
    ],
)
def test_polarity_follows_dorkenwald_rule(transmitter, expected):
    assert polarity_of(transmitter) is expected


def test_polarity_is_case_and_whitespace_insensitive():
    assert polarity_of("  AcetylCholine ") is Polarity.EXCITATORY


@pytest.mark.parametrize("bad", ["", None, "   ", "histamine", "unknown"])
def test_unclassifiable_transmitters_raise(bad):
    # We never silently default to a sign: an unhandled transmitter must fail loudly.
    with pytest.raises(UnknownTransmitterError):
        polarity_of(bad)


def test_modulatory_polarity_is_zero_weight():
    assert int(Polarity.MODULATORY) == 0


@pytest.mark.parametrize(
    ("known_nt", "expected"),
    [
        ("glutamate, proctolin, ecdysis- triggering hormone, bursicon", "glutamate"),
        ("acetylcholine, space blanket", "acetylcholine"),
        ("acetylcholine, space blanket; acetylcholine, space blanket", "acetylcholine"),
        ("acetylcholine, space blanket, CCHa1, bursicon", "acetylcholine"),
        ("", None),
        (None, None),
        ("proctolin, bursicon", None),
    ],
)
def test_primary_known_transmitter_extraction(known_nt, expected):
    assert primary_known_transmitter(known_nt) == expected


def test_negative_assertions_are_not_matched():
    # "acetylcholine-negative" states the neuron is NOT cholinergic.
    assert primary_known_transmitter("gaba-negative, acetylcholine-negative") is None
    assert (
        primary_known_transmitter("acetylcholine-negative, gaba-negative, glutamate")
        == "glutamate"
    )
