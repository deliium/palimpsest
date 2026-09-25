"""Enabled identity projection reads revision history, not policy ids."""

from __future__ import annotations

import logging

import pytest

from agents.cognition import (
    CognitionIdentityMode,
    build_identity_claim,
    project_identity_state,
    project_self_model,
)
from agents.cognition.defaults import DirectSelfStateProjector
from agents.cognition.models import (
    CognitiveLoopInput,
    InternalAgentState,
    RetrievedMemoryContext,
    SituationClaimCode,
    SituationModel,
)
from agents.models import AgentId
from memory.belief_formation import DEFAULT_BELIEF_FORMATION_POLICY
from memory.belief_service import InMemorySemanticBeliefService
from memory.beliefs import (
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefEvidenceBundle,
    BeliefEvidenceContribution,
    BeliefPolicyRef,
    BeliefRevision,
    BeliefRevisionId,
    BeliefRevisionRequest,
    BeliefValueKind,
    ClaimValue,
    EvidenceStance,
    SemanticBelief,
    SemanticBeliefHistory,
)
from memory.models import BeliefId, MemoryId, MemoryRunId, MemoryScope
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _scope() -> MemoryScope:
    return MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))


def _bundle(*memory_ids: str, contradict: tuple[str, ...] = ()) -> BeliefEvidenceBundle:
    supporting = []
    contradicting = []
    ordinal = 0
    for memory_id in memory_ids:
        supporting.append(
            BeliefEvidenceContribution(
                memory_id=MemoryId(memory_id),
                stance=EvidenceStance.SUPPORTING,
                contribution=0.5,
                ordinal=ordinal,
                lineage_root_id=MemoryId(memory_id),
            )
        )
        ordinal += 1
    for memory_id in contradict:
        contradicting.append(
            BeliefEvidenceContribution(
                memory_id=MemoryId(memory_id),
                stance=EvidenceStance.CONTRADICTING,
                contribution=0.2,
                ordinal=ordinal,
                lineage_root_id=MemoryId(memory_id),
            )
        )
        ordinal += 1
    return BeliefEvidenceBundle(
        supporting=tuple(supporting), contradicting=tuple(contradicting)
    )


def _history(
    *,
    belief_id: str,
    predicate: str,
    ticks: tuple[int, ...],
    confidences: tuple[float, ...],
    activation: BeliefActivationState,
    support_ids: tuple[str, ...],
    contradict_ids: tuple[str, ...] = (),
) -> SemanticBeliefHistory:
    owner = AgentId("agent-1")
    claim = build_identity_claim(
        owner,
        predicate,
        ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )
    revisions: list[BeliefRevision] = []
    previous: BeliefRevisionId | None = None
    for ordinal, (tick, confidence) in enumerate(zip(ticks, confidences, strict=True)):
        revision_id = BeliefRevisionId(f"{belief_id}-rev-{ordinal}")
        revisions.append(
            BeliefRevision(
                revision_id=revision_id,
                belief_id=BeliefId(belief_id),
                owner_id=owner,
                ordinal=ordinal,
                logical_tick=tick,
                claim=claim,
                confidence=BeliefConfidenceState(
                    confidence=confidence,
                    support_mass=confidence,
                    contradiction_mass=0.0,
                ),
                evidence=_bundle(*support_ids, contradict=contradict_ids)
                if ordinal == len(ticks) - 1
                else _bundle(support_ids[0]),
                activation_state=activation,
                policy=BeliefPolicyRef(
                    policy_id="semantic-belief-formation", version="1"
                ),
                previous_revision_id=previous,
            )
        )
        previous = revision_id
    head = revisions[-1]
    belief = SemanticBelief(
        belief_id=BeliefId(belief_id),
        owner_id=owner,
        claim=claim,
        confidence=head.confidence,
        activation_state=activation,
        current_revision_id=head.revision_id,
        revision_ordinal=head.ordinal,
        created_tick=ticks[0],
        updated_tick=ticks[-1],
        policy=BeliefPolicyRef(policy_id="semantic-belief-formation", version="1"),
        evidence_support_count=len(support_ids),
        evidence_contradiction_count=len(contradict_ids),
    )
    return SemanticBeliefHistory(belief=belief, revisions=tuple(revisions))


def test_formation_thresholds_stay_on_the_default_policy() -> None:
    assert DEFAULT_BELIEF_FORMATION_POLICY.min_independent_observations == 2
    assert DEFAULT_BELIEF_FORMATION_POLICY.activate_confidence_threshold == 0.4
    assert DEFAULT_BELIEF_FORMATION_POLICY.policy_id == "semantic-belief-formation"


@pytest.mark.asyncio
async def test_projection_includes_candidate_and_active_heads() -> None:
    owner = AgentId("agent-1")
    service = InMemorySemanticBeliefService(_scope())
    candidate_claim = build_identity_claim(
        owner,
        "identity.ability.observed_outcome.move_north",
        ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )
    active_claim = build_identity_claim(
        owner,
        "identity.competence.observed_outcome.move_north",
        ClaimValue(kind=BeliefValueKind.BOOL, bool_value=True),
    )
    await service.revise(
        BeliefRevisionRequest(
            owner_id=owner,
            operation_id="op-candidate",
            logical_tick=1,
            claim=candidate_claim,
            evidence=_bundle("mem-1"),
            policy=DEFAULT_BELIEF_FORMATION_POLICY.as_ref(),
        )
    )
    active = await service.revise(
        BeliefRevisionRequest(
            owner_id=owner,
            operation_id="op-active-1",
            logical_tick=1,
            claim=active_claim,
            evidence=_bundle("mem-2"),
            policy=DEFAULT_BELIEF_FORMATION_POLICY.as_ref(),
        )
    )
    active = await service.revise(
        BeliefRevisionRequest(
            owner_id=owner,
            operation_id="op-active-2",
            logical_tick=2,
            claim=active_claim,
            evidence=_bundle("mem-3"),
            policy=DEFAULT_BELIEF_FORMATION_POLICY.as_ref(),
            belief_id=active.belief_id,
            expected_revision_ordinal=0,
        )
    )
    candidate_belief = next(
        item
        for item in await service.snapshot()
        if item.claim.predicate.startswith("identity.ability")
    )
    assert candidate_belief.activation_state is BeliefActivationState.CANDIDATE
    assert active.activation_state is BeliefActivationState.ACTIVE
    histories = []
    for belief in await service.snapshot():
        history = await service.history(belief.belief_id)
        assert history is not None
        histories.append(history)
    state = project_identity_state(owner_id=owner, histories=tuple(histories))
    by_aspect = {view.aspect.value: view for view in state.views}
    assert by_aspect["ability"].activation is BeliefActivationState.CANDIDATE
    assert by_aspect["competence"].activation is BeliefActivationState.ACTIVE
    assert by_aspect["ability"].provenance.value == "observed_outcome"
    assert by_aspect["ability"].claim.value.bool_value is True
    retired = _history(
        belief_id="belief-retired",
        predicate="identity.weakness.observed_outcome.move_north",
        ticks=(1,),
        confidences=(0.5,),
        activation=BeliefActivationState.RETIRED,
        support_ids=("mem-r",),
    )
    without_retired = project_identity_state(
        owner_id=owner, histories=(*histories, retired)
    )
    assert all(view.aspect.value != "weakness" for view in without_retired.views)


def test_histories_change_stability_rate_and_provenance() -> None:
    owner = AgentId("agent-1")
    short = _history(
        belief_id="belief-short",
        predicate="identity.ability.observed_outcome.move_north",
        ticks=(1,),
        confidences=(0.4,),
        activation=BeliefActivationState.CANDIDATE,
        support_ids=("mem-1",),
        contradict_ids=("mem-x",),
    )
    long = _history(
        belief_id="belief-long",
        predicate="identity.ability.own_choice.forage",
        ticks=tuple(range(1, 9)),
        confidences=(0.4,) * 8,
        activation=BeliefActivationState.ACTIVE,
        support_ids=("mem-1", "mem-2", "mem-3"),
    )
    left = project_identity_state(owner_id=owner, histories=(short,))
    right = project_identity_state(owner_id=owner, histories=(long,))
    assert left.views[0].derived_stability < right.views[0].derived_stability
    assert left.views[0].derived_rate < right.views[0].derived_rate
    assert left.views[0].provenance.value == "observed_outcome"
    assert right.views[0].provenance.value == "own_choice"
    assert short.belief.policy.policy_id == "semantic-belief-formation"
    assert "move_north" not in repr(left)
    model = project_self_model(
        owner_id=owner,
        life_status=LifeStatus.ALIVE,
        beliefs=(short.belief,),
    )
    assert model.identity is None


def test_unknown_predicate_segment_fails_closed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    owner = AgentId("agent-1")
    history = _history(
        belief_id="belief-bad",
        predicate="identity.ability.observed_outcome.move_north",
        ticks=(1,),
        confidences=(0.4,),
        activation=BeliefActivationState.CANDIDATE,
        support_ids=("mem-1",),
    )
    broken_claim = history.belief.claim
    object.__setattr__(
        broken_claim,
        "predicate",
        "identity.warrior.observed_outcome.move_north",
    )
    with caplog.at_level(logging.ERROR, logger="agents.cognition.models"):
        with pytest.raises(ValueError, match="unknown_aspect"):
            project_identity_state(owner_id=owner, histories=(history,))
    rejected = [
        record
        for record in caplog.records
        if record.message == "identity_projection_rejected"
    ]
    assert rejected[-1].reason_code == "unknown_aspect"
    assert "move_north" not in caplog.text


def _alive_self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


@pytest.mark.asyncio
async def test_projector_fills_identity_only_when_enabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    owner = AgentId("agent-1")
    history = _history(
        belief_id="belief-short",
        predicate="identity.ability.observed_outcome.move_north",
        ticks=(1,),
        confidences=(0.4,),
        activation=BeliefActivationState.CANDIDATE,
        support_ids=("mem-1",),
    )
    loop_input = CognitiveLoopInput(
        agent_id=owner,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
            tick=1,
            self_body=_alive_self(),
        ),
        internal_state=InternalAgentState(owner_id=owner),
    )
    situation = SituationModel(
        owner_id=owner,
        tick=1,
        claim_codes=(SituationClaimCode.LOCAL_SCENE,),
        confidence=1.0,
    )
    memory = RetrievedMemoryContext(
        owner_id=owner,
        memory_ids=(),
        belief_ids=(),
        semantic_beliefs=(history.belief,),
        confidence=1.0,
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.defaults"):
        passthrough = await DirectSelfStateProjector().project(
            loop_input, situation, memory
        )
    assert passthrough.identity is None
    projected = [
        record
        for record in caplog.records
        if record.message == "self_model_projected"
    ]
    assert projected[-1].identity_mode == "passthrough"
    assert projected[-1].identity_belief_count == 0
    enabled = await DirectSelfStateProjector(
        identity_mode=CognitionIdentityMode.ENABLED,
        belief_histories=(history,),
    ).project(loop_input, situation, memory)
    assert enabled.identity is not None
    assert enabled.identity.views[0].activation is BeliefActivationState.CANDIDATE
    assert [item.belief_id.value for item in enabled.beliefs] == []
