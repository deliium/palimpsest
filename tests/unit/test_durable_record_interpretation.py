"""Durable-record interpretation distortion, compile gates, cultural genre compose."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest

from agents.cognition.artifacts import (
    ArtifactInterpretationMode,
    apply_artifact_interpretation_update,
)
from agents.cognition.cultural_features import (
    CulturalFeatureKindId,
    CulturalTransmissionChannelId,
    apply_cultural_feature_channel_uptake,
    collect_cultural_feature_public_cues,
    empty_cultural_feature_ledger,
)
from agents.cognition.deliberation import CommandPlanner
from agents.cognition.models import (
    ActionDirection,
    CognitiveLoopInput,
    ImaginedFuture,
    IntentionCode,
    InternalAgentState,
    MotivationCode,
    PossibleFutures,
    SelectedIntention,
    SituationClaimCode,
)
from agents.models import AgentId
from world.actions import AnnotateRecord, CopyRecord, DamageRecord, Wait
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    ArtifactRelation,
    DurableRecordGenre,
    RecordIntegrity,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservedArtifact,
    ObservedItemPlacement,
    ObservedSelf,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

pytestmark = pytest.mark.unit


def _agent(value: str = "ada") -> AgentId:
    return AgentId(value)


def _self(*, fatigue: float = 0.0) -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-ada"),
        location_id=EntityId("clearing"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(fatigue),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _artifact(
    *,
    artifact_id: str = "art-1",
    revision: int = 0,
    integrity: RecordIntegrity | None = RecordIntegrity.INTACT,
    genre: DurableRecordGenre | None = DurableRecordGenre.WARNING,
    marks: tuple[str, ...] = ("water", "north"),
    relations: tuple[ArtifactRelation, ...] | None = None,
) -> ObservedArtifact:
    if relations is None:
        relations = (ArtifactRelation("water", "at", "north"),)
    return ObservedArtifact(
        entity_id=EntityId(artifact_id),
        kind=ArtifactKind.RECORD,
        author_id=EntityId("body-author"),
        created_tick=0,
        content=ArtifactContent(marks=marks, relations=relations),
        content_revision=revision,
        placement=ObservedItemPlacement.GROUND_HERE,
        record_genre=genre,
        integrity=integrity,
        copy_generation=0,
        source_artifact_id=EntityId(artifact_id),
        annotation_revisions=0,
        lost_mark_count=0,
    )


def _observe(
    *artifacts: ObservedArtifact,
    tick: int = 1,
    visibility: float | None = 1.0,
    fatigue: float = 0.0,
) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-ada"),
        revision=WorldRevision(0),
        tick=tick,
        self_body=_self(fatigue=fatigue),
        visibility=visibility,
        artifacts=artifacts,
    )


def _loop_input(observation: Observation | None = None) -> CognitiveLoopInput:
    agent = _agent()
    obs = observation if observation is not None else _observe()
    return CognitiveLoopInput(
        agent_id=agent,
        observation=obs,
        internal_state=InternalAgentState(owner_id=agent),
    )


def _intention() -> SelectedIntention:
    return SelectedIntention(
        owner_id=_agent(),
        intention=IntentionCode.WAIT,
        source_motive=MotivationCode.WAIT,
        confidence=0.8,
        selected_future_id="wait",
        direction=ActionDirection.WAIT,
        appraisal_future_ids=("wait",),
    )


def _futures() -> PossibleFutures:
    return PossibleFutures(
        owner_id=_agent(),
        futures=(
            ImaginedFuture(
                future_id="wait",
                claim_codes=(SituationClaimCode.LOCAL_SCENE,),
                confidence=0.8,
                direction=ActionDirection.WAIT,
            ),
        ),
        confidence=1.0,
    )


def test_damaged_integrity_forces_distortion_when_visibility_clean(
    caplog: pytest.LogCaptureFixture,
) -> None:
    observation = _observe(
        _artifact(integrity=RecordIntegrity.DAMAGED),
        visibility=1.0,
        fatigue=0.0,
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.artifacts"):
        ledger = apply_artifact_interpretation_update(
            observation, _agent(), previous=None
        )
    assert len(ledger.interpretations) == 1
    reading = ledger.interpretations[0]
    assert reading.distorted is True
    assert reading.reading_relations == ()
    assert "record_integrity" in caplog.text


def test_partially_lost_integrity_forces_distortion() -> None:
    observation = _observe(
        _artifact(integrity=RecordIntegrity.PARTIALLY_LOST, revision=1),
        visibility=1.0,
        fatigue=0.0,
    )
    ledger = apply_artifact_interpretation_update(observation, _agent(), previous=None)
    assert ledger.interpretations[0].distorted is True


def test_intact_integrity_does_not_force_distortion() -> None:
    observation = _observe(
        _artifact(integrity=RecordIntegrity.INTACT),
        visibility=1.0,
        fatigue=0.0,
    )
    ledger = apply_artifact_interpretation_update(observation, _agent(), previous=None)
    assert ledger.interpretations[0].distorted is False
    assert len(ledger.interpretations[0].reading_relations) == 1


def test_damage_revision_bump_replaces_prior_clean_reading() -> None:
    clean = _observe(_artifact(integrity=RecordIntegrity.INTACT, revision=0))
    previous = apply_artifact_interpretation_update(clean, _agent(), previous=None)
    assert previous.interpretations[0].distorted is False
    damaged = _observe(
        _artifact(integrity=RecordIntegrity.DAMAGED, revision=1),
        tick=2,
    )
    updated = apply_artifact_interpretation_update(
        damaged, _agent(), previous=previous
    )
    assert updated.interpretations[0].distorted is True
    assert updated.interpretations[0].observed_revision == 1


@pytest.mark.asyncio
async def test_disabled_mode_does_not_compile_durable_commands(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="agents.cognition.deliberation")
    injected = CopyRecord(artifact_id=EntityId("art-1"))
    with patch(
        "agents.cognition.deliberation._compile_command",
        return_value=injected,
    ):
        plan = await CommandPlanner().plan(
            _loop_input(),
            _intention(),
            _futures(),
            artifact_interpretation_mode=ArtifactInterpretationMode.DISABLED,
            durable_records_active=True,
        )
    assert type(plan.command) is Wait
    assert "compile_skip" in caplog.text


@pytest.mark.asyncio
async def test_deterministic_without_durable_rejects_copy(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="agents.cognition.deliberation")
    injected = AnnotateRecord(
        artifact_id=EntityId("art-1"),
        content=ArtifactContent(marks=("note",)),
    )
    with patch(
        "agents.cognition.deliberation._compile_command",
        return_value=injected,
    ):
        plan = await CommandPlanner().plan(
            _loop_input(),
            _intention(),
            _futures(),
            artifact_interpretation_mode=ArtifactInterpretationMode.DETERMINISTIC,
            durable_records_active=False,
        )
    assert type(plan.command) is Wait
    assert "durable_records_inactive" in caplog.text


@pytest.mark.asyncio
async def test_deterministic_and_durable_allows_damage() -> None:
    injected = DamageRecord(artifact_id=EntityId("art-1"), mode="damage")
    with patch(
        "agents.cognition.deliberation._compile_command",
        return_value=injected,
    ):
        plan = await CommandPlanner().plan(
            _loop_input(),
            _intention(),
            _futures(),
            artifact_interpretation_mode=ArtifactInterpretationMode.DETERMINISTIC,
            durable_records_active=True,
        )
    assert type(plan.command) is DamageRecord
    assert plan.command.mode == "damage"


def test_durable_genre_maps_to_cultural_feature_kinds() -> None:
    cases = (
        (DurableRecordGenre.WARNING, CulturalFeatureKindId.SYMBOLIC_ASSOCIATION),
        (DurableRecordGenre.INSTRUCTION, CulturalFeatureKindId.PRACTICE),
        (DurableRecordGenre.STORY, CulturalFeatureKindId.NARRATIVE_ELEMENT),
        (DurableRecordGenre.AGREEMENT, CulturalFeatureKindId.SOCIAL_EXPECTATION),
        (DurableRecordGenre.CHRONICLE, CulturalFeatureKindId.NARRATIVE_ELEMENT),
        (DurableRecordGenre.GENEALOGY, CulturalFeatureKindId.SYMBOLIC_ASSOCIATION),
    )
    for genre, expected_kind in cases:
        cues = collect_cultural_feature_public_cues(
            _observe(_artifact(genre=genre, artifact_id=f"art-{genre.value}"))
        )
        primary = next(
            cue
            for cue in cues
            if cue.channel is CulturalTransmissionChannelId.ARTIFACT
            and cue.feature_kind is not CulturalFeatureKindId.TERM
        )
        assert primary.feature_kind is expected_kind
        assert primary.content_key.startswith(f"durable:{genre.value}:")


def test_cultural_compose_skips_when_cultural_channel_off() -> None:
    """No cultural ledger mutations when channel absent (compose never called)."""
    cues = collect_cultural_feature_public_cues(
        _observe(_artifact(genre=DurableRecordGenre.INSTRUCTION))
    )
    assert cues
    # Channel off ⇒ caller never invokes uptake; empty ledger stays empty.
    ledger = empty_cultural_feature_ledger(_agent())
    assert ledger.beliefs == ()


def test_cultural_uptake_writes_practice_from_instruction_genre() -> None:
    observation = _observe(_artifact(genre=DurableRecordGenre.INSTRUCTION))
    cues = collect_cultural_feature_public_cues(observation)
    ledger = empty_cultural_feature_ledger(_agent())
    updated, audits = apply_cultural_feature_channel_uptake(
        ledger,
        enabled_feature_kinds=(
            CulturalFeatureKindId.PRACTICE.value,
            CulturalFeatureKindId.TERM.value,
        ),
        enabled_provenance_channels=(CulturalTransmissionChannelId.ARTIFACT.value,),
        cues=cues,
        tick=1,
    )
    kinds = {belief.feature_kind for belief in updated.beliefs}
    assert CulturalFeatureKindId.PRACTICE in kinds
    assert audits
