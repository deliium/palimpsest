"""Detached evidence adapters: lane mapping, validation, and determinism."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from analysis.macro_society_contract import MacroSocietyError, MacroSocietyLane
from analysis.macro_society_evidence import (
    MacroSocietyEdge,
    MacroSocietyToken,
    MacroSocietyWindowEvidence,
    edges_from_communication,
    edges_from_exchanges,
    edges_from_interaction,
    edges_from_journeys,
    tokens_from_collective_decisions,
    tokens_from_culture,
    tokens_from_institutions,
    tokens_from_residence,
    tokens_from_self_identification,
    tokens_from_territory,
)

PERSONS = ("person-1", "person-2", "person-3", "person-4")


@dataclass(frozen=True)
class Speech:
    speaker_id: str
    listener_id: str
    tick: int
    action_kind: str = "talk"
    utterance: str = "private text"


@dataclass(frozen=True)
class Action:
    actor_id: str
    target_id: str
    tick: int


@dataclass(frozen=True)
class Journey:
    person_id: str
    origin_region_id: str
    destination_region_id: str
    tick: int


@dataclass(frozen=True)
class Move:
    from_owner_id: str
    to_owner_id: str
    tick: int


def test_communication_adapter_maps_speech_and_ignores_other_kinds() -> None:
    rows = [
        Speech("person-1", "person-2", 3),
        Speech("person-2", "person-3", 4, action_kind="wait"),
    ]
    edges = edges_from_communication(rows)
    assert len(edges) == 1
    assert edges[0].lane is MacroSocietyLane.COMMUNICATION
    assert (edges[0].source_person_id, edges[0].target_person_id) == (
        "person-1",
        "person-2",
    )
    assert "private text" not in repr(edges)


def test_interaction_and_exchange_adapters_tag_their_lanes() -> None:
    interaction = edges_from_interaction([Action("person-1", "person-2", 1)])
    exchange = edges_from_exchanges([Move("person-1", "person-3", 2)])
    assert interaction[0].lane is MacroSocietyLane.INTERACTION
    assert exchange[0].lane is MacroSocietyLane.EXCHANGE
    assert exchange[0].target_person_id == "person-3"


def test_journey_adapter_emits_pairs_only_for_shared_travel() -> None:
    rows = [
        Journey("person-1", "region-a", "region-b", 5),
        Journey("person-2", "region-a", "region-b", 5),
        Journey("person-3", "region-a", "region-c", 5),
    ]
    edges = edges_from_journeys(rows)
    assert len(edges) == 1
    assert (edges[0].source_person_id, edges[0].target_person_id) == (
        "person-1",
        "person-2",
    )
    assert edges[0].lane is MacroSocietyLane.MIGRATION


def test_token_adapters_preserve_owner_local_tokens() -> None:
    institution = tokens_from_institutions(
        [{"owner_id": "person-1", "local_pattern_id": "pattern-1"}]
    )
    culture = tokens_from_culture(
        [{"carriers": {"trait-1": ["person-1", "person-2"]}}]
    )
    territory = tokens_from_territory(
        [{"owner_id": "person-1", "target_kind": "region", "target_entity_id": "r-1"}]
    )
    identity = tokens_from_self_identification(
        [{"owner_id": "person-1", "group_id": "group-1"}]
    )
    decisions = tokens_from_collective_decisions(
        [{"owner_id": "person-1", "proposal_ref": "proposal-1"}]
    )
    residence = tokens_from_residence([{"person_id": "person-1", "region_id": "r-1"}])

    assert institution[0].lane is MacroSocietyLane.INSTITUTION
    assert len(culture) == 2
    assert territory[0].token_id == "r-1"
    assert identity[0].token_id == "group-1"
    assert decisions[0].token_id == "proposal-1"
    assert residence[0].token_id == "region:r-1"


def test_token_adapters_require_a_token() -> None:
    with pytest.raises(MacroSocietyError, match="macro_society_invalid_evidence_row"):
        tokens_from_collective_decisions([{"owner_id": "person-1"}])


def test_adapters_ignore_non_territory_claim_kinds() -> None:
    rows = [{"owner_id": "person-1", "target_kind": "agent", "target_entity_id": "p"}]
    assert tokens_from_territory(rows) == ()


def test_missing_required_field_fails_closed() -> None:
    with pytest.raises(MacroSocietyError, match="macro_society_invalid_evidence_row"):
        edges_from_interaction([{"actor_id": "person-1"}])


def test_self_edges_are_rejected() -> None:
    with pytest.raises(MacroSocietyError, match="macro_society_self_edge_rejected"):
        MacroSocietyEdge(MacroSocietyLane.INTERACTION, "person-1", "person-1", 0)


@pytest.mark.parametrize("weight", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_weights_are_rejected(weight: float) -> None:
    with pytest.raises(MacroSocietyError, match="macro_society_invalid_weight"):
        MacroSocietyEdge(MacroSocietyLane.EXCHANGE, "person-1", "person-2", 0, weight)


def test_edge_lane_must_be_an_edge_lane() -> None:
    with pytest.raises(MacroSocietyError, match="macro_society_unknown_lane"):
        MacroSocietyEdge(MacroSocietyLane.CULTURE, "person-1", "person-2", 0)
    with pytest.raises(MacroSocietyError, match="macro_society_unknown_lane"):
        MacroSocietyToken(MacroSocietyLane.INTERACTION, "person-1", "t-1")


def test_window_sorts_and_rejects_unknown_persons() -> None:
    window = MacroSocietyWindowEvidence(
        window_index=0,
        tick_start=2,
        tick_end=4,
        person_ids=("person-2", "person-1"),
        edges=(MacroSocietyEdge(MacroSocietyLane.EXCHANGE, "person-2", "person-1", 3),),
        tokens=(MacroSocietyToken(MacroSocietyLane.CULTURE, "person-2", "trait-1"),),
    )
    assert window.person_ids == ("person-1", "person-2")
    assert window.lane_presence == tuple(
        sorted(
            (
                lane.value,
                lane in {MacroSocietyLane.EXCHANGE, MacroSocietyLane.CULTURE},
            )
            for lane in MacroSocietyLane
        )
    )

    with pytest.raises(MacroSocietyError, match="macro_society_unknown_person"):
        MacroSocietyWindowEvidence(
            window_index=0,
            tick_start=0,
            tick_end=1,
            person_ids=("person-1",),
            edges=(
                MacroSocietyEdge(MacroSocietyLane.EXCHANGE, "person-1", "person-2", 0),
            ),
        )


def test_window_rejects_empty_or_inverted_inputs() -> None:
    with pytest.raises(MacroSocietyError, match="macro_society_empty_window"):
        MacroSocietyWindowEvidence(0, 0, 0, ())
    with pytest.raises(MacroSocietyError, match="macro_society_invalid_window"):
        MacroSocietyWindowEvidence(0, 5, 4, ("person-1",))
    with pytest.raises(MacroSocietyError, match="macro_society_duplicate_member"):
        MacroSocietyWindowEvidence(0, 0, 1, ("person-1", "person-1"))


def test_window_rejects_oversized_edge_sets_before_graph_work() -> None:
    from analysis.macro_society_contract import MAX_WINDOW_EDGES

    edges = tuple(
        MacroSocietyEdge(MacroSocietyLane.EXCHANGE, "person-1", "person-2", index)
        for index in range(MAX_WINDOW_EDGES + 1)
    )
    with pytest.raises(MacroSocietyError, match="macro_society_window_too_large"):
        MacroSocietyWindowEvidence(0, 0, 1, PERSONS, edges)


def test_adapters_are_order_independent() -> None:
    rows = [
        Speech("person-1", "person-2", 3),
        Speech("person-2", "person-3", 4),
        Speech("person-3", "person-4", 5),
    ]
    assert edges_from_communication(rows) == edges_from_communication(
        list(reversed(rows))
    )
