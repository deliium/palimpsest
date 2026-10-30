"""Closed V4 capability flag vocabulary: shape, ownership, and digest."""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields

import pytest

from simulation.compatibility import V4_CAPABILITY_FLAG_NAMES
from simulation.runner_models import (
    V2CapabilityFlags,
    V3CapabilityFlags,
    V4CapabilityFlags,
    v4_capability_flags_digest,
)
from simulation.v4_architecture import V4_CONTEXTS


def test_default_flags_are_all_off_and_twelve_wide() -> None:
    flags = V4CapabilityFlags()
    assert flags.any_enabled() is False
    assert flags.enabled_names() == ()
    assert flags.owned_enabled_names() == ()
    assert flags.unimplemented_enabled_names() == ()
    assert len(fields(V4CapabilityFlags)) == 12
    assert len(V4_CAPABILITY_FLAG_NAMES) == 12
    assert (
        tuple(field.name for field in fields(V4CapabilityFlags))
        == V4_CAPABILITY_FLAG_NAMES
    )


def test_flag_names_match_the_context_registry() -> None:
    assert (
        tuple(
            spec.capability_flag
            for spec in V4_CONTEXTS
            if spec.capability_flag is not None
        )
        == V4_CAPABILITY_FLAG_NAMES
    )
    assert len(V4_CAPABILITY_FLAG_NAMES) == 12
    assert len(V4_CONTEXTS) == 14


def test_flag_vocabularies_do_not_overlap() -> None:
    v2_names = {field.name for field in fields(V2CapabilityFlags)}
    v3_names = {field.name for field in fields(V3CapabilityFlags)}
    v4_names = set(V4_CAPABILITY_FLAG_NAMES)

    assert v4_names.isdisjoint(v2_names)
    assert v4_names.isdisjoint(v3_names)

    for name in V4_CAPABILITY_FLAG_NAMES:
        with pytest.raises(TypeError):
            V2CapabilityFlags(**{name: True})
        with pytest.raises(TypeError):
            V3CapabilityFlags(**{name: True})
    for name in sorted(v2_names | v3_names):
        with pytest.raises(TypeError):
            V4CapabilityFlags(**{name: True})


def test_non_bool_flag_values_are_rejected() -> None:
    for name in V4_CAPABILITY_FLAG_NAMES:
        with pytest.raises(TypeError, match=f"V4CapabilityFlags.{name} must be bool"):
            V4CapabilityFlags(**{name: 1})  # type: ignore[arg-type]


def test_digest_is_stable_hex_and_changes_with_one_flag() -> None:
    flags = V4CapabilityFlags()
    digest = v4_capability_flags_digest(flags)
    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(character in "0123456789abcdef" for character in digest)
    assert digest == v4_capability_flags_digest(V4CapabilityFlags())

    expected = hashlib.sha256(
        json.dumps(
            {name: getattr(flags, name) for name in V4_CAPABILITY_FLAG_NAMES},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert digest == expected

    for name in V4_CAPABILITY_FLAG_NAMES:
        flipped = V4CapabilityFlags(**{name: True})
        assert v4_capability_flags_digest(flipped) != digest
        assert v4_capability_flags_digest(flipped) == v4_capability_flags_digest(
            V4CapabilityFlags(**{name: True})
        )


def test_digest_rejects_other_flag_types() -> None:
    with pytest.raises(TypeError, match="requires V4CapabilityFlags"):
        v4_capability_flags_digest(V3CapabilityFlags())  # type: ignore[arg-type]


def test_every_enabled_flag_is_unimplemented() -> None:
    for name in V4_CAPABILITY_FLAG_NAMES:
        flags = V4CapabilityFlags(**{name: True})
        assert flags.any_enabled() is True
        assert flags.enabled_names() == (name,)
        assert flags.unimplemented_enabled_names() == (name,)
        assert flags.owned_enabled_names() == ()
