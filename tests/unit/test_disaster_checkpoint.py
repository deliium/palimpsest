# mypy: ignore-errors

"""Codec v24 disaster checkpoint round-trip and restore binding."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.disasters_checkpoint import (
    DisasterStateSection,
    section_from_disaster_state,
)
from simulation.ecological_resources_checkpoint import checkpoint_section_from_rows
from simulation.ecological_resources_config import (
    ECOLOGICAL_RESOURCES_POLICY_ID,
    EcologicalResourceNodeSpec,
    EcologicalResourcesSpec,
    policy_sha256_for_ecological_resources,
)
from simulation.journal import (
    PersistenceSerializationError,
    _decode_world_snapshot,
    _encode_world_snapshot,
    hash_snapshot,
)
from simulation.models import RunId
from simulation.persistence import (
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from simulation.versioning import (
    DISASTERS_WRITE_PAIR_CODEC,
    DISASTERS_WRITE_PAIR_EVENT,
)
from tests.physical_helpers import physical_config
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_resource,
    make_weather,
)
from world._disasters import DisasterState
from world.environment import example_environmental_dynamics
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _v24_snapshot(
    *,
    food_quantity: float = 4.0,
    damage: int = 0,
    applied: tuple[str, ...] = (),
    overexploitation_active: bool = False,
) -> tuple[WorldSnapshot, EcologicalResourcesSpec, object]:
    food = make_resource(
        "res-food",
        quantity=food_quantity,
        maximum_quantity=10.0,
        regeneration_per_tick=1.0,
    )
    node = EcologicalResourceNodeSpec(
        resource_id=food.entity_id,
        minimum_capacity_tenths=10,
        withdrawal_allowance_tenths=20,
        recovery_tenths_per_idle_tick=5,
    )
    spec = EcologicalResourcesSpec(
        policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
        nodes=(node,),
    )
    policy = policy_sha256_for_ecological_resources(spec)
    section = checkpoint_section_from_rows(
        policy_sha256=policy,
        rows=((food.entity_id, 10, damage),),
    )
    disaster = DisasterStateSection(
        policy_sha256="b" * 64,
        overexploitation_active=overexploitation_active,
        applied_rule_ids=applied,
    )
    dynamics = example_environmental_dynamics()
    config = physical_config(2, rules=default_physical_rules())
    body = alive_body("body-1")
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-dis-1"),
        run_id=RunId("run-dis-1"),
        world_id=WorldId("world-1"),
        seed=config.seed,
        config=config,
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
        locations=(make_location("loc-1"),),
        bodies=(body,),
        items=(),
        resources=(food,),
        weather=(make_weather("loc-1"),),
        next_tick=Tick(1),
        revision=WorldRevision(0),
        event_schema_version=DISASTERS_WRITE_PAIR_EVENT,
        projector_version="v2",
        persistence_codec_version=DISASTERS_WRITE_PAIR_CODEC,
        derivation_version=config.derivation_version or "v3",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        ecological_resources=section,
        environmental_dynamics=dynamics,
        disaster_state=disaster,
        exchange_offers=(),
        collective_projects=(),
        kinship_edges=(),
        dependency_need_registers=(),
        lifecycle_records=(),
        repositories=(),
        corpse_custody_item_ids=(),
    )
    bound = replace(draft, integrity_hash=hash_snapshot(draft))
    return bound, spec, dynamics


def test_snapshot_encode_decode_v24() -> None:
    bound, _spec, dynamics = _v24_snapshot(applied=("fire-a",))
    encoded = _encode_world_snapshot(bound, include_integrity_hash=True)
    assert encoded["persistence_codec_version"] == "v24"
    assert "ecological_resources" in encoded
    assert "disaster_state" in encoded
    assert encoded["disaster_state"]["applied_rule_ids"] == ["fire-a"]
    decoded = _decode_world_snapshot(encoded, path="$")
    assert decoded.persistence_codec_version == "v24"
    assert decoded.event_schema_version == DISASTERS_WRITE_PAIR_EVENT
    assert decoded.disaster_state == bound.disaster_state
    assert (
        decoded.environmental_dynamics.canonical_payload
        == dynamics.canonical_payload
    )


def test_legacy_codec_rejects_disaster_state() -> None:
    bound, _spec, _dynamics = _v24_snapshot()
    encoded = _encode_world_snapshot(bound, include_integrity_hash=True)
    encoded["persistence_codec_version"] = "v23"
    encoded["event_schema_version"] = 25
    with pytest.raises(PersistenceSerializationError):
        _decode_world_snapshot(encoded, path="$")


def test_section_from_disaster_state_round_trip() -> None:
    state = DisasterState(
        policy_sha256="c" * 64,
        overexploitation_active=True,
        applied_rule_ids=("alpha", "beta"),
    )
    section = section_from_disaster_state(state)
    assert section.to_disaster_state() == state
