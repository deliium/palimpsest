"""V4-10 six lane builders."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from analysis.diplomacy_contract import (
    DIPLOMACY_FORBIDDEN_RESULT_FIELDS,
    InterSocietyLane,
    diplomacy_agent_token,
)
from analysis.diplomacy_lanes import (
    InterSocietyRelationRow,
    relation_rows_from_agent_relationships,
    relation_rows_from_agreements,
    relation_rows_from_conflict,
    relation_rows_from_institutional_interaction,
    relation_rows_from_narratives,
    relation_rows_from_trade,
)

pytestmark = pytest.mark.unit


def test_lane_enum_is_closed_at_six() -> None:
    assert {lane.value for lane in InterSocietyLane} == {
        "agent_relationships",
        "trade",
        "conflict",
        "agreements",
        "narratives",
        "institutional_interaction",
    }


def test_agent_relationship_rows_are_sorted_and_deduped() -> None:
    rows = (
        SimpleNamespace(source_id="a", target_id="b", logical_tick=1),
        SimpleNamespace(source_id="b", target_id="a", logical_tick=1),
        SimpleNamespace(source_id="a", target_id="c", logical_tick=2),
    )
    lane = relation_rows_from_agent_relationships(rows)
    assert lane == tuple(
        sorted(
            lane, key=lambda row: (row.lane, row.left_token, row.right_token, row.tick)
        )
    )
    assert max(row.event_count for row in lane) == 2
    assert all(type(row) is InterSocietyRelationRow for row in lane)


def test_given_transfer_is_never_a_trade_row() -> None:
    events = (
        SimpleNamespace(
            tick=1,
            details=SimpleNamespace(actor_id="a", counterparty_id="b", kind="given"),
        ),
    )
    assert relation_rows_from_trade(events) == ()


def test_exchange_completed_produces_a_trade_row() -> None:
    class ExchangeCompleted:
        def __init__(self) -> None:
            self.actor_id = "a"
            self.counterparty_id = "b"

    events = (SimpleNamespace(tick=2, details=ExchangeCompleted()),)
    rows = relation_rows_from_trade(events)
    assert len(rows) == 1
    assert rows[0].lane == InterSocietyLane.TRADE.value
    assert rows[0].event_count == 1


def test_absent_inputs_yield_empty_tuples() -> None:
    for builder in (
        relation_rows_from_agent_relationships,
        relation_rows_from_trade,
        relation_rows_from_conflict,
        relation_rows_from_agreements,
        relation_rows_from_narratives,
        relation_rows_from_institutional_interaction,
    ):
        assert builder(()) == ()


def test_conflict_rows_use_conflict_actions_only() -> None:
    rows = (
        SimpleNamespace(tick=1, agent_id="a", target_id="b", action_kind="attack"),
        SimpleNamespace(tick=1, agent_id="a", target_id="c", action_kind="wait"),
    )
    lane = relation_rows_from_conflict(rows)
    assert len(lane) == 1
    assert lane[0].lane == InterSocietyLane.CONFLICT.value


def test_agreement_and_narrative_and_institutional_rows() -> None:
    declarations = (
        SimpleNamespace(
            owner_token=diplomacy_agent_token("a"),
            party_token=diplomacy_agent_token("b"),
            act="accept",
            instrument_id="dpi-1",
        ),
    )
    agreements = relation_rows_from_agreements(declarations)
    assert len(agreements) == 1
    assert agreements[0].lane == InterSocietyLane.AGREEMENTS.value

    shared = (
        SimpleNamespace(owner_token=diplomacy_agent_token("a"), variant_token="v1"),
        SimpleNamespace(owner_token=diplomacy_agent_token("b"), variant_token="v1"),
    )
    narratives = relation_rows_from_narratives(shared)
    assert len(narratives) == 1
    assert narratives[0].lane == InterSocietyLane.NARRATIVES.value

    institutional = relation_rows_from_institutional_interaction(
        formal_rule_rows=(
            SimpleNamespace(
                owner_token=diplomacy_agent_token("a"), anchor_ref="rule-1"
            ),
            SimpleNamespace(
                owner_token=diplomacy_agent_token("b"), anchor_ref="rule-1"
            ),
        )
    )
    assert len(institutional) == 1
    assert institutional[0].lane == InterSocietyLane.INSTITUTIONAL_INTERACTION.value


def test_lane_rows_carry_no_score_field() -> None:
    row = InterSocietyRelationRow(
        lane=InterSocietyLane.TRADE.value,
        left_token=diplomacy_agent_token("a"),
        right_token=diplomacy_agent_token("b"),
        tick=1,
        event_count=1,
        denominator=1,
    )
    for name in DIPLOMACY_FORBIDDEN_RESULT_FIELDS:
        assert not hasattr(row, name)
