"""Status changes request social signals and do not collect a debt."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from agents.cognition.configuration import build_cognitive_loop
from agents.cognition.models import MemoryUpdateKind
from agents.cognition.reputation import (
    _OBSERVATION_DELTAS,
    ReputationLedger,
    note_remembered_reliability,
)
from agents.cognition.social_norms import (
    NormBelief,
    NormContext,
    NormExpectation,
    NormLedger,
    NormPattern,
    NormStatus,
    empty_norm_ledger,
    norm_belief_id,
    note_reciprocal_commitment_evidence,
)
from agents.cognition.structured_commitments import (
    CommitmentInterpretation,
    apply_commitment_sanction,
    commitment_social_requests,
    empty_structured_commitments,
)
from agents.models import AgentId
from social.relationships import (
    RelationshipDimension,
    RelationshipFormationPolicy,
    RelationshipInteractionSignal,
    RelationshipSignalKind,
    merge_relationship_revision,
)
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world._operations import OperationAccepted, validate_action_request
from world._rules import apply_operation
from world._state import WorldState
from world.actions import ActionRequest, Give, require_agent_command
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision
from world.values import ItemKind


def _row(status: str, debtor: str, creditor: str) -> CommitmentInterpretation:
    return CommitmentInterpretation(
        1,
        ("evt-1",),
        ("body-a", "body-b"),
        debtor,
        creditor,
        "future_exchange",
        "counterparty",
        "material",
        "none",
        1,
        "food",
        "by_tick",
        4,
        1,
        status,
        False,
        0,
        0.5,
    )


def _ledger(owner: str, row: CommitmentInterpretation):
    base = empty_structured_commitments(AgentId(owner))
    return replace(base, interpretations=(row,))


def _requests(owner_entity: str, before_status: str, after_status: str, **flags):
    debtor, creditor = ("body-a", "body-b")
    if owner_entity == "body-b":
        debtor, creditor = ("body-a", "body-b")
    before = _ledger("owner", _row(before_status, debtor, creditor))
    after = _ledger("owner", _row(after_status, debtor, creditor))
    return commitment_social_requests(
        owner_entity,
        before,
        after,
        reputation_on=flags.get("reputation_on", False),
        norms_on=flags.get("norms_on", False),
    )


def _debt(source: str, target: str, kind: RelationshipSignalKind) -> float:
    history, _, _, _ = merge_relationship_revision(
        source_id=AgentId(source),
        target_id=AgentId(target),
        signals=(
            RelationshipInteractionSignal(
                counterpart_id=AgentId(target),
                kind=kind,
                strength=1.0,
                memory_ref="commitment:1",
                lineage_root_ref="commitment:1",
                source_tick=2,
            ),
        ),
        prior=None,
        logical_tick=2,
        operation_id="op-1",
        policy=RelationshipFormationPolicy(policy_id="rel-test", version="1"),
    )
    for dimension in history.profile.dimensions:
        if dimension.dimension is RelationshipDimension.DEBT:
            return dimension.value
    return 0.0


def test_creditor_violation_requests_contradiction_and_criticism() -> None:
    requests = _requests("body-b", "open", "violated")
    signals = [item.signal for item in requests if item.channel == "relationship"]
    sanctions = [item.sanction for item in requests if item.channel == "sanction"]
    assert signals == ["contradiction_received"]
    assert sanctions == ["criticism"]
    assert "retaliation_considered" not in sanctions
    marked = apply_commitment_sanction(
        _ledger("owner", _row("violated", "body-a", "body-b")), 1, "criticism"
    )
    assert marked.interpretations[0].sanction == "criticism"


def test_debtor_open_raises_debt_and_creditor_open_does_not() -> None:
    debtor = _requests("body-a", "proposed", "open")
    assert [item.signal for item in debtor if item.channel == "relationship"] == [
        "resource_received"
    ]
    assert _debt("owner-a", "owner-b", RelationshipSignalKind.RESOURCE_RECEIVED) > 0
    creditor = _requests("body-b", "proposed", "open")
    assert [item for item in creditor if item.channel == "relationship"] == []


def test_reputation_and_norms_skip_when_disabled_or_unseeded() -> None:
    assert "commitment_declared" not in _OBSERVATION_DELTAS
    quiet = _requests("body-a", "open", "fulfilled")
    assert [item for item in quiet if item.channel == "reputation"] == []
    owner = AgentId("owner-a")
    other = AgentId("owner-b")
    noted = note_remembered_reliability(
        ReputationLedger(owner),
        target_id=other,
        delta=0.10,
        lineage="commitment:1:fulfilled:3",
        tick=3,
    )
    assert noted.profile_for(other).reliability.value == 0.10  # type: ignore[union-attr]
    full = noted
    for index in range(63):
        full = note_remembered_reliability(
            full,
            target_id=other,
            delta=-0.10 if index % 2 else 0.10,
            lineage=f"commitment:1:violated:{index}",
            tick=4 + index,
        )
    capped = note_remembered_reliability(
        full,
        target_id=other,
        delta=0.10,
        lineage="commitment:1:fulfilled:99",
        tick=80,
    )
    assert len(capped.profile_for(other).evidence) == len(  # type: ignore[union-attr]
        full.profile_for(other).evidence  # type: ignore[union-attr]
    )
    untouched = note_reciprocal_commitment_evidence(
        empty_norm_ledger(owner),
        owner,
        other,
        lineage="commitment:1:open:2",
        tick=2,
    )
    assert untouched.beliefs == ()
    belief = NormBelief(
        belief_id=norm_belief_id(
            owner, NormPattern.RECIPROCAL_EXCHANGE, (owner, other)
        ),
        owner_id=owner,
        pattern=NormPattern.RECIPROCAL_EXCHANGE,
        expectation=NormExpectation.GIVE_AGAIN,
        context=NormContext(pattern=NormPattern.RECIPROCAL_EXCHANGE),
        status=NormStatus.CANDIDATE,
        confidence=0.2,
        counterpart_ids=(owner, other),
    )
    seeded = NormLedger(owner, beliefs=(belief,))
    counted = note_reciprocal_commitment_evidence(
        seeded, owner, other, lineage="commitment:1:open:2", tick=2
    )
    assert len(counted.beliefs[0].evidence) == 1


def test_the_live_loop_stores_a_sanction_and_queues_a_relationship() -> None:
    before = _ledger("owner-a", _row("open", "body-b", "body-a"))
    after = _ledger("owner-a", _row("violated", "body-b", "body-a"))
    loop = build_cognitive_loop()
    loop._structured_commitments_active = True
    observation = SimpleNamespace(observer_id=EntityId("body-a"), tick=3)
    loop_input = SimpleNamespace(
        observation=observation,
        snapshot=SimpleNamespace(structured_commitments=before),
        agent_id=AgentId("owner-a"),
    )
    folded, _reputation, _norms = loop._fold_commitment_consequences(
        loop_input, after, None, None
    )
    assert folded.interpretations[0].sanction == "criticism"
    proposal = SimpleNamespace(
        structured_commitments=after,
        loop_input=loop_input,
        agent_id=AgentId("owner-a"),
    )
    updates = loop._append_commitment_relationships(proposal, ())
    assert len(updates) == 1
    assert updates[0].kind is MemoryUpdateKind.REVISE_RELATIONSHIP
    assert updates[0].relationship_revision.signals[0].kind is (
        RelationshipSignalKind.CONTRADICTION_RECEIVED
    )


def test_a_later_give_is_still_admitted() -> None:
    food = make_item("food-1", location_id=None, holder_id="body-a", kind=ItemKind.FOOD)
    giver = alive_body("body-a", inventory=(food.entity_id,))
    other = alive_body("body-b")
    state = WorldState(
        WorldRevision(1),
        locations=(make_location(),),
        items=(food,),
        bodies=(giver, other),
        weather=(make_weather(),),
    )
    outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=state,
        request=ActionRequest(
            request_id=RequestId("r-give"),
            proposal_id=ProposalId("p-give"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-a"),
            revision=WorldRevision(1),
            command=require_agent_command(Give(EntityId("body-b"), food.entity_id)),
        ),
    )
    assert type(outcome) is OperationAccepted
    applied = apply_operation(state, outcome.operation, tick=1)
    assert applied.next_state.items[food.entity_id].holder_id == EntityId("body-b")
