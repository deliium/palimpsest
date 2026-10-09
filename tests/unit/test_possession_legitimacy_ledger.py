"""Owner legitimacy ledgers stay empty for newborns and checkpoint on v13."""

from __future__ import annotations

import json

import pytest

from agents.cognition.possession_legitimacy import (
    POSSESSION_SUPPORT_CAP,
    PossessionClaimNote,
    PossessionSanctionNote,
    append_possession_claim,
    append_possession_sanction,
    empty_possession_legitimacy,
    note_doctrine_support,
)
from agents.models import AgentId
from simulation.new_agent_initialization import (
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
)
from simulation.serialization import (
    decode_possession_legitimacy_checkpoint,
    possession_legitimacy_checkpoint_payload,
)
from world.identifiers import EntityId


def test_newborn_ledger_must_be_empty() -> None:
    owner = AgentId("child-1")
    assert empty_possession_legitimacy(owner).supports == ()
    assert_blank_slate_subjective_state(owner, BlankSlateStoreCounts())
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        assert_blank_slate_subjective_state(
            owner, BlankSlateStoreCounts(possession_legitimacy=1)
        )


def test_support_caps_at_thirty_two() -> None:
    ledger = empty_possession_legitimacy(AgentId("owner-1"))
    for _ in range(POSSESSION_SUPPORT_CAP + 3):
        ledger = note_doctrine_support(ledger, "nobody_owns")
    assert ledger.support_count("nobody_owns") == POSSESSION_SUPPORT_CAP
    claimed = append_possession_claim(
        ledger,
        PossessionClaimNote(
            2, EntityId("body-dead"), EntityId("body-live"), "nobody_owns"
        ),
    )
    sanctioned = append_possession_sanction(
        claimed,
        PossessionSanctionNote(
            3, EntityId("body-dead"), EntityId("body-live"), "retaliation_considered"
        ),
    )
    assert sanctioned.sanctions[-1].token == "retaliation_considered"
    assert sanctioned.support_count("nobody_owns") == POSSESSION_SUPPORT_CAP


def test_v12_omits_field_and_v13_round_trips_supports() -> None:
    ledger = note_doctrine_support(
        empty_possession_legitimacy(AgentId("owner-1")), "children_should_inherit"
    )
    ledger = append_possession_claim(
        ledger,
        PossessionClaimNote(
            4,
            EntityId("body-dead"),
            EntityId("owner-body"),
            "children_should_inherit",
            EntityId("item-1"),
        ),
    )
    ledgers = {"owner-1": ledger}
    older = possession_legitimacy_checkpoint_payload(ledgers, codec="v12")
    assert "possession_legitimacy" not in older
    assert decode_possession_legitimacy_checkpoint(older, codec="v12") == {}
    current = possession_legitimacy_checkpoint_payload(ledgers, codec="v13")
    encoded = json.dumps(current)
    assert "blade" not in encoded
    assert "item-1" in encoded
    restored = decode_possession_legitimacy_checkpoint(current, codec="v13")
    assert restored["owner-1"] == ledger
