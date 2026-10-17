"""runner-config-v44 regions/migration activation and strict wire contract."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from experiments.matrix_schema import finalize_matrix_cell_config
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V44,
    V3CapabilityFlags,
    example_possession_succession_spec,
    example_resource_exchange_profile_spec,
    example_structured_commitments_spec,
    example_subjective_valuation_spec,
)
from simulation.runner_serialization import (
    RunnerSerializationError,
    decode_runner_config,
    encode_runner_config,
)
from tests.unit.test_runner_config_v43 import _plain_base, _v43
from world.identifiers import EntityId
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)


def _regions() -> RegionsMigrationSpec:
    return RegionsMigrationSpec(
        regions=(RegionDefinition("one", "One"), RegionDefinition("two", "Two")),
        location_regions=(LocationRegion(EntityId("location-1"), "one"),),
        routes=(RouteSpec(EntityId("location-1"), EntityId("location-2"), 2, 1.5),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=3,
        destination_memory_limit=4,
        destination_hop_limit=2,
        cognition_mode=CognitionMode.DISABLED,
    )


def _v44(**kwargs):
    values = {
        "schema_version": RUNNER_SCHEMA_VERSION_V44,
        "v3_capability_flags": V3CapabilityFlags(multi_polity_migration=True),
        "regions_migration": _regions(),
    }
    values.update(kwargs)
    return replace(_plain_base(), **values)


def test_v44_migration_only_round_trip_omits_other_channels() -> None:
    config = _v44()
    encoded = encode_runner_config(config)
    document = json.loads(encoded)
    assert "public_goods" not in document
    assert "collective_projects" not in document
    restored = decode_runner_config(encoded)
    assert restored.schema_version == RUNNER_SCHEMA_VERSION_V44
    assert restored.regions_migration == config.regions_migration
    assert restored.public_goods is None
    assert restored.collective_projects is None


def test_v44_composes_public_goods_family_without_changing_its_prerequisite() -> None:
    legacy_channels = _v43()
    config = _v44(
        collective_projects=legacy_channels.collective_projects,
        public_goods=legacy_channels.public_goods,
    )
    restored = decode_runner_config(encode_runner_config(config))
    assert restored.collective_projects == legacy_channels.collective_projects
    assert restored.public_goods == legacy_channels.public_goods


def test_v44_composes_valuation_commitments_and_succession_channels() -> None:
    config = _v44(
        subjective_valuation=example_subjective_valuation_spec(),
        resource_exchange_profile=example_resource_exchange_profile_spec(),
        structured_commitments=example_structured_commitments_spec(),
        possession_succession=example_possession_succession_spec(),
    )
    restored = decode_runner_config(encode_runner_config(config))
    assert restored.subjective_valuation == config.subjective_valuation
    assert restored.resource_exchange_profile == config.resource_exchange_profile
    assert restored.structured_commitments == config.structured_commitments
    assert restored.possession_succession == config.possession_succession


def test_v44_requires_migration_flag_and_spec() -> None:
    with pytest.raises(ValueError, match="regions_migration_spec_required"):
        replace(
            _plain_base(),
            schema_version=RUNNER_SCHEMA_VERSION_V44,
            v3_capability_flags=V3CapabilityFlags(multi_polity_migration=True),
        )
    with pytest.raises(ValueError, match="regions_migration_flag_required"):
        _v44(v3_capability_flags=V3CapabilityFlags())
    with pytest.raises(ValueError, match="regions_migration_requires_v44"):
        replace(_plain_base(), regions_migration=_regions())


def test_matrix_schema_selects_v44_for_migration_channel() -> None:
    config = finalize_matrix_cell_config(_v44())
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V44


def test_v44_rejects_unknown_nested_wire_fields() -> None:
    document = json.loads(encode_runner_config(_v44()))
    document["regions_migration"]["regions"][0]["extra"] = True
    with pytest.raises(RunnerSerializationError, match="invalid_fields"):
        decode_runner_config(json.dumps(document).encode())
