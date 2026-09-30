"""Enabled skill replay refolds the ledger. Disabled restore leaves it absent."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import hash_snapshot
from simulation.lifecycle import ActionSubmission
from simulation.models import DERIVATION_VERSION
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from tests.physical_helpers import physical_config, two_location_fixture
from tests.unit.determinism_helpers import project_world_state
from world._skills import (
    ObjectiveSkillLedger,
    SkillDomain,
    default_objective_skill_policy,
)
from world.actions import Search, Talk, Wait
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId, WorldRevision

pytestmark = pytest.mark.unit


def _quantize(value: float) -> float:
    return round(value / 1e-6) * 1e-6


def _snapshot_at_start(engine: WorldEngine) -> WorldSnapshot:
    bootstrap = engine._bootstrap
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-skill"),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=tuple(bootstrap.registrations),
        locations=tuple(bootstrap.locations),
        bodies=tuple(bootstrap.bodies),
        items=tuple(bootstrap.items),
        resources=tuple(bootstrap.resources),
        weather=tuple(bootstrap.weather),
        next_tick=Tick(0),
        revision=WorldRevision(0),
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=engine._config.derivation_version or DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
    )
    return WorldSnapshot(
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
    )


def test_disabled_restore_skips_the_ledger_and_keeps_observation_parity(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="simulation.engine")
    fixture = two_location_fixture(item_on_ground=False)
    live = WorldEngine(config=physical_config(4), bootstrap=fixture.as_bootstrap())
    snapshot = _snapshot_at_start(live)
    batch = live.observe()
    live.resolve_tick((ActionSubmission(batch.token, AgentId("agent-1"), Wait()),))
    restored = WorldEngine.restore_from_snapshot(
        snapshot,
        events=live._snapshot.event_history,
        committed_through_tick=Tick(live.tick.value - 1),
    )
    assert restored._skill_ledger is None
    assert "skill_ledger=absent" in caplog.text
    assert project_world_state(restored._snapshot.world.state) == project_world_state(
        live._snapshot.world.state
    )
    assert restored.observe().observations == live.observe().observations


def test_enabled_refold_matches_search_witness_and_private_instruction(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="simulation.engine")
    fixture = two_location_fixture(item_on_ground=False)
    policy = default_objective_skill_policy()
    from world.models import PhysicalRules

    live = WorldEngine(
        config=physical_config(5, rules=PhysicalRules(search_base_probability=1.0)),
        bootstrap=fixture.as_bootstrap(),
        skill_policy=policy,
        skill_entity_ids=(EntityId("body-1"), EntityId("body-2")),
    )
    snapshot = _snapshot_at_start(live)
    batch = live.observe()
    live.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Search(EntityId("res-food"))
            ),
        )
    )
    batch = live.observe()
    live.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Talk(
                    EntityId("body-2"),
                    origin_utterance(
                        text="quiet",
                        speaker_id=EntityId("body-1"),
                        relations=(
                            CommunicationRelation(
                                subject="skill",
                                predicate="instruct",
                                object="navigation",
                            ),
                        ),
                    ),
                ),
            ),
        )
    )
    enabled = (EntityId("body-1"), EntityId("body-2"))
    restored = WorldEngine.restore_from_snapshot(
        snapshot,
        events=live._snapshot.event_history,
        committed_through_tick=Tick(live.tick.value - 1),
        skill_policy=policy,
        skill_entity_ids=enabled,
    )
    assert restored._skill_ledger is not None
    assert live._skill_ledger is not None
    for body in enabled:
        for domain in SkillDomain:
            left = restored._skill_ledger.level(body, domain)
            right = live._skill_ledger.level(body, domain)
            assert left == right
    assert live._skill_ledger.level(
        EntityId("body-1"), SkillDomain.RESOURCE_DETECTION
    ) == _quantize(0.07)
    assert live._skill_ledger.level(
        EntityId("body-2"), SkillDomain.RESOURCE_DETECTION
    ) == _quantize(0.01)
    assert live._skill_ledger.level(EntityId("body-1"), SkillDomain.TEACHING) == (
        _quantize(0.07)
    )
    assert live._skill_ledger.level(EntityId("body-2"), SkillDomain.NAVIGATION) == 0.0
    assert "skill_ledger_restored" in caplog.text
    assert project_world_state(restored._snapshot.world.state) == project_world_state(
        live._snapshot.world.state
    )
    with pytest.raises(ValueError, match="skill_ledger_mismatch"):
        WorldEngine.restore_from_snapshot(
            snapshot,
            events=live._snapshot.event_history,
            committed_through_tick=Tick(live.tick.value - 1),
            skill_policy=policy,
            skill_entity_ids=enabled,
            skill_ledger=ObjectiveSkillLedger.bootstrap(enabled),
        )
    assert "reason_code=skill_ledger_mismatch" in caplog.text
    assert "quiet" not in caplog.text
