"""External carrier survival, loss, and later learning without telepathy."""

from __future__ import annotations

from agents.cognition.artifacts import (
    ArtifactInterpretation,
    ArtifactInterpretationLedger,
)
from agents.cognition.institutional_memory import (
    InstitutionalBindingKind,
    InstitutionalFact,
    InstitutionalMemoryChannel,
    apply_institutional_memory_update,
    empty_institutional_memory_ledger,
)
from agents.cognition.institutional_memory_frames import (
    InstitutionalMemoryFrame,
    decode_institutional_marks,
    encode_institutional_marks,
    institutional_frame_relation,
    institutional_frame_root,
)
from agents.cognition.models import (
    CounterpartBinding,
    OwnerSafeSocialIdentity,
)
from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.journal import (
    _decode_information_artifact,
    _encode_information_artifact,
)
from simulation.lifecycle import ActionSubmission
from simulation.runner_models import example_durable_records_spec
from tests.physical_helpers import physical_config, two_location_fixture
from world.actions import CopyRecord, DamageRecord, Inscribe
from world.artifacts import ArtifactContent, ArtifactKind, DurableRecordGenre
from world.communications import origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
)

_BODY_A = EntityId("body-1")
_BODY_B = EntityId("body-2")
_AGENT_A = AgentId("agent-1")
_AGENT_B = AgentId("agent-2")
_CONTEXT = "c_" + "a" * 16


def _frame(*, root: str | None = None) -> InstitutionalMemoryFrame:
    return InstitutionalMemoryFrame(
        binding_kind=InstitutionalBindingKind.ROLE,
        function_token="exchange_aaaaaaaa",
        context_digest=_CONTEXT,
        root=root or institutional_frame_root("continuity-root"),
        parent="p_none",
        facts=(InstitutionalFact("trade", "owes", "grain"),),
        declared_fact_count=1,
    )


def _identity(agent: AgentId, body: EntityId) -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(owner_id=agent, owner_entity_id=body)


def _reading(artifact, *, confidence: float = 0.8):
    return ArtifactInterpretationLedger(
        owner_id=_AGENT_B,
        interpretations=(
            ArtifactInterpretation(
                artifact_id=artifact.entity_id,
                observed_revision=artifact.content_revision,
                reading_marks=artifact.content.marks,
                reading_relations=(),
                confidence=confidence,
                distorted=False,
                source_tick=1,
            ),
        ),
    )


def test_physical_record_survives_author_and_replay() -> None:
    engine = WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
    )
    frame = _frame()
    marks = encode_institutional_marks(frame)
    batch = engine.observe()
    created = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                _AGENT_A,
                Inscribe(
                    ArtifactKind.RECORD,
                    ArtifactContent(marks=marks),
                    record_genre=DurableRecordGenre.CHRONICLE,
                ),
            ),
        )
    )
    assert created.resolutions[0].status.value == "applied"
    batch = engine.observe()
    artifact = batch.for_observer(_BODY_B).artifacts[0]
    assert decode_institutional_marks(artifact.content.marks) == frame

    encoded = _encode_information_artifact(
        engine._snapshot.world.state.artifacts[artifact.entity_id]
    )
    restored = _decode_information_artifact(encoded, path="$")
    assert restored.content.marks == marks
    assert decode_institutional_marks(restored.content.marks) == frame

    engine.resolve_tick(
        (ActionSubmission(batch.token, _AGENT_A, CopyRecord(artifact.entity_id)),)
    )
    batch = engine.observe()
    child = next(
        item
        for item in batch.for_observer(_BODY_B).artifacts
        if item.entity_id != artifact.entity_id
    )
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, _AGENT_A, DamageRecord(artifact.entity_id, "destroy")
            ),
        )
    )
    batch = engine.observe()
    survivors = batch.for_observer(_BODY_B).artifacts
    assert all(item.entity_id != artifact.entity_id for item in survivors)
    survivor = next(item for item in survivors if item.entity_id == child.entity_id)
    assert decode_institutional_marks(survivor.content.marks) == frame


def test_successor_starts_empty_then_learns_from_visible_record() -> None:
    engine = WorldEngine(
        config=physical_config(1),
        bootstrap=two_location_fixture().as_bootstrap(),
        artifacts_enabled=True,
        durable_records_spec=example_durable_records_spec(),
    )
    frame = _frame()
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                _AGENT_A,
                Inscribe(
                    ArtifactKind.RECORD,
                    ArtifactContent(marks=encode_institutional_marks(frame)),
                    record_genre=DurableRecordGenre.CHRONICLE,
                ),
            ),
        )
    )
    batch = engine.observe()
    observation = batch.for_observer(_BODY_B)
    artifact = observation.artifacts[0]
    empty = empty_institutional_memory_ledger(_AGENT_B)
    assert empty.entries == ()
    learned = apply_institutional_memory_update(
        owner_id=_AGENT_B,
        observation=observation,
        identity=_identity(_AGENT_B, _BODY_B),
        previous=empty,
        artifact_interpretations=_reading(artifact),
    )
    assert len(learned.entries) == 1
    assert learned.entries[0].facts[0].object == "grain"
    assert learned.entries[0].provenance[0].immediate_channel in {
        InstitutionalMemoryChannel.RECORD,
        InstitutionalMemoryChannel.OBSERVATION,
    }


def test_hidden_carrier_yields_no_acquisition() -> None:
    ledger = apply_institutional_memory_update(
        owner_id=_AGENT_B,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=_BODY_B,
            revision=WorldRevision(1),
            tick=1,
        ),
        identity=_identity(_AGENT_B, _BODY_B),
        previous=empty_institutional_memory_ledger(_AGENT_B),
    )
    assert ledger.entries == ()


def test_teaching_chain_passes_only_acquired_facts() -> None:
    frame = _frame()
    relation = institutional_frame_relation(frame, teaching=True)
    assert relation is not None
    utterance = origin_utterance(
        text="teaching",
        speaker_id=_BODY_A,
        communication_id="teach-1",
        relations=(relation,),
    )
    a_to_b = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=0,
            source_event_id=EventId("teach-1"),
        ),
        speaker_id=_BODY_A,
        listener_id=_BODY_B,
        utterance=utterance,
        action_kind="tell",
    )
    observation_b = Observation(
        world_id=WorldId("world-1"),
        observer_id=_BODY_B,
        revision=WorldRevision(1),
        tick=1,
        communications=(a_to_b,),
    )
    identity_b = OwnerSafeSocialIdentity(
        owner_id=_AGENT_B,
        owner_entity_id=_BODY_B,
        counterparts=(CounterpartBinding(agent_id=_AGENT_A, entity_id=_BODY_A),),
    )
    learned_b = apply_institutional_memory_update(
        owner_id=_AGENT_B,
        observation=observation_b,
        identity=identity_b,
        previous=empty_institutional_memory_ledger(_AGENT_B),
        teaching_enabled=True,
    )
    teaching_entries = [
        entry
        for entry in learned_b.entries
        if entry.provenance[0].immediate_channel is InstitutionalMemoryChannel.TEACHING
    ]
    assert len(teaching_entries) == 1
    assert teaching_entries[0].facts[0].object == "grain"

    # B can pass on only what B retained; no peer ledger is read.
    forwarded = institutional_frame_relation(
        _frame(
            root=teaching_entries[0].provenance[0].declared_frame_root or _frame().root
        ),
        teaching=True,
    )
    assert forwarded is not None
    assert forwarded.object
