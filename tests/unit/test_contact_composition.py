"""Detached contact composition and provenance exports."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.regional_population import (
    RegionalEventRow,
    RegionalInitialPlacementRow,
    RegionalLocationRow,
    RegionalPopulationInput,
)
from analysis.society_emergence import CandidateCommunityRow
from experiments.composition import (
    contact_analysis_inputs_from_context,
    naming_borrowing_rows_from_ledgers,
    reputation_evidence_rows_from_ledgers,
)
from world.events import ContactRecorded


def _regional_input() -> RegionalPopulationInput:
    return RegionalPopulationInput(
        run_id="run-contact",
        input_revision="rev",
        region_ids=("north", "south"),
        known_location_ids=("loc-n", "loc-s"),
        location_rows=(
            RegionalLocationRow("loc-n", "north"),
            RegionalLocationRow("loc-s", "south"),
        ),
        initial_placements=(
            RegionalInitialPlacementRow("a-1", "loc-n"),
            RegionalInitialPlacementRow("b-1", "loc-s"),
        ),
        events=(
            RegionalEventRow(
                tick=3,
                sequence=0,
                kind="relocation",
                body_id="a-1",
                origin_location_id="loc-n",
                destination_location_id="loc-s",
                relocation_kind="journey",
            ),
        ),
        residence_min_ticks=1,
        window_end=5,
        complete_through_boundary=5,
    )


def _contact_event() -> object:
    details = ContactRecorded(
        relocation_kind="journey_arrived",
        journey_id="journey-1",
        location_id=__import__("world.identifiers", fromlist=["EntityId"]).EntityId(
            "loc-s"
        ),
        participant_ids=(
            __import__("world.identifiers", fromlist=["EntityId"]).EntityId("a-1"),
        ),
        present_ids=(
            __import__("world.identifiers", fromlist=["EntityId"]).EntityId("b-1"),
        ),
        origin_region_id="north",
        destination_region_id="south",
    )
    return SimpleNamespace(details=details, tick=3, actor_id=None, target_id=None)


def _communities() -> tuple[CandidateCommunityRow, ...]:
    return (
        CandidateCommunityRow.from_members(
            person_ids=("a-1",), lane_coverage=("interaction",)
        ),
        CandidateCommunityRow.from_members(
            person_ids=("b-1",), lane_coverage=("interaction",)
        ),
    )


def test_context_composition_shares_onset_across_families() -> None:
    inputs = contact_analysis_inputs_from_context(
        run_id="run-contact",
        input_revision="rev",
        window_end=5,
        communities=_communities(),
        regional_input=_regional_input(),
        events=(_contact_event(),),
        dimension_sources={
            "vocabulary": (
                SimpleNamespace(person_id="a-1", token="tok-a", tick=1),
                SimpleNamespace(person_id="b-1", token="tok-b", tick=1),
                SimpleNamespace(person_id="a-1", token="tok-x", tick=4),
                SimpleNamespace(person_id="b-1", token="tok-x", tick=4),
            )
        },
    )
    assert len(inputs.contact.pairs) == 1
    assert inputs.contact.pairs[0].onset_tick == 3
    assert inputs.contact.pairs[0].contact_event_count == 1
    assert inputs.cultural_change.coverage_pair_count == 1
    assert inputs.knowledge_transfer.total_transfer_count == 0
    assert inputs.lexical_borrowing.borrowing_event_count == 0
    assert inputs.reputation_transfer.transfer_event_count == 0


def test_naming_ledger_export_is_metadata_only() -> None:
    ledger = SimpleNamespace(
        bindings=(
            SimpleNamespace(
                owner_id=SimpleNamespace(value="b-1"),
                label_token="tok-a",
                referent_kind=SimpleNamespace(value="food"),
                strength=0.8,
                transmission=SimpleNamespace(value="communicated"),
                first_tick=3,
                last_tick=4,
                evidence=(
                    SimpleNamespace(
                        channel=SimpleNamespace(value="communicated"),
                        tick=3,
                        actor_id=SimpleNamespace(value="a-1"),
                    ),
                ),
            ),
        )
    )
    rows = naming_borrowing_rows_from_ledgers({"b": ledger})
    assert len(rows) == 1
    assert rows[0].owner_id == "b-1"
    assert rows[0].actor_id == "a-1"
    assert rows[0].label_token == "tok-a"


def test_reputation_ledger_export_is_metadata_only() -> None:
    ledger = SimpleNamespace(
        profiles=(
            SimpleNamespace(
                evidence=(
                    SimpleNamespace(
                        owner_id=SimpleNamespace(value="b-1"),
                        target_id=SimpleNamespace(value="b-2"),
                        source_id=SimpleNamespace(value="a-1"),
                        dimension=SimpleNamespace(value="reliability"),
                        channel=SimpleNamespace(value="communication"),
                        source_trust_band=SimpleNamespace(value="high"),
                        tick=4,
                    ),
                )
            ),
        )
    )
    rows = reputation_evidence_rows_from_ledgers({"b": ledger})
    assert len(rows) == 1
    assert rows[0].source_id == "a-1"
    assert rows[0].dimension == "reliability"
