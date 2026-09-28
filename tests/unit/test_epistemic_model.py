"""Epistemic ledger contracts and the deterministic updater."""

from __future__ import annotations

import dataclasses
import logging
import math

import pytest

from agents.cognition.epistemic import (
    EPISTEMIC_POLICY_VERSION,
    EpistemicAttitude,
    EpistemicAttribution,
    EpistemicPolicy,
    EpistemicSource,
    default_epistemic_policy,
    epistemic_attribution_id_for,
    epistemic_proposition_ref,
    update_epistemic_state,
)
from agents.cognition.theory_of_mind import (
    THEORY_OF_MIND_POLICY_VERSION,
    MindAspect,
    MindAtom,
    MindEvidenceChannel,
    MindHypothesis,
    MindSlot,
    TheoryOfMind,
    TheoryOfMindPolicy,
    default_theory_of_mind_policy,
    derive_future_actions,
    update_theory_of_mind,
)
from agents.models import AgentId
from memory import (
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefId,
    BeliefPolicyRef,
    BeliefRevisionId,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    SemanticBelief,
    SemanticClaim,
)
from tests.unit.test_theory_of_mind import _occurrence, _watch
from world._state import WorldState
from world.communications import (
    CommunicationContent,
    CommunicationId,
    CommunicationRelation,
    CommunicationSourceBasis,
    DeclaredTransmission,
    StructuredUtterance,
)
from world.identifiers import EntityId, EventId
from world.models import AgentBody, PhysicalRules
from world.observations import (
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
)

_LOG = "agents.cognition.epistemic"
_OWNER = AgentId("agent-alice")
_BOB = "agent-bob"


def _row(
    *,
    nesting_level: int = 1,
    attitude: EpistemicAttitude = EpistemicAttitude.KNOWS,
    modeled_agents: tuple[str, ...] = (),
    proposition_ref: str = "belief:belief-1",
    confidence: float = 0.8,
    contradiction_mass: float = 0.0,
    owner: AgentId = _OWNER,
) -> EpistemicAttribution:
    return EpistemicAttribution(
        owner_id=owner,
        proposition_ref=proposition_ref,
        attitude=attitude,
        support=confidence,
        counter=contradiction_mass,
        confidence=confidence,
        source=EpistemicSource.SEMANTIC_BELIEF,
        nesting_level=nesting_level,
        belief_id="belief-1" if proposition_ref.startswith("belief:") else None,
        modeled_agents=modeled_agents,
        contradiction_mass=contradiction_mass,
        updated_tick=1,
    )


def test_policy_defaults_and_theory_version_stay_put(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOG)
    policy = default_epistemic_policy()
    assert policy.version == EPISTEMIC_POLICY_VERSION
    assert policy.max_depth == 2
    assert policy.hard_ceiling == 3
    assert policy.knows_threshold == pytest.approx(0.8)
    assert policy.believes_threshold == pytest.approx(0.55)
    assert policy.contradiction_threshold == pytest.approx(0.5)
    assert policy.action_threshold == pytest.approx(0.55)
    assert policy.max_attributions == 64
    assert policy.max_history == 32
    assert policy.prior == pytest.approx(1.0)
    assert TheoryOfMindPolicy().version == THEORY_OF_MIND_POLICY_VERSION
    text = caplog.text
    assert "epistemic_policy_constructed" in text
    assert "policy_version=epistemic-model-v1" in text
    assert "nesting_level=2" in text
    assert "attribution_count=0" in text
    assert "food" not in text


def test_row_id_is_stable_and_has_no_child_model(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOG)
    first = _row()
    second = _row()
    assert first.attribution_id == second.attribution_id
    assert first.attribution_id.startswith("ep-")
    assert len(first.attribution_id) == 51
    assert not hasattr(first, "child")
    field_types = {item.type for item in dataclasses.fields(EpistemicAttribution)}
    assert EpistemicAttribution not in field_types
    assert first.attribution_id == epistemic_attribution_id_for(
        owner_id=_OWNER,
        nesting_level=1,
        modeled_agents=(),
        attitude=EpistemicAttitude.KNOWS,
        proposition_ref="belief:belief-1",
    )
    text = caplog.text
    assert "epistemic_attribution_constructed" in text
    assert f"owner_id={_OWNER.value}" in text
    assert "nesting_level=1" in text
    assert "attribution_count=1" in text


def test_level_three_chain_is_legal_and_level_four_is_rejected() -> None:
    legal = _row(
        nesting_level=3,
        modeled_agents=(_BOB, "agent-carol"),
        proposition_ref="fact:ate:none",
        attitude=EpistemicAttitude.KNOWS,
    )
    assert legal.nesting_level == 3
    assert len(legal.modeled_agents) == 2
    with pytest.raises(ValueError, match="epistemic_depth_rejected"):
        _row(nesting_level=4, modeled_agents=(_BOB, "agent-carol", "agent-dave"))
    with pytest.raises(ValueError, match="epistemic_depth_rejected"):
        _row(nesting_level=1, modeled_agents=(_BOB,))
    with pytest.raises(ValueError, match="epistemic_depth_rejected"):
        EpistemicPolicy(max_depth=4)
    with pytest.raises(ValueError, match="epistemic_depth_rejected"):
        EpistemicPolicy(max_depth=-1)


def test_closed_attitudes_and_self_chain(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger=_LOG)
    level2 = _row(
        nesting_level=2,
        modeled_agents=(_BOB,),
        attitude=EpistemicAttitude.DOES_NOT_KNOW,
        proposition_ref="fact:ate:none",
    )
    assert level2.attitude is EpistemicAttitude.DOES_NOT_KNOW
    with pytest.raises(ValueError, match="epistemic_attitude_rejected"):
        _row(attitude=EpistemicAttitude.DOES_NOT_KNOW)
    with pytest.raises(ValueError, match="self_subject"):
        _row(nesting_level=2, modeled_agents=(_OWNER.value,))
    with pytest.raises(ValueError, match="unknown_enum"):
        EpistemicAttribution(
            owner_id=_OWNER,
            proposition_ref="belief:belief-1",
            attitude="knows",  # type: ignore[arg-type]
            support=0.8,
            counter=0.0,
            confidence=0.8,
            source=EpistemicSource.SEMANTIC_BELIEF,
            nesting_level=1,
        )
    with pytest.raises(ValueError, match="not_finite"):
        _row(confidence=math.nan)
    with pytest.raises(ValueError, match="empty_proposition"):
        _row(proposition_ref="")
    text = caplog.text
    assert "epistemic_validation_failed" in text
    assert "field=" in text
    assert "reason_code=" in text
    assert "utterance" not in text


def _belief(
    *,
    belief_id: str = "belief-1",
    confidence: float = 0.8,
    support_mass: float = 1.0,
    contradiction_mass: float = 0.0,
    state: BeliefActivationState = BeliefActivationState.ACTIVE,
    owner: AgentId = _OWNER,
    predicate: str = "at",
    text_value: str = "place-1",
) -> SemanticBelief:
    return SemanticBelief(
        belief_id=BeliefId(belief_id),
        owner_id=owner,
        claim=SemanticClaim(
            subject=ClaimSubject(
                kind=ClaimSubjectKind.CONCEPT,
                concept="food",
            ),
            predicate=predicate,
            value=ClaimValue(kind=BeliefValueKind.TEXT, text_value=text_value),
        ),
        confidence=BeliefConfidenceState(
            confidence=confidence,
            support_mass=support_mass,
            contradiction_mass=contradiction_mass,
        ),
        activation_state=state,
        current_revision_id=BeliefRevisionId(f"rev-{belief_id}"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=1,
        policy=BeliefPolicyRef(policy_id="semantic-v1", version="1"),
        evidence_support_count=1,
        evidence_contradiction_count=0,
    )


def _speech(
    *,
    predicate: str,
    obj: str,
    subject: str = "body-bob",
    hop: int = 1,
    event: str = "evt-speech",
) -> ObservedCommunication:
    current = CommunicationId("comm-tell")
    root = CommunicationId("comm-root")
    speaker = EntityId("body-carol")
    chain = (*(EntityId("body-erin"), EntityId("body-frank"))[:hop], speaker)
    utterance = StructuredUtterance(
        content=CommunicationContent(
            text="hidden-speech",
            concepts=(),
            relations=(
                CommunicationRelation(
                    subject=subject, predicate=predicate, object=obj
                ),
            ),
        ),
        declared=DeclaredTransmission(
            communication_id=current,
            immediate_source_id=speaker,
            parent_communication_id=None if hop == 0 else root,
            root_communication_id=current if hop == 0 else root,
            source_agent_chain=chain,
            hop_count=hop,
            sender_confidence=0.9,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=0,
            source_event_id=EventId(event),
        ),
        speaker_id=speaker,
        listener_id=EntityId("body-alice"),
        utterance=utterance,
        action_kind="tell",
    )


def _level1(
    model: TheoryOfMind, proposition_ref: str
) -> EpistemicAttribution:
    return next(
        item
        for item in model.attributions
        if item.nesting_level == 1 and item.proposition_ref == proposition_ref
    )


def test_proposition_forms_and_empty_ledger_default() -> None:
    assert epistemic_proposition_ref(belief_id="belief-1") == "belief:belief-1"
    assert (
        epistemic_proposition_ref(occurrence_kind="ate", location_id=None)
        == "fact:ate:none"
    )
    assert (
        epistemic_proposition_ref(occurrence_kind="ate", location_id="place-1")
        == "fact:ate:place-1"
    )
    model = TheoryOfMind(owner_id=_OWNER)
    assert model.attributions == ()
    stored = TheoryOfMind(owner_id=_OWNER, attributions=(_row(),))
    assert stored.attributions[0].attribution_id == _row().attribution_id
    with pytest.raises(ValueError, match="owner_mismatch"):
        TheoryOfMind(owner_id=AgentId("agent-other"), attributions=(_row(),))


def test_update_copies_belief_confidence_and_keeps_hypotheses(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOG)
    seen = _watch(tick=2, occurrences=(), bodies=("body-bob",))
    prior = TheoryOfMind(
        owner_id=_OWNER,
        hypotheses=(
            MindHypothesis(
                owner_id=_OWNER,
                subject_id=EntityId("body-bob"),
                aspect=MindAspect.NEED,
                atoms=(MindAtom(slot=MindSlot.NEED_KIND, value="hunger"),),
                support=4.0,
                counter=0.0,
                evidence_ids=("prov-1",),
                counter_evidence_ids=(),
                channel=MindEvidenceChannel.OBSERVED_BEHAVIOR,
            ),
        ),
    )
    updated = update_epistemic_state(
        prior,
        seen,
        (_belief(support_mass=1.0, contradiction_mass=0.0, confidence=0.8),),
        default_epistemic_policy(),
    )
    assert updated.hypotheses == prior.hypotheses
    row = _level1(updated, "belief:belief-1")
    assert row.confidence == pytest.approx(0.8)
    assert row.attitude is EpistemicAttitude.KNOWS
    assert row.source is EpistemicSource.SEMANTIC_BELIEF
    assert row.witness_ids == ()
    text = caplog.text
    assert "epistemic_updated" in text
    assert "input_belief_count=1" in text
    assert "epistemic_row_kept" in text
    assert "attitude=knows" in text
    assert "source=semantic_belief" in text
    assert "hidden-speech" not in text


def test_inactive_beliefs_and_depth_zero_do_not_rewrite_the_ledger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=_LOG)
    seen = _watch(tick=2)
    fresh = update_epistemic_state(
        TheoryOfMind(owner_id=_OWNER),
        seen,
        (
            _belief(state=BeliefActivationState.CANDIDATE),
            _belief(belief_id="belief-2", state=BeliefActivationState.RETIRED),
        ),
        default_epistemic_policy(),
    )
    assert fresh.attributions == ()
    assert "reason_code=belief_inactive" in caplog.text
    existing = TheoryOfMind(owner_id=_OWNER, attributions=(_row(),))
    kept = update_epistemic_state(
        existing,
        seen,
        (_belief(),),
        EpistemicPolicy(max_depth=0),
    )
    assert kept is existing


def test_updater_rejects_foreign_types_and_owner_mismatch(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger=_LOG)
    model = TheoryOfMind(owner_id=_OWNER)
    policy = default_epistemic_policy()
    seen = _watch(tick=2)
    with pytest.raises(TypeError):
        update_epistemic_state(model, object.__new__(WorldState), (), policy)
    with pytest.raises(TypeError):
        update_epistemic_state(model, object.__new__(PhysicalRules), (), policy)
    with pytest.raises(TypeError):
        update_epistemic_state(model, object.__new__(AgentBody), (), policy)
    with pytest.raises(TypeError):
        update_epistemic_state(model, seen, object(), policy)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="owner_mismatch"):
        update_epistemic_state(
            model,
            seen,
            (_belief(owner=AgentId("agent-bob")),),
            policy,
        )
    assert "reason_code=owner_mismatch" in caplog.text


def test_witness_union_depth_cap_and_testimony(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOG)
    policy = default_epistemic_policy()
    first = update_epistemic_state(
        TheoryOfMind(owner_id=_OWNER),
        _watch(
            tick=2,
            occurrences=(
                _occurrence(
                    kind="eat", tick=2, actor="body-carol", event="evt-eat"
                ),
            ),
            bodies=("body-carol",),
        ),
        (_belief(),),
        policy,
    )
    belief = _level1(first, "belief:belief-1")
    fact = _level1(first, "fact:eat:none")
    assert belief.witness_ids == ("body-carol",)
    assert fact.source is EpistemicSource.OBSERVED_BEHAVIOR
    assert fact.confidence == pytest.approx(0.8)
    assert any(
        item.nesting_level == 2
        and item.modeled_agents == ("body-carol",)
        and item.attitude is EpistemicAttitude.KNOWS
        and item.proposition_ref == "belief:belief-1"
        for item in first.attributions
    )
    assert all(item.nesting_level <= 2 for item in first.attributions)
    later = update_epistemic_state(
        first,
        _watch(tick=3, occurrences=(), bodies=("body-carol", "body-bob")),
        (_belief(),),
        policy,
    )
    refreshed = _level1(later, "belief:belief-1")
    assert refreshed.witness_ids == ("body-carol",)
    assert any(
        item.nesting_level == 2
        and item.modeled_agents == ("body-bob",)
        and item.attitude is EpistemicAttitude.DOES_NOT_KNOW
        for item in later.attributions
    )
    deep = _row(
        nesting_level=3,
        modeled_agents=("body-bob", "body-carol"),
        proposition_ref="fact:move:none",
    )
    capped = update_epistemic_state(
        TheoryOfMind(owner_id=_OWNER, attributions=(deep,)),
        _watch(tick=4, occurrences=(), bodies=("body-bob",)),
        (),
        policy,
    )
    assert all(item.nesting_level <= 2 for item in capped.attributions)
    assert "reason_code=epistemic_depth_exceeded" in caplog.text
    testified = update_epistemic_state(
        TheoryOfMind(owner_id=_OWNER),
        _watch(
            tick=5,
            communications=(_speech(predicate="knows", obj="food"),),
            bodies=("body-bob",),
        ),
        (),
        policy,
    )
    assert any(
        item.nesting_level == 2
        and item.source is EpistemicSource.COMMUNICATION
        and item.attitude is EpistemicAttitude.KNOWS
        and item.proposition_ref == "food"
        for item in testified.attributions
    )
    multi = update_epistemic_state(
        TheoryOfMind(owner_id=_OWNER),
        _watch(
            tick=6,
            communications=(
                _speech(predicate="knows", obj="food", hop=2, event="evt-hop"),
            ),
            bodies=("body-bob",),
        ),
        (),
        policy,
    )
    assert multi.attributions == ()
    assert "reason_code=multi_hop_deferred" in caplog.text
    wants = update_epistemic_state(
        TheoryOfMind(owner_id=_OWNER),
        _watch(
            tick=7,
            communications=(_speech(predicate="wants", obj="food", event="evt-want"),),
            bodies=("body-bob",),
        ),
        (),
        policy,
    )
    assert wants.attributions == ()
    preserved = update_theory_of_mind(
        first,
        (),
        default_theory_of_mind_policy(),
    )
    assert preserved.attributions == first.attributions
    derived = derive_future_actions(
        first, default_theory_of_mind_policy(), tick=2
    )
    assert derived.attributions == first.attributions
    source = inspect_source()
    for banned in (
        "import simulation",
        "import analysis",
        "import llm",
        "world.events",
        "world._state",
    ):
        assert banned not in source


def inspect_source() -> str:
    from pathlib import Path

    return Path("src/agents/cognition/epistemic.py").read_text(encoding="utf-8")
