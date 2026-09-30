"""Open teaching offers are rebuilt from events and rejected off the snapshot."""

from __future__ import annotations

import json
import logging

import pytest

from agents.cognition.teaching import (
    AdviceAct,
    AdviceBand,
    AdviceDomain,
    DeclarativeAdvice,
    empty_advice_store,
)
from agents.models import AgentId
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import (
    PersistenceSerializationError,
    decode_persistence,
    encode_persistence,
    hash_snapshot,
)
from simulation.lifecycle import ActionSubmission
from simulation.models import DERIVATION_VERSION
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    ReplayRequest,
    SnapshotId,
    WorldSnapshot,
)
from simulation.run_control import AgentRuntimeCheckpoint
from tests.physical_helpers import physical_config, two_location_fixture
from tests.unit.test_identity_runtime import _runtime
from world._skills import SkillDomain
from world._teaching import (
    TeachingAct,
    TeachingOffer,
    default_teaching_interaction_policy,
    refold_teaching_offers,
)
from world.actions import Talk
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId, WorldRevision

pytestmark = pytest.mark.unit


def _snapshot_at_start(engine: WorldEngine) -> WorldSnapshot:
    bootstrap = engine._bootstrap
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-teach"),
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


def _demonstrate_engine() -> tuple[WorldEngine, WorldSnapshot]:
    fixture = two_location_fixture(item_on_ground=False)
    policy = default_teaching_interaction_policy()
    live = WorldEngine(
        config=physical_config(4),
        bootstrap=fixture.as_bootstrap(),
        teaching_policy=policy,
        teaching_entity_ids=(EntityId("body-1"), EntityId("body-2")),
    )
    snapshot = _snapshot_at_start(live)
    batch = live.observe()
    live.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Talk(
                    EntityId("body-2"),
                    origin_utterance(
                        text="watch",
                        speaker_id=EntityId("body-1"),
                        communication_id="comm-demo-1",
                        relations=(
                            CommunicationRelation(
                                subject="skill",
                                predicate="demonstrate",
                                object="foraging",
                            ),
                        ),
                    ),
                ),
            ),
        )
    )
    return live, snapshot


def test_refold_keeps_an_open_offer_and_rejects_a_disagreement(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="world._teaching")
    live, snapshot = _demonstrate_engine()
    policy = default_teaching_interaction_policy()
    participants = frozenset({EntityId("body-1"), EntityId("body-2")})
    events = live._snapshot.event_history
    restored_tick = live.tick.value
    open_offers = refold_teaching_offers(
        events,
        policy,
        participants,
        tick=restored_tick,
    )
    assert len(open_offers) == 1
    assert open_offers[0].act is TeachingAct.DEMONSTRATE
    assert open_offers[0].domain is SkillDomain.FORAGING
    assert "teaching_offers_refolded" in caplog.text
    assert "tick=" in caplog.text
    assert "open_count=1" in caplog.text
    WorldEngine.restore_from_snapshot(
        snapshot,
        events=events,
        committed_through_tick=Tick(restored_tick - 1),
        teaching_policy=policy,
        teaching_entity_ids=tuple(participants),
        teaching_offers=open_offers,
    )
    stale = (
        TeachingOffer(
            speaker_id=EntityId("body-1"),
            recipient_id=EntityId("body-2"),
            act=TeachingAct.DEMONSTRATE,
            domain=SkillDomain.NAVIGATION,
            delivery_tick=0,
        ),
    )
    with pytest.raises(ValueError, match="teaching_offer_mismatch"):
        WorldEngine.restore_from_snapshot(
            snapshot,
            events=events,
            committed_through_tick=Tick(restored_tick - 1),
            teaching_policy=policy,
            teaching_entity_ids=tuple(participants),
            teaching_offers=stale,
        )
    assert "reason_code=teaching_offer_mismatch" in caplog.text
    assert "watch" not in caplog.text


def test_disabled_restore_skips_the_refold(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="world._teaching")
    fixture = two_location_fixture(item_on_ground=False)
    live = WorldEngine(config=physical_config(4), bootstrap=fixture.as_bootstrap())
    snapshot = _snapshot_at_start(live)
    batch = live.observe()
    live.resolve_tick((ActionSubmission(batch.token, AgentId("agent-1"), Talk(
        EntityId("body-2"),
        origin_utterance(
            text="hello",
            speaker_id=EntityId("body-1"),
            communication_id="comm-plain",
        ),
    )),))
    WorldEngine.restore_from_snapshot(
        snapshot,
        events=live._snapshot.event_history,
        committed_through_tick=Tick(live.tick.value - 1),
    )
    assert "teaching_offers_refolded" not in caplog.text
    request = ReplayRequest(run_id=live.run_id, target_tick=None)
    assert request.teaching_policy is None
    assert request.teaching_offers is None
    with pytest.raises(ValueError, match="teaching_offer_mismatch"):
        WorldEngine.restore_from_snapshot(
            snapshot,
            events=live._snapshot.event_history,
            committed_through_tick=Tick(live.tick.value - 1),
            teaching_offers=(
                TeachingOffer(
                    speaker_id=EntityId("body-1"),
                    recipient_id=EntityId("body-2"),
                    act=TeachingAct.DEMONSTRATE,
                    domain=SkillDomain.FORAGING,
                    delivery_tick=0,
                ),
            ),
        )


def test_world_snapshot_rejects_a_teaching_key() -> None:
    fixture = two_location_fixture(item_on_ground=False)
    engine = WorldEngine(config=physical_config(2), bootstrap=fixture.as_bootstrap())
    encoded = encode_persistence(_snapshot_at_start(engine))
    document = json.loads(encoded.decode("utf-8"))
    document["data"]["teaching_offers"] = []
    with pytest.raises(PersistenceSerializationError) as unknown:
        decode_persistence(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode(),
            WorldSnapshot,
        )
    assert unknown.value.code == "unknown_field"


def test_advice_round_trips_on_the_runtime_checkpoint() -> None:
    runtime, _reader = _runtime()
    advice = empty_advice_store(runtime.agent_id).record(
        DeclarativeAdvice(
            occurrence_id="occ-explain-1",
            source_agent_id=AgentId("agent-2"),
            act=AdviceAct.EXPLAIN,
            domain=AdviceDomain.FORAGING,
            band=AdviceBand.HIGH,
            delivery_tick=1,
        )
    )
    runtime._advice = advice
    exported = runtime.export_runtime_checkpoint()
    assert type(exported) is AgentRuntimeCheckpoint
    assert exported.declarative_advice == advice
    fresh, _reader = _runtime()
    fresh.restore_runtime_checkpoint(exported)
    assert fresh._advice == advice
    blank = AgentRuntimeCheckpoint(
        agent_id=runtime.agent_id,
        status=exported.status,
        internal_state=exported.internal_state,
        last_observation_key=None,
        processed_invocation_count=0,
        finalized_hash_count=0,
        goals=runtime.agent.goals,
    )
    assert blank.declarative_advice is None
    runtime.restore_runtime_checkpoint(blank)
    assert runtime._advice is None
