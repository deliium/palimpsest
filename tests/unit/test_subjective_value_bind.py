"""Valuations stay on the owner and survive a v15 checkpoint."""

from __future__ import annotations

from dataclasses import replace

from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopResult,
    ComponentBoundaryRecord,
    ComponentKind,
    ComponentStatus,
    DecisionMetadata,
    IntentionCode,
    InternalAgentState,
    MotivationCode,
    SelectedIntention,
)
from agents.cognition.subjective_value import (
    SubjectiveValuationLedger,
    appraise_reservation,
    refresh_owner_ledgers,
    remember_judgment,
)
from agents.models import AgentId
from simulation.serialization import (
    decode_subjective_valuation_checkpoint,
    subjective_valuation_checkpoint_payload,
)
from world.actions import Wait
from world.identifiers import EntityId
from world.values import ItemKind


def test_refresh_keeps_alice_at_eight_and_bob_at_three() -> None:
    here = EntityId("camp")
    alice, _alice_scarcity = refresh_owner_ledgers(
        owner_id=AgentId("alice"),
        valuations=None,
        scarcity=None,
        tick=2,
        hunger=0,
        thirst=0,
        health=100,
        body_present=True,
        held_counts={ItemKind.TOOL: 1},
        ground_kinds=(),
        other_held_kinds=(),
        location_id=here,
        plan_kinds=frozenset({ItemKind.TOOL}),
        risk_active=False,
        future_kinds=frozenset(),
    )
    bob, _bob_scarcity = refresh_owner_ledgers(
        owner_id=AgentId("bob"),
        valuations=None,
        scarcity=None,
        tick=2,
        hunger=0,
        thirst=0,
        health=100,
        body_present=True,
        held_counts={},
        ground_kinds=(),
        other_held_kinds=(ItemKind.TOOL,),
        location_id=here,
        plan_kinds=frozenset(),
        risk_active=False,
        future_kinds=frozenset(),
    )
    assert _reservation(alice, ItemKind.TOOL) == 8
    assert _reservation(bob, ItemKind.TOOL) == 3


def test_checkpoint_restores_both_reservations() -> None:
    alice, alice_scarcity = refresh_owner_ledgers(
        owner_id=AgentId("alice"),
        valuations=None,
        scarcity=None,
        tick=1,
        hunger=0,
        thirst=0,
        health=100,
        body_present=True,
        held_counts={ItemKind.TOOL: 1},
        ground_kinds=(),
        other_held_kinds=(),
        location_id=EntityId("camp"),
        plan_kinds=frozenset({ItemKind.TOOL}),
        risk_active=False,
        future_kinds=frozenset(),
    )
    bob, bob_scarcity = refresh_owner_ledgers(
        owner_id=AgentId("bob"),
        valuations=None,
        scarcity=None,
        tick=1,
        hunger=0,
        thirst=0,
        health=100,
        body_present=True,
        held_counts={},
        ground_kinds=(),
        other_held_kinds=(ItemKind.TOOL,),
        location_id=EntityId("camp"),
        plan_kinds=frozenset(),
        risk_active=False,
        future_kinds=frozenset(),
    )
    payload = subjective_valuation_checkpoint_payload(
        {"alice": alice, "bob": bob},
        {"alice": alice_scarcity, "bob": bob_scarcity},
        codec="v15",
    )
    restored = decode_subjective_valuation_checkpoint(payload, codec="v15")
    assert _reservation(restored["subjective_valuations"]["alice"], ItemKind.TOOL) == 8
    assert _reservation(restored["subjective_valuations"]["bob"], ItemKind.TOOL) == 3


def test_judgment_cap_drops_the_oldest_and_keeps_kind_rows() -> None:
    owner = AgentId("alice")
    ledger = SubjectiveValuationLedger(owner, max_judgments=1)
    kind = appraise_reservation(item_kind=ItemKind.TOOL, others_visible_count=0)
    ledger = remember_judgment(
        ledger, replace(kind, counterparty_id=EntityId("bob"))
    )
    ledger = remember_judgment(
        ledger, replace(kind, counterparty_id=EntityId("cara"), tick=4)
    )
    assert len(ledger.judgment_rows) == 1
    assert ledger.judgment_rows[0].counterparty_id == EntityId("cara")
    assert ledger.kind_rows == ()


def test_child_does_not_inherit_a_parent_ledger() -> None:
    parent, parent_scarcity = refresh_owner_ledgers(
        owner_id=AgentId("alice"),
        valuations=None,
        scarcity=None,
        tick=1,
        hunger=0,
        thirst=0,
        health=100,
        body_present=True,
        held_counts={ItemKind.TOOL: 1},
        ground_kinds=(),
        other_held_kinds=(),
        location_id=EntityId("camp"),
        plan_kinds=frozenset({ItemKind.TOOL}),
        risk_active=False,
        future_kinds=frozenset(),
        judgment_kind=ItemKind.TOOL,
        counterparty_id=EntityId("bob"),
    )
    child, child_scarcity = refresh_owner_ledgers(
        owner_id=AgentId("child"),
        valuations=parent,
        scarcity=parent_scarcity,
        tick=1,
        hunger=0,
        thirst=0,
        health=100,
        body_present=False,
        held_counts={},
        ground_kinds=(),
        other_held_kinds=(),
        location_id=None,
        plan_kinds=frozenset(),
        risk_active=False,
        future_kinds=frozenset(),
    )
    assert parent.judgment_rows
    assert child.owner_id == AgentId("child")
    assert child.judgment_rows == ()
    assert child_scarcity.owner_id == AgentId("child")
    assert child_scarcity.rows == ()


def test_channel_off_writes_neither_store() -> None:
    loop = CognitiveLoop.__new__(CognitiveLoop)
    loop._subjective_valuation_active = False
    assert loop._prepare_subjective_valuations(
        None, world_model=None, emotional_evaluation=None
    ) == (None, None, None)


def test_loop_result_exposes_both_ledgers() -> None:
    agent = AgentId("alice")
    valuations, scarcity = refresh_owner_ledgers(
        owner_id=agent,
        valuations=None,
        scarcity=None,
        tick=1,
        hunger=0,
        thirst=0,
        health=100,
        body_present=True,
        held_counts={ItemKind.TOOL: 1},
        ground_kinds=(),
        other_held_kinds=(),
        location_id=EntityId("camp"),
        plan_kinds=frozenset({ItemKind.TOOL}),
        risk_active=False,
        future_kinds=frozenset(),
    )
    plan = ActionPlan(owner_id=agent, command=Wait(), confidence=1.0)
    record = ComponentBoundaryRecord(
        invocation_id="inv-1",
        component_kind=ComponentKind.PLANNING,
        component_version="v1",
        ordinal=7,
        status=ComponentStatus.COMPLETED,
        confidence=1.0,
        input_artifact=SelectedIntention(
            owner_id=agent,
            intention=IntentionCode.WAIT,
            source_motive=MotivationCode.WAIT,
            confidence=1.0,
        ),
        output_artifact=plan,
        decision_metadata=DecisionMetadata(
            selection_codes=("wait",), candidate_count=1
        ),
    )
    result = CognitiveLoopResult(
        invocation_id="inv-1",
        agent_id=agent,
        command=Wait(),
        boundary_records=(record,),
        memory_update_intents=(),
        final_confidence=1.0,
        internal_state=InternalAgentState(owner_id=agent),
        subjective_valuations=valuations,
        scarcity_beliefs=scarcity,
    )
    assert _reservation(result.subjective_valuations, ItemKind.TOOL) == 8
    assert result.scarcity_beliefs.owner_id == agent


def _reservation(ledger: SubjectiveValuationLedger, kind: ItemKind) -> int:
    return next(row.reservation for row in ledger.kind_rows if row.item_kind is kind)
