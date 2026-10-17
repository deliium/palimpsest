"""runner-config-v45 exact cultural_contact sibling and compatibility gates."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from experiments.matrix_schema import finalize_matrix_cell_config
from experiments.regional_migration_scenario import (
    _regions,
    regional_migration_scenario,
)
from simulation.compatibility import COMPATIBILITY_MATRIX
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V43,
    RUNNER_SCHEMA_VERSION_V44,
    RUNNER_SCHEMA_VERSION_V45,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    V3CapabilityFlags,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
)
from world.contact import ContactMode, CulturalContactSpec
from world.regions import CognitionMode

_OFF_ARM = regional_migration_scenario().conditions[0].runner_config


def _v45(**overrides: object):
    values: dict[str, object] = {
        "schema_version": RUNNER_SCHEMA_VERSION_V45,
        "v3_capability_flags": V3CapabilityFlags(multi_polity_migration=True),
        "regions_migration": _regions(cognition_mode=CognitionMode.DISABLED),
        "cultural_contact": CulturalContactSpec(mode=ContactMode.DETERMINISTIC),
    }
    values.update(overrides)
    return replace(_OFF_ARM, **values)  # type: ignore[arg-type]


def test_v45_is_supported_and_compat_map_lists_it() -> None:
    assert RUNNER_SCHEMA_VERSION_V45 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    entry = COMPATIBILITY_MATRIX["runner_config"]
    assert RUNNER_SCHEMA_VERSION_V45 in entry.accepted_restore


def test_v45_round_trips_through_runner_codec() -> None:
    config = _v45()
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V45
    assert decoded.cultural_contact == CulturalContactSpec(
        mode=ContactMode.DETERMINISTIC
    )
    assert decoded.regions_migration == config.regions_migration


def test_v45_mode_disabled_is_accepted() -> None:
    config = _v45(cultural_contact=CulturalContactSpec(mode=ContactMode.DISABLED))
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.cultural_contact == CulturalContactSpec(mode=ContactMode.DISABLED)


def test_v45_requires_contact_sibling() -> None:
    with pytest.raises(ValueError, match="v45_requires_cultural_contact"):
        _v45(cultural_contact=None)


def test_v45_requires_regions() -> None:
    with pytest.raises(ValueError, match="v45_requires_regions_migration"):
        _v45(
            regions_migration=None,
            v3_capability_flags=V3CapabilityFlags(),
        )


def test_contact_requires_v45_schema() -> None:
    with pytest.raises(ValueError, match="cultural_contact_requires_v45"):
        _v45(schema_version=RUNNER_SCHEMA_VERSION_V44)


def test_contact_requires_migration_flag() -> None:
    with pytest.raises(ValueError, match="regions_migration_flag_required"):
        _v45(v3_capability_flags=V3CapabilityFlags())


def test_contact_requires_regions_object() -> None:
    with pytest.raises(ValueError, match="v45_requires_regions_migration"):
        _v45(
            regions_migration=None,
            v3_capability_flags=V3CapabilityFlags(multi_polity_migration=True),
        )


def test_contact_rejects_unknown_nested_key_on_decode() -> None:
    document = json.loads(encode_runner_config(_v45()))
    document["cultural_contact"]["unexpected"] = "x"
    with pytest.raises(RunnerSerializationError):
        decode_runner_config(json.dumps(document).encode("utf-8"))


def test_v44_off_contact_remains_valid_and_omits_contact() -> None:
    v44 = _v45(schema_version=RUNNER_SCHEMA_VERSION_V44, cultural_contact=None)
    document = json.loads(encode_runner_config(v44))
    assert "cultural_contact" not in document
    decoded = decode_runner_config(encode_runner_config(v44))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V44
    assert decoded.cultural_contact is None


def test_matrix_finalize_selects_v45_when_contact_is_active() -> None:
    from experiments.matrix_factors import clone_runner_config

    provisional = clone_runner_config(_v45(), schema_version=RUNNER_SCHEMA_VERSION_V4)
    config = finalize_matrix_cell_config(provisional)
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V45


def test_v43_is_still_supported() -> None:
    assert RUNNER_SCHEMA_VERSION_V43 in SUPPORTED_RUNNER_SCHEMA_VERSIONS
