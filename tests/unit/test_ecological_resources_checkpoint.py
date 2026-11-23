# mypy: ignore-errors

"""Codec v23 ecological checkpoint section round-trip."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.ecological_resources_checkpoint import (
    checkpoint_section_from_rows,
    decode_ecological_resources_checkpoint_section,
    encode_ecological_resources_checkpoint_section,
)
from simulation.journal import (
    _decode_world_snapshot,
    _encode_world_snapshot,
    hash_snapshot,
)
from simulation.models import RunId
from simulation.persistence import PayloadHash, SnapshotId, WorldSnapshot
from simulation.versioning import ECOLOGY_WRITE_PAIR_CODEC, ECOLOGY_WRITE_PAIR_EVENT
from tests.physical_helpers import physical_config
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_resource,
    make_weather,
)
from world.environment import example_environmental_dynamics
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def test_section_round_trip_rejects_bad_order() -> None:
    section = checkpoint_section_from_rows(
        policy_sha256="ab" * 32,
        rows=(
            (EntityId("res-water"), 5, 0),
            (EntityId("res-food"), 10, 3),
        ),
    )
    assert [row.resource_id.value for row in section.rows] == [
        "res-food",
        "res-water",
    ]
    encoded = encode_ecological_resources_checkpoint_section(section)
    decoded = decode_ecological_resources_checkpoint_section(encoded)
    assert decoded == section
    with pytest.raises(ValueError, match="ecology_checkpoint_rows_order"):
        decode_ecological_resources_checkpoint_section(
            {
                "ecological_resources": {
                    "schema_version": "ecological-resources-checkpoint-v1",
                    "policy_sha256": "ab" * 32,
                    "rows": [
                        {
                            "resource_id": "res-water",
                            "minimum_capacity_tenths": 5,
                            "damage_tenths": 0,
                        },
                        {
                            "resource_id": "res-food",
                            "minimum_capacity_tenths": 10,
                            "damage_tenths": 0,
                        },
                    ],
                }
            }
        )


def test_snapshot_encode_decode_v23() -> None:
    body = alive_body("body-1")
    food = make_resource(
        "res-food",
        quantity=4.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    section = checkpoint_section_from_rows(
        policy_sha256="cd" * 32,
        rows=((food.entity_id, 10, 0),),
    )
    dynamics = example_environmental_dynamics()
    config = physical_config(2, rules=default_physical_rules())
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-eco-1"),
        run_id=RunId("run-eco-1"),
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
        event_schema_version=ECOLOGY_WRITE_PAIR_EVENT,
        projector_version="v2",
        persistence_codec_version=ECOLOGY_WRITE_PAIR_CODEC,
        derivation_version=config.derivation_version or "v3",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        infrastructure=(),
        ecological_resources=section,
        environmental_dynamics=dynamics,
    )
    bound = WorldSnapshot(
        snapshot_id=draft.snapshot_id,
        run_id=draft.run_id,
        world_id=draft.world_id,
        seed=draft.seed,
        config=draft.config,
        registrations=draft.registrations,
        locations=draft.locations,
        bodies=draft.bodies,
        items=draft.items,
        resources=draft.resources,
        weather=draft.weather,
        next_tick=draft.next_tick,
        revision=draft.revision,
        event_schema_version=draft.event_schema_version,
        projector_version=draft.projector_version,
        persistence_codec_version=draft.persistence_codec_version,
        derivation_version=draft.derivation_version,
        integrity_hash=hash_snapshot(draft),
        predecessor_commit_hash=None,
        infrastructure=(),
        ecological_resources=draft.ecological_resources,
        environmental_dynamics=draft.environmental_dynamics,
    )
    encoded = _encode_world_snapshot(bound, include_integrity_hash=True)
    decoded = _decode_world_snapshot(encoded, path="$")
    assert decoded.persistence_codec_version == "v23"
    assert decoded.ecological_resources == section
    assert (
        decoded.environmental_dynamics.canonical_payload
        == dynamics.canonical_payload
    )


def test_restore_fold_without_policy_and_continuation_with_match() -> None:
    from dataclasses import replace

    from simulation.ecological_resources_config import (
        ECOLOGICAL_RESOURCES_POLICY_ID,
        EcologicalResourceNodeSpec,
        EcologicalResourcesSpec,
        policy_sha256_for_ecological_resources,
    )
    from simulation.engine import WorldEngine
    from simulation.persistence import ReplayMode, ReplayResult, ReplayStatus
    from simulation.replay import ReplayOutcome, ReplayService
    from world.models import non_lethal_physical_rules

    food = make_resource(
        "res-food",
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    node = EcologicalResourceNodeSpec(
        resource_id=food.entity_id,
        minimum_capacity_tenths=10,
        withdrawal_allowance_tenths=0,
        recovery_tenths_per_idle_tick=5,
    )
    spec = EcologicalResourcesSpec(
        policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
        nodes=(node,),
    )
    digest = policy_sha256_for_ecological_resources(spec)
    section = checkpoint_section_from_rows(
        policy_sha256=digest,
        rows=((food.entity_id, 10, 20),),
    )
    dynamics = example_environmental_dynamics()
    config = physical_config(3, rules=non_lethal_physical_rules())
    body = alive_body("body-1")
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-eco-restore"),
        run_id=RunId("run-eco-restore"),
        world_id=WorldId("world-1"),
        seed=config.seed,
        config=config,
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
        locations=(make_location("loc-1"),),
        bodies=(body,),
        items=(),
        resources=(food,),
        weather=(make_weather("loc-1"),),
        next_tick=Tick(2),
        revision=WorldRevision(1),
        event_schema_version=ECOLOGY_WRITE_PAIR_EVENT,
        projector_version="v2",
        persistence_codec_version=ECOLOGY_WRITE_PAIR_CODEC,
        derivation_version=config.derivation_version or "v3",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        infrastructure=(),
        ecological_resources=section,
        environmental_dynamics=dynamics,
    )
    bound = replace(draft, integrity_hash=hash_snapshot(draft))

    readonly = WorldEngine.restore_from_snapshot(
        bound,
        events=(),
        committed_through_tick=None,
        environmental_dynamics=None,
        ecological_resources=None,
    )
    assert readonly._ecological_resources is None
    assert (
        readonly._snapshot.world.state.ecological_resources[
            food.entity_id
        ].damage_tenths
        == 20
    )
    assert readonly._environmental_dynamics is not None
    assert readonly._environmental_dynamics.digest == dynamics.digest

    continued = WorldEngine.restore_from_snapshot(
        bound,
        events=(),
        committed_through_tick=None,
        ecological_resources=spec,
    )
    assert continued._ecological_resources == spec
    assert continued._ecological_parameters is not None
    assert (
        continued._snapshot.world.state.ecological_resources[
            food.entity_id
        ].damage_tenths
        == 20
    )

    wrong = EcologicalResourcesSpec(
        policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
        nodes=(
            EcologicalResourceNodeSpec(
                resource_id=food.entity_id,
                minimum_capacity_tenths=10,
                withdrawal_allowance_tenths=1,
                recovery_tenths_per_idle_tick=5,
            ),
        ),
    )
    with pytest.raises(ValueError, match="ecology_policy_mismatch"):
        WorldEngine.restore_from_snapshot(
            bound,
            events=(),
            committed_through_tick=None,
            ecological_resources=wrong,
        )

    mismatched_env = replace(
        dynamics,
        season_length_ticks=dynamics.season_length_ticks + 1,
    )
    with pytest.raises(ValueError, match="ecology_environment_mismatch"):
        WorldEngine.restore_from_snapshot(
            bound,
            events=(),
            committed_through_tick=None,
            ecological_resources=spec,
            environmental_dynamics=mismatched_env,
        )

    outcome = ReplayOutcome(
        result=ReplayResult(
            run_id=bound.run_id,
            status=ReplayStatus.OK,
            mode=ReplayMode.CONTINUATION,
            snapshot_id=bound.snapshot_id,
            snapshot_next_tick=bound.next_tick,
            target_tick=bound.next_tick,
            events_applied=0,
            event_schema_version=bound.event_schema_version,
            projector_version=bound.projector_version,
            persistence_codec_version=bound.persistence_codec_version,
        ),
        engine=readonly,
        predecessor_commit_hash=None,
    )
    service = ReplayService.__new__(ReplayService)
    with pytest.raises(RuntimeError, match="ecology policy"):
        service.open_durable(outcome, journal=object())  # type: ignore[arg-type]
