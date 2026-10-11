"""Private valuation and scarcity ledgers stay off older checkpoints."""

from __future__ import annotations

import pytest

from agents.cognition.scarcity_beliefs import (
    ScarcityBelief,
    empty_scarcity_beliefs,
    scarcity_row,
    store_scarcity_belief,
)
from agents.cognition.structured_commitments import empty_structured_commitments
from agents.cognition.subjective_value import (
    ValuationComponent,
    ValuationRow,
    empty_subjective_valuations,
    store_kind_valuation,
)
from agents.models import AgentId
from simulation.new_agent_initialization import (
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
)
from simulation.serialization import (
    DomainSerializationError,
    decode_structured_commitments_checkpoint,
    decode_subjective_valuation_checkpoint,
    structured_commitments_checkpoint_payload,
    subjective_valuation_checkpoint_payload,
)
from world.identifiers import EntityId
from world.values import ItemKind


def _tool_row(reservation: int) -> ValuationRow:
    return ValuationRow(
        ItemKind.TOOL,
        ItemKind.FOOD,
        reservation,
        (
            ValuationComponent("scarcity", 4 if reservation == 8 else 3),
            ValuationComponent("plan", 4 if reservation == 8 else 0),
        ),
        1,
    )


def test_newborn_ledgers_are_empty() -> None:
    owner = AgentId("child-1")
    valuations = empty_subjective_valuations(owner)
    scarcity = empty_scarcity_beliefs(owner)
    assert valuations.kind_rows == ()
    assert valuations.judgment_rows == ()
    assert scarcity.rows == ()
    assert scarcity_row(scarcity, ItemKind.TOOL) is None
    assert_blank_slate_subjective_state(owner, BlankSlateStoreCounts())
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        assert_blank_slate_subjective_state(
            owner, BlankSlateStoreCounts(subjective_valuations=1)
        )


def test_missing_scarcity_row_is_not_a_zero_count() -> None:
    owner = AgentId("alice")
    empty = empty_scarcity_beliefs(owner)
    zero = store_scarcity_belief(
        empty,
        ScarcityBelief(ItemKind.TOOL, 0, EntityId("loc-1"), 1),
    )
    assert scarcity_row(empty, ItemKind.TOOL) is None
    stored = scarcity_row(zero, ItemKind.TOOL)
    assert stored is not None
    assert stored.believed_local_count == 0


def test_v14_omits_ledgers_and_keeps_commitments() -> None:
    owner = AgentId("alice")
    valuations = {
        owner.value: store_kind_valuation(
            empty_subjective_valuations(owner), _tool_row(8)
        )
    }
    scarcity = {owner.value: empty_scarcity_beliefs(owner)}
    commitments = {owner.value: empty_structured_commitments(owner)}
    older = subjective_valuation_checkpoint_payload(
        valuations, scarcity, codec="v14"
    )
    commitment_payload = structured_commitments_checkpoint_payload(
        commitments, codec="v14"
    )
    assert "subjective_valuations" not in older
    assert "scarcity_beliefs" not in older
    assert "structured_commitments" in commitment_payload
    merged = {**older, **commitment_payload}
    assert decode_structured_commitments_checkpoint(merged, codec="v14")
    with pytest.raises(
        DomainSerializationError, match="subjective_valuation_requires_codec_v15"
    ):
        decode_subjective_valuation_checkpoint(
            {"subjective_valuations": {}, "scarcity_beliefs": {}}, codec="v14"
        )


def test_v15_round_trips_two_owners_tool_reservations() -> None:
    alice = AgentId("alice")
    bob = AgentId("bob")
    valuations = {
        alice.value: store_kind_valuation(
            empty_subjective_valuations(alice), _tool_row(8)
        ),
        bob.value: store_kind_valuation(empty_subjective_valuations(bob), _tool_row(3)),
    }
    scarcity = {
        alice.value: store_scarcity_belief(
            empty_scarcity_beliefs(alice),
            ScarcityBelief(ItemKind.TOOL, 0, EntityId("loc-1"), 1),
        ),
        bob.value: store_scarcity_belief(
            empty_scarcity_beliefs(bob),
            ScarcityBelief(ItemKind.TOOL, 1, EntityId("loc-1"), 1),
        ),
    }
    payload = subjective_valuation_checkpoint_payload(
        valuations, scarcity, codec="v15"
    )
    assert "price" not in str(payload)
    restored = decode_subjective_valuation_checkpoint(payload, codec="v15")
    assert restored["subjective_valuations"][alice.value].kind_rows[0].reservation == 8
    assert restored["subjective_valuations"][bob.value].kind_rows[0].reservation == 3
    assert restored["scarcity_beliefs"] == scarcity
