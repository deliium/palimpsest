"""Owner commitment ledgers start empty and checkpoint only on codec v14."""

from __future__ import annotations

import pytest

from agents.cognition.structured_commitments import (
    MAX_OPEN_INTERPRETATIONS_LIMIT,
    CommitmentInterpretation,
    empty_structured_commitments,
    replace_interpretation,
)
from agents.models import AgentId
from simulation.new_agent_initialization import (
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
)
from simulation.serialization import (
    DomainSerializationError,
    decode_structured_commitments_checkpoint,
    structured_commitments_checkpoint_payload,
)


def _row(local_id: int, item_kind: str) -> CommitmentInterpretation:
    return CommitmentInterpretation(
        local_id,
        ("evt-1",),
        ("body-a", "body-b"),
        "body-b",
        "body-a",
        "future_exchange",
        "counterparty",
        item_kind,
        "none",
        1,
        "food",
        "by_tick",
        4,
        1,
        "open",
        False,
        0,
        0.5,
    )


def test_newborn_ledger_is_empty_and_cap_is_the_spec_limit() -> None:
    owner = AgentId("child-1")
    ledger = empty_structured_commitments(owner, max_open_interpretations=4)
    assert ledger.interpretations == ()
    assert ledger.max_open_interpretations == 4
    assert MAX_OPEN_INTERPRETATIONS_LIMIT == 16
    assert_blank_slate_subjective_state(owner, BlankSlateStoreCounts())
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        assert_blank_slate_subjective_state(
            owner, BlankSlateStoreCounts(structured_commitments=1)
        )


def test_v13_has_no_field_and_v14_keeps_divergent_terms() -> None:
    first = replace_interpretation(
        empty_structured_commitments(AgentId("owner-a"), max_open_interpretations=8),
        _row(1, "material"),
    )
    second = replace_interpretation(
        empty_structured_commitments(AgentId("owner-b"), max_open_interpretations=8),
        _row(1, "tool"),
    )
    ledgers = {"owner-a": first, "owner-b": second}
    older = structured_commitments_checkpoint_payload(ledgers, codec="v13")
    assert "structured_commitments" not in older
    assert decode_structured_commitments_checkpoint(older, codec="v13") == {}
    with pytest.raises(
        DomainSerializationError, match="structured_commitments_requires_codec_v14"
    ):
        decode_structured_commitments_checkpoint(
            {"structured_commitments": {}}, codec="v13"
        )
    current = structured_commitments_checkpoint_payload(ledgers, codec="v14")
    restored = decode_structured_commitments_checkpoint(current, codec="v14")
    assert restored["owner-a"].interpretations[0].item_kind == "material"
    assert restored["owner-b"].interpretations[0].item_kind == "tool"
    assert restored["owner-a"].interpretations[0].source_event_ids == ("evt-1",)
