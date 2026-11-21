# mypy: ignore-errors
"""V4-33 carrier markers, addressed delivery, teaching, and record reading."""

from __future__ import annotations

import dataclasses

import pytest

from agents.cognition.artifacts import (
    ArtifactInterpretation,
    ArtifactInterpretationLedger,
    ArtifactReadingRelation,
)
from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    ExperimentHypothesis,
    HypothesisClaim,
    HypothesisRevision,
    HypothesisRevisionReason,
    HypothesisStatus,
    admit_hypothesis,
    empty_experiment_ledger,
    experiment_hypothesis_id,
)
from agents.cognition.scientific_hypothesis_communication import (
    adopt_communicated_hypothesis,
    encode_scientific_hypothesis_claim,
    parse_scientific_hypothesis_claim_relation,
)
from agents.cognition.teaching import (
    AdviceAct,
    AdviceBand,
    AdviceDomain,
    AdviceStore,
    DeclarativeAdvice,
)
from agents.models import AgentId
from analysis.science_diffusion_contract import (
    DiffusionError,
    DiffusionLane,
    DiffusionOccurrence,
    DiffusionReason,
    DiffusionResolution,
    DiffusionStage,
    EvidenceKind,
    EvidenceRef,
    HypothesisDescriptor,
    ScienceKind,
    ScienceVersion,
    ScienceVersionKey,
)
from experiments.catalog import (
    base_runner_config_from_scenario,
    experiment_scientific_institutions,
)
from experiments.science_diffusion_carriers import (
    CarrierMarker,
    decode_marker,
    encode_call_triples,
    encode_marker_triples,
    project_carrier_occurrences,
    qualified_version_digest,
    receipt_digest,
)
from simulation.models import RunId, StochasticIdentity
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    ArtifactRelation,
    InformationArtifact,
    RecordIntegrity,
)
from world.communications import (
    CommunicationContent,
    CommunicationId,
    CommunicationRelation,
    CommunicationSourceBasis,
    DeclaredTransmission,
    StructuredUtterance,
)
from world.events import Talked, WorldEvent
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.values import ItemKind

pytestmark = pytest.mark.unit

RUN = "run-sdf-carriers"


def _config():
    body_1 = alive_body("body-1", inventory=(EntityId("wood-1"),))
    body_2 = alive_body(
        "body-2",
        location_id="loc-2",
        inventory=(EntityId("wood-2"),),
    )
    base = base_runner_config_from_scenario(
        seed=73,
        stochastic_identity=StochasticIdentity("sdf-carriers"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-sdf-carriers"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(
                make_location("loc-1", adjacent=("loc-2",)),
                make_location("loc-2", adjacent=("loc-1",)),
            ),
            bodies=(body_1, body_2),
            items=(
                make_item(
                    "wood-1",
                    name="wood",
                    kind=ItemKind.MATERIAL,
                    location_id=None,
                    holder_id="body-1",
                ),
                make_item(
                    "wood-2",
                    name="wood",
                    kind=ItemKind.MATERIAL,
                    location_id=None,
                    holder_id="body-2",
                ),
            ),
            weather=(make_weather("loc-1"), make_weather("loc-2")),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-1"),
                entity_id=body_1.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-1")),
            ),
            AgentRunnerSpec(
                agent_id=AgentId("agent-2"),
                entity_id=body_2.entity_id,
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-2")),
            ),
        ),
        max_ticks=96,
    )
    definition = experiment_scientific_institutions(base, max_ticks=96)
    return {row.condition_id: row.runner_config for row in definition.conditions}[
        "institutions-combined-v56"
    ]


def _key(revision: int = 0) -> ScienceVersionKey:
    return ScienceVersionKey(
        run_id=RUN,
        owner_id="agent-1",
        kind=ScienceKind.HYPOTHESIS,
        local_id=_sender_hypothesis().hypothesis_id,
        revision_index=revision,
    )


def test_marker_round_trip_and_split_shape() -> None:
    key = _key()
    triples = encode_marker_triples(key)
    assert len(triples) == 2
    assert triples[0][0] == "sdf_v1"
    assert triples[0][2].startswith("a") and len(triples[0][2]) == 27
    assert triples[1][2].startswith("b") and len(triples[1][2]) == 27
    marker = decode_marker(_relations(triples))
    assert marker == CarrierMarker(source_digest=qualified_version_digest(key))

    variant = _key(1)
    optional = encode_marker_triples(key, variant=variant)
    decoded = decode_marker(_relations(optional))
    assert decoded is not None
    assert decoded.variant_digest == qualified_version_digest(variant)

    digest = receipt_digest(
        run_id=RUN,
        carrier_kind="speech:marker_report",
        reference="evt-1",
        recipient_id="agent-2",
    )
    relay = encode_marker_triples(key, prior=digest)
    relay_marker = decode_marker(_relations(relay))
    assert relay_marker is not None
    assert relay_marker.prior_digest == digest

    call_triples = encode_call_triples("term", "translate", "object")
    call_marker = decode_marker(_relations(triples + call_triples))
    assert call_marker is not None
    assert call_marker.call_digest


def test_marker_rejects_missing_halves_duplicates_and_unknowns() -> None:
    key = _key()
    triples = encode_marker_triples(key)
    with pytest.raises(DiffusionError):
        decode_marker(_relations(triples[:1]))
    with pytest.raises(DiffusionError):
        decode_marker(_relations((triples[0], triples[0], triples[1])))
    with pytest.raises(DiffusionError):
        decode_marker(
            _relations(
                (
                    ("sdf_v1", "source_a", triples[0][2]),
                    ("sdf_v1", "source_b", triples[1][2]),
                    ("sdf_v1", "unknown_a", triples[0][2]),
                )
            )
        )
    with pytest.raises(DiffusionError):
        decode_marker(_relations((("sdf_v1", "source_a", "a123"),)))
    with pytest.raises(DiffusionError):
        encode_marker_triples(_key(), variant=_key())


def test_version_digest_is_deterministic_and_owner_scoped() -> None:
    assert qualified_version_digest(_key()) == qualified_version_digest(_key())
    other = ScienceVersionKey(
        run_id=RUN,
        owner_id="agent-2",
        kind=ScienceKind.HYPOTHESIS,
        local_id="h1",
        revision_index=0,
    )
    assert qualified_version_digest(_key()) != qualified_version_digest(other)


@pytest.mark.asyncio
async def test_speech_adoption_teaching_and_record_reading() -> None:
    config = _config()
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId(RUN),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        await runner.initialize_finalized_boundary()
        boundary = await runner.export_finalized_research_boundary()
        inventory = runner.engine.detached_objective_facts()

    hypothesis = _sender_hypothesis()
    relation = encode_scientific_hypothesis_claim(hypothesis)
    event = _talk_event(relation, tick=1)
    claim = parse_scientific_hypothesis_claim_relation(relation)
    assert claim is not None
    binding = ExperimentCognitionBinding(
        max_hypotheses=8,
        max_trials_per_tick=1,
        repeat_threshold=2,
        learn_into_genealogy=False,
        allow_provider=False,
    )
    sender = admit_hypothesis(
        empty_experiment_ledger(AgentId("agent-1"), binding), hypothesis
    )
    recipient = adopt_communicated_hypothesis(
        empty_experiment_ledger(AgentId("agent-2"), binding),
        claim,
        source_token=f"evt:{event.event_id.value}",
        tick=1,
    )
    advice = AdviceStore(
        owner_id=AgentId("agent-2"),
        rows=(
            DeclarativeAdvice(
                occurrence_id=event.event_id.value,
                source_agent_id=AgentId("agent-1"),
                act=AdviceAct.EXPLAIN,
                domain=AdviceDomain.CRAFTING,
                band=AdviceBand.HIGH,
                delivery_tick=1,
            ),
        ),
    )
    artifact = _artifact(hypothesis)
    reading = ArtifactInterpretation(
        artifact_id=artifact.artifact_id,
        observed_revision=0,
        reading_marks=(),
        reading_relations=tuple(
            ArtifactReadingRelation(*triple)
            for triple in encode_marker_triples(_source_version().key)
        ),
        confidence=1.0,
        distorted=False,
        source_tick=1,
    )
    interpretations = ArtifactInterpretationLedger(
        owner_id=AgentId("agent-2"), interpretations=(reading,)
    )
    owners = []
    for owner in boundary.owners:
        checkpoint = owner.runtime_checkpoint
        if owner.owner_id == AgentId("agent-1"):
            checkpoint = dataclasses.replace(checkpoint, experiment_ledger=sender)
        else:
            checkpoint = dataclasses.replace(
                checkpoint,
                experiment_ledger=recipient,
                declarative_advice=advice,
                artifact_interpretations=interpretations,
            )
        owners.append(dataclasses.replace(owner, runtime_checkpoint=checkpoint))
    boundary = dataclasses.replace(
        boundary,
        boundary_tick=type(boundary.boundary_tick)(2),
        boundary_revision=WorldRevision(2),
        owners=tuple(owners),
        events=(event,),
    )
    inventory = dataclasses.replace(
        inventory,
        tick=2,
        revision=2,
        artifacts=(artifact,),
    )
    projection = project_carrier_occurrences(
        boundary,
        inventory,
        versions=(_source_version(),),
        observed_boundary=2,
    )
    lanes = {row.lane for row in projection.occurrences}
    assert DiffusionLane.SPEECH in lanes
    assert DiffusionLane.TEACHING in lanes
    assert DiffusionLane.RECORDS in lanes
    adopted = [
        row
        for row in projection.occurrences
        if row.lane is DiffusionLane.SPEECH and row.stage is DiffusionStage.ADOPTED
    ]
    assert adopted and adopted[0].source_version == _source_version().key
    teaching = [
        row for row in projection.occurrences if row.lane is DiffusionLane.TEACHING
    ]
    assert teaching and teaching[0].detail == (("advice_act", "explain"),)
    readings = [
        row for row in projection.occurrences if row.lane is DiffusionLane.RECORDS
    ]
    assert readings and readings[0].resolution is DiffusionResolution.CONFIRMED


def test_relay_requires_exact_prior_receipt() -> None:
    key = _key()
    prior = DiffusionOccurrence(
        run_id=RUN,
        lane=DiffusionLane.SPEECH,
        occurrence_kind="marker_report",
        tick=1,
        first_observed_boundary=1,
        evidence=EvidenceRef(
            kind=EvidenceKind.EVENT,
            run_id=RUN,
            tick=1,
            event_id="evt-1",
            sequence=0,
        ),
        stage=DiffusionStage.REPORTED_REFERENCE,
        actor_id="agent-2",
        counterparty_id="agent-1",
        source_version=key,
    )
    digest = receipt_digest(
        run_id=RUN,
        carrier_kind="speech:marker_report",
        reference=prior.evidence.qualified_key().__repr__(),
        recipient_id="agent-1",
    )
    marker = CarrierMarker(
        source_digest=qualified_version_digest(key), prior_digest=digest
    )
    occurrence = _marker_occurrence(marker, prior=(prior,))
    assert occurrence.resolution is DiffusionResolution.CONFIRMED
    wrong = dataclasses.replace(prior, counterparty_id="agent-9")
    rejected = _marker_occurrence(marker, prior=(wrong,))
    assert rejected.resolution is DiffusionResolution.UNRESOLVED
    assert rejected.reason is DiffusionReason.RELAY_PARENT_MISSING


def _relations(triples):
    return tuple(CommunicationRelation(*triple) for triple in triples)


def _sender_hypothesis() -> ExperimentHypothesis:
    claim = HypothesisClaim(
        operator=ExperimentOperator.COMBINE,
        operand_a_id="wood-1",
        operand_b_id=None,
        process_token=ExperimentProcessToken.HARVEST,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
    )
    hypothesis_id = experiment_hypothesis_id(
        AgentId("agent-1"),
        claim.operator,
        claim.operand_a_id,
        claim.operand_b_id,
        claim.process_token,
    )
    revision = HypothesisRevision(
        revision_index=0,
        tick=0,
        reason=HypothesisRevisionReason.FORMULATED,
        claim=claim,
        confidence_milli=500,
    )
    return ExperimentHypothesis(
        owner_id=AgentId("agent-1"),
        hypothesis_id=hypothesis_id,
        operator=claim.operator,
        operand_a_id=claim.operand_a_id,
        operand_b_id=claim.operand_b_id,
        process_token=claim.process_token,
        predicted_outcome=claim.predicted_outcome.value,
        confidence_milli=500,
        status=HypothesisStatus.PROVISIONAL,
        revisions=(revision,),
    )


def _source_version() -> ScienceVersion:
    hypothesis = _sender_hypothesis()
    key = ScienceVersionKey(
        run_id=RUN,
        owner_id="agent-1",
        kind=ScienceKind.HYPOTHESIS,
        local_id=hypothesis.hypothesis_id,
        revision_index=0,
    )
    return ScienceVersion(
        key=key,
        occurrence_tick=0,
        first_observed_boundary=0,
        wire=(
            ("confidence", "500"),
            ("evidence_ref", "none"),
            ("reason", "formulated"),
            ("source_kind", "self_formulated"),
            ("source_token", "self"),
            ("status", "provisional"),
        ),
        hypothesis=HypothesisDescriptor(
            operator="combine",
            operand_refs=("item:wood-1",),
            process="harvest",
            predicted_outcome="success",
            conditions=(),
        ),
        evidence=EvidenceRef(
            kind=EvidenceKind.OWNER_ROW,
            run_id=RUN,
            tick=0,
            owner_id="agent-1",
            local_id=hypothesis.hypothesis_id,
            revision_index=0,
        ),
    )


def _talk_event(relation: CommunicationRelation, *, tick: int) -> WorldEvent:
    content = CommunicationContent(text="shared claim", relations=(relation,))
    declared = DeclaredTransmission(
        communication_id=CommunicationId("comm-1"),
        immediate_source_id=EntityId("body-1"),
        parent_communication_id=None,
        root_communication_id=CommunicationId("comm-1"),
        source_agent_chain=(EntityId("body-1"),),
        hop_count=0,
        sender_confidence=0.5,
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    utterance = StructuredUtterance(content=content, declared=declared)
    return WorldEvent(
        event_id=EventId("evt-talk-1"),
        run_id=RUN,
        world_id=WorldId("world-sdf-carriers"),
        tick=tick,
        sequence=0,
        request_id=RequestId("req-talk-1"),
        resulting_revision=WorldRevision(tick),
        schema_version=2,
        target_id=EntityId("body-2"),
        actor_id=EntityId("body-1"),
        details=Talked(recipient_id=EntityId("body-2"), utterance=utterance),
    )


def _artifact(hypothesis: ExperimentHypothesis) -> InformationArtifact:
    triples = encode_marker_triples(_source_version().key)
    return InformationArtifact(
        artifact_id=EntityId("artifact-1"),
        kind=ArtifactKind.RECORD,
        author_id=EntityId("body-1"),
        created_tick=1,
        content=ArtifactContent(
            relations=tuple(ArtifactRelation(*triple) for triple in triples)
        ),
        content_revision=0,
        location_id=EntityId("loc-2"),
        integrity=RecordIntegrity.INTACT,
    )


def _marker_occurrence(
    marker: CarrierMarker, *, prior: tuple[DiffusionOccurrence, ...]
) -> DiffusionOccurrence:
    from experiments.science_diffusion_carriers import _marker_speech_occurrence

    by_digest = {qualified_version_digest(_key()): _key()}
    receipts = {}
    for row in prior:
        digest = receipt_digest(
            run_id=RUN,
            carrier_kind=f"{row.lane.value}:{row.occurrence_kind}",
            reference=row.evidence.qualified_key().__repr__(),
            recipient_id=row.counterparty_id,
        )
        receipts[digest] = row
    return _marker_speech_occurrence(
        marker,
        event=_talk_event(
            CommunicationRelation("hyp_v1", "claim", "x"), tick=2
        ),
        run_id=RUN,
        speaker="agent-1",
        recipient="agent-2",
        observed_boundary=2,
        by_digest=by_digest,
        by_key={_key(): _source_version()},
        prior_receipts=receipts,
        versions=(_source_version(),),
    )
