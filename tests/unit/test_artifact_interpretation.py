"""Opt-in private artifact interpretation without auto-download memory."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.cognition.artifacts import (
    ArtifactInterpretation,
    ArtifactInterpretationLedger,
    ArtifactInterpretationMode,
    ArtifactReadingRelation,
    apply_artifact_interpretation_update,
    artifact_inscribe_command,
    artifact_inscribe_penalties,
    artifact_inscribe_preferred,
    empty_artifact_interpretation_ledger,
    require_owner_artifact_interpretations,
)
from agents.cognition.models import ActionDirection, SubjectiveSnapshot
from agents.models import AgentId
from world.actions import Inscribe, Talk, Wait
from world.artifacts import ArtifactContent, ArtifactKind, ArtifactRelation
from world.communications import origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservedArtifact,
    ObservedItemPlacement,
    ObservedSelf,
    VisibleBody,
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


def _self(
    *,
    fatigue: float = 0.0,
    body_id: str = "body-ada",
) -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId(body_id),
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
    marks: tuple[str, ...] = ("water", "north"),
    relations: tuple[ArtifactRelation, ...] | None = None,
) -> ObservedArtifact:
    if relations is None:
        relations = (ArtifactRelation("water", "at", "north"),)
    return ObservedArtifact(
        entity_id=EntityId(artifact_id),
        kind=ArtifactKind.SIGN,
        author_id=EntityId("body-author"),
        created_tick=0,
        content=ArtifactContent(marks=marks, relations=relations),
        content_revision=revision,
        placement=ObservedItemPlacement.GROUND_HERE,
    )


def _observe(
    *artifacts: ObservedArtifact,
    tick: int = 1,
    visibility: float | None = 1.0,
    fatigue: float = 0.0,
    bodies: tuple[VisibleBody, ...] = (),
    body_id: str = "body-ada",
) -> Observation:
    return Observation(
        world_id=WorldId("world-w"),
        observer_id=EntityId(body_id),
        revision=WorldRevision(1),
        tick=tick,
        self_body=_self(fatigue=fatigue, body_id=body_id),
        artifacts=artifacts,
        visible_bodies=bodies,
        visibility=visibility,
    )


def test_mode_default_disabled() -> None:
    assert ArtifactInterpretationMode.DISABLED.value == "disabled"
    assert ArtifactInterpretationMode.DETERMINISTIC.value == "deterministic"


def test_disabled_snapshot_field_defaults_none() -> None:
    snap = SubjectiveSnapshot(
        owner_id=_agent(),
        revision=0,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
    )
    assert snap.artifact_interpretations is None


def test_clean_interpretation_copies_exact(caplog: pytest.LogCaptureFixture) -> None:
    observation = _observe(_artifact(), visibility=0.9, fatigue=10.0)
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.artifacts"):
        ledger = apply_artifact_interpretation_update(observation, _agent())
    assert len(ledger.interpretations) == 1
    entry = ledger.interpretations[0]
    assert entry.reading_marks == ("water", "north")
    assert entry.reading_relations == (
        ArtifactReadingRelation("water", "at", "north"),
    )
    assert entry.distorted is False
    assert entry.confidence == 0.85
    assert entry.observed_revision == 0
    assert entry.source_tick == 1
    assert "artifact_interpretation_updated" in caplog.text


def test_visibility_distortion_drops_last_relation() -> None:
    observation = _observe(
        _artifact(
            relations=(
                ArtifactRelation("water", "at", "north"),
                ArtifactRelation("food", "at", "south"),
            )
        ),
        visibility=0.74,
        fatigue=0.0,
    )
    ledger = apply_artifact_interpretation_update(observation, _agent())
    entry = ledger.interpretations[0]
    assert entry.distorted is True
    assert entry.confidence == 0.55
    assert entry.reading_marks == ("water", "north")
    assert entry.reading_relations == (
        ArtifactReadingRelation("water", "at", "north"),
    )


def test_fatigue_distortion_and_empty_relations() -> None:
    observation = _observe(
        _artifact(relations=()),
        visibility=1.0,
        fatigue=70.0,
    )
    ledger = apply_artifact_interpretation_update(observation, _agent())
    entry = ledger.interpretations[0]
    assert entry.distorted is True
    assert entry.confidence == 0.55
    assert entry.reading_relations == ()


def test_fatigue_distortion_drops_last_relation() -> None:
    observation = _observe(
        _artifact(
            relations=(
                ArtifactRelation("water", "at", "north"),
                ArtifactRelation("food", "at", "south"),
            )
        ),
        visibility=1.0,
        fatigue=70.0,
    )
    ledger = apply_artifact_interpretation_update(observation, _agent())
    entry = ledger.interpretations[0]
    assert entry.distorted is True
    assert entry.confidence == 0.55
    assert entry.reading_relations == (
        ArtifactReadingRelation("water", "at", "north"),
    )


def test_two_owners_one_fatigued_divergent_readings_observer_marks_identical() -> None:
    from observer.contracts import ObserverArtifact

    shared = _artifact(
        relations=(
            ArtifactRelation("water", "at", "north"),
            ArtifactRelation("food", "at", "south"),
        )
    )
    clean = apply_artifact_interpretation_update(
        _observe(shared, visibility=1.0, fatigue=0.0, body_id="body-ada"),
        _agent("ada"),
    )
    fatigued = apply_artifact_interpretation_update(
        _observe(shared, visibility=1.0, fatigue=70.0, body_id="body-ben"),
        _agent("ben"),
    )
    clean_entry = clean.interpretations[0]
    fatigued_entry = fatigued.interpretations[0]
    assert clean_entry.distorted is False
    assert clean_entry.confidence == 0.85
    assert clean_entry.reading_relations == (
        ArtifactReadingRelation("water", "at", "north"),
        ArtifactReadingRelation("food", "at", "south"),
    )
    assert fatigued_entry.distorted is True
    assert fatigued_entry.confidence == 0.55
    assert fatigued_entry.reading_relations == (
        ArtifactReadingRelation("water", "at", "north"),
    )
    assert clean_entry.reading_marks == fatigued_entry.reading_marks == ("water", "north")
    projected = ObserverArtifact(
        artifact_id="art-1",
        kind="sign",
        author_id="body-author",
        created_tick=0,
        content_revision=0,
        location_id="clearing",
        marks=("water", "north"),
    )
    assert projected.marks == clean_entry.reading_marks
    assert projected.marks == fatigued_entry.reading_marks
    assert not hasattr(projected, "reading_relations")
    assert not hasattr(projected, "distorted")


def test_higher_revision_replaces_entry() -> None:
    first = apply_artifact_interpretation_update(
        _observe(_artifact(revision=0, marks=("old",)), tick=1),
        _agent(),
    )
    second = apply_artifact_interpretation_update(
        _observe(_artifact(revision=2, marks=("new",)), tick=2),
        _agent(),
        first,
    )
    assert len(second.interpretations) == 1
    assert second.interpretations[0].observed_revision == 2
    assert second.interpretations[0].reading_marks == ("new",)


def test_lower_revision_does_not_replace() -> None:
    first = apply_artifact_interpretation_update(
        _observe(_artifact(revision=3, marks=("kept",)), tick=1),
        _agent(),
    )
    second = apply_artifact_interpretation_update(
        _observe(_artifact(revision=1, marks=("ignored",)), tick=2),
        _agent(),
        first,
    )
    assert second.interpretations[0].reading_marks == ("kept",)
    assert second.interpretations[0].observed_revision == 3


def test_cap_exceeded_drops_further(
    caplog: pytest.LogCaptureFixture,
) -> None:
    prior_entries = [
        ArtifactInterpretation(
            artifact_id=EntityId(f"art-{index}"),
            observed_revision=0,
            reading_marks=("mark",),
            reading_relations=(),
            confidence=0.85,
            distorted=False,
            source_tick=0,
        )
        for index in range(16)
    ]
    previous = ArtifactInterpretationLedger(
        owner_id=_agent(),
        interpretations=tuple(prior_entries),
    )
    observation = _observe(_artifact(artifact_id="art-new"), tick=1)
    with caplog.at_level(logging.WARNING, logger="agents.cognition.artifacts"):
        ledger = apply_artifact_interpretation_update(
            observation, _agent(), previous
        )
    assert len(ledger.interpretations) == 16
    assert "art-new" not in {item.artifact_id.value for item in ledger.interpretations}
    assert "cap_exceeded" in ledger.notices
    assert "cap_exceeded" in caplog.text


def test_foreign_ledger_and_forbidden_inputs_fail_closed() -> None:
    observation = _observe()
    foreign = empty_artifact_interpretation_ledger(_agent("ben"))
    with pytest.raises(TypeError, match="foreign_ledger"):
        apply_artifact_interpretation_update(observation, _agent(), foreign)

    class WorldState:
        pass

    class WorldEvent:
        pass

    class PhysicalRules:
        pass

    for forbidden in (WorldState(), WorldEvent(), PhysicalRules()):
        with pytest.raises(TypeError, match="forbidden_input"):
            apply_artifact_interpretation_update(forbidden, _agent())

    with pytest.raises(TypeError, match="forbidden_input"):
        apply_artifact_interpretation_update(
            observation, _agent(), {"metric_family": "x", "availability": "y"}
        )


def test_require_owner_passthrough_and_reject() -> None:
    require_owner_artifact_interpretations(None, _agent(), field_name="x")
    ledger = empty_artifact_interpretation_ledger(_agent())
    require_owner_artifact_interpretations(ledger, _agent(), field_name="x")
    with pytest.raises(TypeError):
        require_owner_artifact_interpretations(object(), _agent(), field_name="x")
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_artifact_interpretations(
            empty_artifact_interpretation_ledger(_agent("ben")),
            _agent(),
            field_name="x",
        )


def test_inscribe_preference_and_penalties(
    caplog: pytest.LogCaptureFixture,
) -> None:
    observation = _observe(bodies=())
    futures = (
        SimpleNamespace(future_id="f-comm", direction=ActionDirection.COMMUNICATE),
        SimpleNamespace(future_id="f-wait", direction=ActionDirection.WAIT),
        SimpleNamespace(future_id="f-move", direction=ActionDirection.MOVE),
    )
    assert artifact_inscribe_preferred(
        observation,
        futures,
        mode=ArtifactInterpretationMode.DETERMINISTIC,
        inbox=(),
    )
    penalties = artifact_inscribe_penalties(
        observation,
        futures,
        mode=ArtifactInterpretationMode.DETERMINISTIC,
        inbox=(),
    )
    assert penalties == {"f-wait": 0.30, "f-move": 0.30}

    with_listener = _observe(
        bodies=(
            VisibleBody(
                entity_id=EntityId("body-ben"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
        )
    )
    assert not artifact_inscribe_preferred(
        with_listener,
        futures,
        mode=ArtifactInterpretationMode.DETERMINISTIC,
        inbox=(),
    )
    assert (
        artifact_inscribe_penalties(
            with_listener,
            futures,
            mode=ArtifactInterpretationMode.DETERMINISTIC,
            inbox=(),
        )
        == {}
    )

    with caplog.at_level(logging.INFO, logger="agents.cognition.artifacts"):
        missing = artifact_inscribe_penalties(
            observation,
            (SimpleNamespace(future_id="f-wait", direction=ActionDirection.WAIT),),
            mode=ArtifactInterpretationMode.DETERMINISTIC,
            inbox=(),
        )
    assert missing == {}
    assert "no_candidate" in caplog.text


def test_inscribe_command_only_when_preferred() -> None:
    observation = _observe()
    talk = Talk(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-ada"),
            communication_id="c1",
        ),
    )
    compiled = artifact_inscribe_command(
        talk,
        observation=observation,
        mode=ArtifactInterpretationMode.DETERMINISTIC,
        preferred=True,
        inbox=(),
    )
    assert type(compiled) is Inscribe
    assert compiled.kind is ArtifactKind.NOTE
    assert compiled.content == ArtifactContent()
    assert compiled.hold is False

    unchanged = artifact_inscribe_command(
        talk,
        observation=observation,
        mode=ArtifactInterpretationMode.DISABLED,
        preferred=True,
        inbox=(),
    )
    assert unchanged is talk

    withheld = artifact_inscribe_command(
        Wait(),
        observation=observation,
        mode=ArtifactInterpretationMode.DETERMINISTIC,
        preferred=True,
        inbox=(),
    )
    assert type(withheld) is Wait


def test_module_does_not_import_private_world_or_analysis() -> None:
    import agents.cognition.artifacts as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "world._state" not in source
    assert "import analysis" not in source
    assert "from analysis" not in source
    assert "world._operations" not in source
