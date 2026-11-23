# mypy: ignore-errors

"""Engine-owned ecological stock-damage channel binding."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from simulation.bootstrap import WorldBootstrap, build_initial_ecological_resources
from simulation.ecological_resources_config import (
    ECOLOGICAL_RESOURCES_POLICY_ID,
    EcologicalResourceNodeSpec,
    EcologicalResourcesSpec,
    policy_sha256_for_ecological_resources,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V60,
    V4CapabilityFlags,
)
from tests.simulation_helpers import make_location, make_resource, make_weather
from tests.unit.test_ecological_resources_config import _as_v60, _ecology_base
from world._ecological_resources import (
    EcologicalInvariantError,
    EcologicalStockRow,
    bootstrap_ecological_rows,
    validate_ecological_resources_state,
)
from world._state import WorldState, rebuild_world_state
from world.identifiers import EntityId, WorldId, WorldRevision

pytestmark = pytest.mark.unit


def _spec() -> EcologicalResourcesSpec:
    return EcologicalResourcesSpec(
        policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
        nodes=(
            EcologicalResourceNodeSpec(
                resource_id=EntityId("res-food"),
                minimum_capacity_tenths=10,
                withdrawal_allowance_tenths=0,
                recovery_tenths_per_idle_tick=5,
            ),
        ),
    )


def test_bootstrap_rows_zero_damage_and_order() -> None:
    rows = bootstrap_ecological_rows(
        nodes=(
            (EntityId("res-water"), 5),
            (EntityId("res-food"), 10),
        )
    )
    assert list(rows) == [EntityId("res-food"), EntityId("res-water")]
    assert all(row.damage_tenths == 0 for row in rows.values())


def test_world_state_preserves_ecology_across_unrelated_rebuild() -> None:
    food = make_resource(
        "res-food",
        quantity=4.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    rows = bootstrap_ecological_rows(nodes=((food.entity_id, 10),))
    digest = "a" * 64
    state = WorldState(
        WorldRevision(0),
        locations=(make_location(),),
        resources=(food,),
        weather=(make_weather(),),
        ecological_resources=rows,
        ecological_policy_digest=digest,
    )
    rebuilt = rebuild_world_state(state)
    assert rebuilt.ecological_resources == state.ecological_resources
    assert rebuilt.ecological_policy_digest == digest
    assert rebuilt.ecological_resources is not None
    assert isinstance(rebuilt.ecological_resources, MappingProxyType)


def test_validate_rejects_digest_mismatch_and_over_cap() -> None:
    food = make_resource(
        "res-food",
        quantity=4.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    rows = bootstrap_ecological_rows(nodes=((food.entity_id, 10),))
    digest = policy_sha256_for_ecological_resources(_spec())
    with pytest.raises(EcologicalInvariantError) as excinfo:
        validate_ecological_resources_state(
            rows,
            resources={food.entity_id: food},
            policy_digest="b" * 64,
            expected_digest=digest,
            expected_floors={food.entity_id: 10},
        )
    assert excinfo.value.code == "ecological_digest_mismatch"
    damaged = {
        food.entity_id: EcologicalStockRow(
            resource_id=food.entity_id,
            minimum_capacity_tenths=10,
            damage_tenths=35,
        )
    }
    with pytest.raises(EcologicalInvariantError):
        validate_ecological_resources_state(
            damaged,
            resources={food.entity_id: food},
            policy_digest=digest,
            expected_digest=digest,
            expected_floors={food.entity_id: 10},
        )


def test_build_initial_from_config_and_absent_when_off() -> None:
    config = _as_v60(_ecology_base())
    built = build_initial_ecological_resources(config)
    assert built is not None
    rows, digest = built
    assert digest == policy_sha256_for_ecological_resources(
        config.ecological_resources
    )
    assert list(rows) == [EntityId("res-food")]
    assert rows[EntityId("res-food")].damage_tenths == 0
    off = _ecology_base()
    assert build_initial_ecological_resources(off) is None
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-ecology-off"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        resources=(),
        weather=(make_weather(),),
        bodies=(),
    )
    assert bootstrap.ecological_resources is None
    assert bootstrap.ecological_policy_digest is None
    assert off.schema_version != RUNNER_SCHEMA_VERSION_V60
    assert not off.v4_capability_flags.ecological_feedback
    assert V4CapabilityFlags().ecological_feedback is False
