"""Conservation and dwell-qualified migration over detached regional events."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition.regional_migration import destination_memory_trace
from agents.models import AgentId
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import MetricAvailability
from analysis.regional_destination_beliefs import (
    RegionalDestinationEvidenceRow,
    compute_regional_destination_beliefs,
)
from analysis.regional_migration_metrics import compute_regional_migration_metrics
from analysis.regional_population import (
    RegionalEventRow,
    RegionalInitialPlacementRow,
    RegionalLocationRow,
    RegionalPopulationError,
    RegionalPopulationInput,
    compute_regional_population,
    fold_regional_history,
)
from analysis.specifications import METRIC_FAMILY_COUNT, validate_metric_catalog
from experiments.composition import (
    EvidenceCompositionService,
    regional_context_from_run,
    regional_destination_evidence_rows_from_traces,
    regional_metric_inputs_from_snapshots,
    regional_population_input_from_snapshot,
    regional_population_rows_from_events,
)
from experiments.persistence import PersistedAnalysisSnapshot
from tests.simulation_helpers import alive_body
from world.effects import ActionCause, SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V21,
    Fled,
    JourneyArrived,
    JourneyEnded,
    Moved,
    Transported,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservedRegionalContext,
    ObservedSelf,
    VisibleExit,
)
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)


def _inputs(
    *,
    residence_min_ticks: int = 2,
    window_end: int = 4,
    complete_through_boundary: int | None = None,
    initial: tuple[RegionalInitialPlacementRow, ...] | None = None,
    events: tuple[RegionalEventRow, ...] = (),
) -> RegionalPopulationInput:
    return RegionalPopulationInput(
        run_id="regional-run",
        input_revision="regional-revision",
        region_ids=("a", "b", "c"),
        known_location_ids=("loc-a", "loc-b", "loc-c", "loc-x"),
        location_rows=(
            RegionalLocationRow("loc-a", "a"),
            RegionalLocationRow("loc-b", "b"),
            RegionalLocationRow("loc-c", "c"),
        ),
        initial_placements=(
            (RegionalInitialPlacementRow("body-1", "loc-a"),)
            if initial is None
            else initial
        ),
        events=events,
        residence_min_ticks=residence_min_ticks,
        window_end=window_end,
        complete_through_boundary=complete_through_boundary,
    )


def _move(
    tick: int,
    sequence: int,
    body_id: str,
    origin: str,
    destination: str,
    *,
    kind: str = "move",
) -> RegionalEventRow:
    return RegionalEventRow(
        tick=tick,
        sequence=sequence,
        kind="relocation",
        body_id=body_id,
        origin_location_id=origin,
        destination_location_id=destination,
        relocation_kind=kind,
    )


def test_exact_dwell_threshold_and_qualified_return_flow() -> None:
    inputs = _inputs(
        events=(
            _move(0, 0, "body-1", "loc-a", "loc-b"),
            _move(2, 0, "body-1", "loc-b", "loc-a"),
        )
    )
    history = fold_regional_history(inputs)
    assert history.final_population == {"a": 1, "b": 0, "c": 0}
    assert history.person_ticks == {"a": 3, "b": 2, "c": 0}
    assert history.raw_interregional_flows == {("a", "b"): 1, ("b", "a"): 1}
    assert [
        (
            row.origin_region_id,
            row.destination_region_id,
            row.candidate_arrival_boundary,
        )
        for row in history.qualified_migrations
    ] == [("a", "b", 1), ("b", "a", 3)]
    migration = compute_regional_migration_metrics(inputs)
    assert migration.values["interregional_raw_arrivals"] == 2
    assert migration.values["qualified_migration_count"] == 2
    assert migration.values["return_flow_count"] == 1


@pytest.mark.parametrize("entered_mid_run", (False, True))
def test_first_residence_requires_dwell_before_later_migration(
    entered_mid_run: bool,
) -> None:
    initial = (
        () if entered_mid_run else (RegionalInitialPlacementRow("body-1", "loc-x"),)
    )
    entry = (
        (
            RegionalEventRow(
                tick=0,
                sequence=0,
                kind="entry",
                body_id="body-1",
                destination_location_id="loc-x",
            ),
        )
        if entered_mid_run
        else ()
    )
    inputs = _inputs(
        initial=initial,
        residence_min_ticks=3,
        window_end=7,
        events=(
            *entry,
            _move(0, 1, "body-1", "loc-x", "loc-a"),
            _move(1, 0, "body-1", "loc-a", "loc-b"),
            _move(4, 0, "body-1", "loc-b", "loc-c"),
        ),
    )
    history = fold_regional_history(inputs)
    assert [
        (
            row.origin_region_id,
            row.destination_region_id,
            row.candidate_arrival_boundary,
            row.qualified_boundary,
        )
        for row in history.qualified_migrations
    ] == [("b", "c", 5, 7)]
    assert history.raw_interregional_flows == {("a", "b"): 1, ("b", "c"): 1}


def test_short_visit_cancels_candidate_without_migration() -> None:
    inputs = _inputs(
        residence_min_ticks=3,
        events=(
            _move(0, 0, "body-1", "loc-a", "loc-b"),
            _move(1, 0, "body-1", "loc-b", "loc-a"),
        ),
    )
    history = fold_regional_history(inputs)
    assert history.qualified_migrations == ()
    assert history.final_population == {"a": 1, "b": 0, "c": 0}
    assert sum(history.raw_interregional_flows.values()) == 2


def test_third_region_replaces_candidate_and_unassigned_clears_it() -> None:
    third = _inputs(
        residence_min_ticks=2,
        window_end=3,
        events=(
            _move(0, 0, "body-1", "loc-a", "loc-b"),
            _move(1, 0, "body-1", "loc-b", "loc-c"),
        ),
    )
    history = fold_regional_history(third)
    assert len(history.qualified_migrations) == 1
    assert (
        history.qualified_migrations[0].origin_region_id,
        history.qualified_migrations[0].destination_region_id,
        history.qualified_migrations[0].candidate_arrival_boundary,
    ) == ("a", "c", 2)

    unassigned = replace(
        _inputs(
            residence_min_ticks=2,
            window_end=4,
            events=(
                _move(0, 0, "body-1", "loc-a", "loc-x"),
                _move(1, 0, "body-1", "loc-x", "loc-b"),
            ),
        ),
        location_rows=(
            RegionalLocationRow("loc-a", "a"),
            RegionalLocationRow("loc-b", "b"),
            RegionalLocationRow("loc-c", "c"),
        ),
    )
    unassigned_history = fold_regional_history(unassigned)
    assert unassigned_history.assigned_unassigned_out == 1
    assert unassigned_history.assigned_unassigned_in == 1
    assert len(unassigned_history.qualified_migrations) == 1
    assert unassigned_history.qualified_migrations[0].origin_region_id == "a"
    assert unassigned_history.qualified_migrations[0].destination_region_id == "b"
    unassigned_doc = compute_regional_population(unassigned)
    assert unassigned_doc.values["unassigned_coverage"] == "present"
    assert unassigned_doc.values["unassigned_location_count"] == 1
    assert unassigned_doc.values["unassigned_person_ticks"] == 1


def test_entry_baseline_death_and_partial_prefix_coverage() -> None:
    entrant = RegionalEventRow(
        tick=0,
        sequence=0,
        kind="entry",
        body_id="body-new",
        destination_location_id="loc-b",
    )
    entered = fold_regional_history(
        _inputs(initial=(), events=(entrant,), window_end=3)
    )
    assert entered.entries["b"] == 1
    assert entered.qualified_migrations == ()

    death = RegionalEventRow(tick=1, sequence=1, kind="death", body_id="body-1")
    died_on_threshold = fold_regional_history(
        _inputs(
            window_end=2,
            events=(_move(0, 0, "body-1", "loc-a", "loc-b"), death),
        )
    )
    assert died_on_threshold.deaths["b"] == 1
    assert died_on_threshold.qualified_migrations == ()

    partial = compute_regional_population(
        _inputs(
            window_end=5,
            complete_through_boundary=2,
            events=(_move(0, 0, "body-1", "loc-a", "loc-b"),),
        )
    )
    assert partial.availability is MetricAvailability.PARTIAL
    assert partial.coverage is not None
    assert partial.coverage.observed == 3
    assert partial.coverage.expected == 6


def test_grouped_transport_counts_each_participant_and_conserves_population() -> None:
    inputs = _inputs(
        initial=(
            RegionalInitialPlacementRow("body-1", "loc-a"),
            RegionalInitialPlacementRow("body-2", "loc-a"),
        ),
        events=(
            _move(0, 0, "body-1", "loc-a", "loc-b", kind="transport"),
            _move(0, 0, "body-2", "loc-a", "loc-b", kind="transport"),
        ),
    )
    history = fold_regional_history(inputs)
    assert history.raw_interregional_flows[("a", "b")] == 2
    assert history.final_population == {"a": 0, "b": 2, "c": 0}
    assert history.relocation_kind_counts["transport"] == 2
    document = compute_regional_population(inputs)
    assert document.values["conservation_violations"] == 0
    assert document.values["assigned_living_population"] == 2


def test_stage_and_cohort_composition_appears_only_with_lifecycle_evidence() -> None:
    without_lifecycle = compute_regional_population(_inputs())
    assert without_lifecycle.values["lifecycle_evidence_available"] is False
    assert "region:a:stage:adult:living_population" not in without_lifecycle.values
    with_lifecycle = compute_regional_population(
        _inputs(
            initial=(
                RegionalInitialPlacementRow(
                    "body-1", "loc-a", stage_id="adult", cohort_id="cohort-1"
                ),
            )
        )
    )
    assert with_lifecycle.values["lifecycle_evidence_available"] is True
    assert with_lifecycle.values["region:a:stage:adult:living_population"] == 1
    assert with_lifecycle.values["region:a:cohort:cohort-1:living_population"] == 1


def test_same_tick_relocations_are_folded_in_order_and_wrong_origins_fail() -> None:
    inputs = _inputs(
        window_end=1,
        residence_min_ticks=1,
        events=(
            _move(0, 0, "body-1", "loc-a", "loc-b"),
            _move(0, 1, "body-1", "loc-b", "loc-c"),
        ),
    )
    history = fold_regional_history(inputs)
    assert history.raw_interregional_flows == {("a", "b"): 1, ("b", "c"): 1}
    assert history.final_population == {"a": 0, "b": 0, "c": 1}
    with pytest.raises(RegionalPopulationError, match="relocation_origin_mismatch"):
        fold_regional_history(
            replace(inputs, events=(_move(0, 0, "body-1", "loc-b", "loc-c"),))
        )


def _event(
    tick: int,
    sequence: int,
    actor: str,
    details: object,
    origin: str,
    dest: str | None,
):
    request_id = RequestId(f"request-{tick}-{sequence}")
    cause = (
        SystemCause(
            request_id,
            SystemEffectFamily.TRAVEL,
            EntityId(details.journey_id),
            sequence,
        )
        if isinstance(details, (JourneyArrived, JourneyEnded))
        else ActionCause(request_id, EntityId(actor))
    )
    return make_physical_replayable_event(
        event_id=EventId(f"event-{tick}-{sequence}"),
        run_id="regional-run",
        world_id=WorldId("regional-world"),
        tick=tick,
        sequence=sequence,
        cause=cause,
        resulting_revision=WorldRevision(tick + 1),
        details=details,
        occurrence=build_occurrence_context(
            details,
            origin_location_id=EntityId(origin),
            destination_location_id=None if dest is None else EntityId(dest),
        ),
        schema_version=EVENT_SCHEMA_REPLAY_V21,
    )


def test_event_composition_counts_successful_flee_transport_and_journey_once() -> None:
    events = (
        _event(
            0,
            0,
            "body-1",
            Fled(
                success=True,
                destination_id=EntityId("loc-b"),
                fatigue_delta=1.0,
                resulting_fatigue=1.0,
            ),
            "loc-a",
            "loc-b",
        ),
        _event(
            1,
            0,
            "body-1",
            Transported(
                EntityId("body-2"),
                EntityId("loc-c"),
                origin_location_id=EntityId("loc-b"),
                helper_fatigue_delta=1.0,
                resulting_helper_fatigue=1.0,
            ),
            "loc-b",
            "loc-c",
        ),
        _event(
            2,
            0,
            "body-1",
            JourneyArrived(
                "journey-1",
                (EntityId("body-1"),),
                EntityId("loc-c"),
                EntityId("loc-a"),
            ),
            "loc-c",
            "loc-a",
        ),
        _event(
            3,
            0,
            "body-1",
            Fled(success=False),
            "loc-a",
            None,
        ),
        _event(
            4,
            0,
            "body-1",
            Moved(
                EntityId("loc-b"),
                resulting_location_id=EntityId("loc-b"),
                fatigue_delta=1.0,
                resulting_fatigue=1.0,
            ),
            "loc-a",
            "loc-b",
        ),
        _event(
            5,
            0,
            "body-1",
            JourneyEnded(
                "journey-timeout",
                (EntityId("body-1"),),
                EntityId("loc-a"),
                EntityId("loc-b"),
                "arrival_timeout",
            ),
            "loc-a",
            "loc-b",
        ),
    )
    rows = regional_population_rows_from_events(events)
    assert [(row.body_id, row.relocation_kind) for row in rows] == [
        ("body-1", "flee"),
        ("body-1", "transport"),
        ("body-2", "transport"),
        ("body-1", "journey"),
        ("body-1", "move"),
    ]
    fled_rows = tuple(row for row in rows if row.relocation_kind == "flee")
    fled_history = fold_regional_history(
        _inputs(
            window_end=1,
            events=fled_rows,
        )
    )
    assert fled_history.final_population == {"a": 0, "b": 1, "c": 0}


@pytest.mark.asyncio
async def test_population_composition_keeps_bootstrap_and_owner_evidence_detached() -> (
    None
):
    body = alive_body("body-1", location_id="loc-a")
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("a", "A"), RegionDefinition("b", "B")),
        location_regions=(
            LocationRegion(EntityId("loc-a"), "a"),
            LocationRegion(EntityId("loc-b"), "b"),
        ),
        routes=(RouteSpec(EntityId("loc-a"), EntityId("loc-b"), 2, 4.0),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    context = regional_context_from_run(
        regions_spec=spec,
        bodies=(body,),
        known_location_ids=(EntityId("loc-a"), EntityId("loc-b")),
        owner_ids=("agent-1", "agent-2"),
    )
    assert context is not None
    assert context.region_ids == ("a", "b")
    assert context.initial_placements[0].location_id == "loc-a"
    assert context.owner_ids == ("agent-1", "agent-2")
    persisted = PersistedAnalysisSnapshot(
        experiment_id="",
        run_id="regional-snapshot-run",
        owner_id="agent-1",
        traces=(),
        reconstructions=(),
        derivation_edges=(),
        events=(),
        regional_context=context,
    )
    regional_input = regional_population_input_from_snapshot(
        persisted,
        input_revision="regional-revision",
        window_end=3,
    )
    assert regional_input is not None
    assert regional_input.residence_min_ticks == 2
    assert regional_input.initial_placements[0].alive
    prefix_input = regional_population_input_from_snapshot(
        replace(persisted, objective_complete_through_boundary=2),
        input_revision="regional-revision",
        window_end=5,
    )
    assert prefix_input is not None
    assert prefix_input.complete_through_boundary == 2

    observed = Observation(
        world_id=WorldId("regional-world"),
        observer_id=body.entity_id,
        revision=WorldRevision(2),
        tick=3,
        self_body=ObservedSelf(
            entity_id=body.entity_id,
            location_id=EntityId("loc-a"),
            health=body.health,
            hunger=body.hunger,
            thirst=body.thirst,
            fatigue=body.fatigue,
            temperature=body.temperature,
            inventory=(),
            life_status=body.life_status,
            carry_capacity=body.carry_capacity,
        ),
        exits=(
            VisibleExit(
                destination_id=EntityId("loc-b"),
                name="B",
                travel_duration_ticks=2,
                fatigue_cost=4.0,
                destination_region_id="b",
            ),
        ),
        regional_context=ObservedRegionalContext("a", "A"),
    )
    trace = destination_memory_trace(
        owner_id=AgentId("agent-1"),
        observer_body_id=body.entity_id,
        observation=observed,
        exit_view=observed.exits[0],
    )
    evidence_rows = regional_destination_evidence_rows_from_traces((trace,))
    assert len(evidence_rows) == 1
    assert evidence_rows[0].destination_id == "loc-b"
    assert evidence_rows[0].region_id == "b"
    assert evidence_rows[0].owner_id == "agent-1"
    second_trace = destination_memory_trace(
        owner_id=AgentId("agent-2"),
        observer_body_id=body.entity_id,
        observation=observed,
        exit_view=observed.exits[0],
    )
    owner_one = replace(persisted, traces=(trace,))
    owner_two = replace(persisted, owner_id="agent-2", traces=(second_trace,))
    joined_population, joined_evidence, expected_owners = (
        regional_metric_inputs_from_snapshots(
            (owner_one, owner_two),
            input_revision="regional-revision",
            window_end=3,
        )
    )
    assert joined_population is not None
    assert joined_evidence is not None and len(joined_evidence) == 2
    assert expected_owners == 2

    class Reader:
        async def load(self, *, run_id, owner_id, experiment_id=None, manifest=None):
            assert run_id == persisted.run_id
            return {"agent-1": owner_one, "agent-2": owner_two}[owner_id]

    loaded = await EvidenceCompositionService(Reader()).load_regional_metric_inputs(
        run_id=persisted.run_id,
        owner_id="agent-1",
        input_revision="regional-revision",
        window_end=3,
    )
    assert loaded[0] is not None
    assert loaded[1] is not None and len(loaded[1]) == 2
    assert loaded[2] == 2


def test_metric_service_registers_all_regional_families() -> None:
    docs = assemble_metric_documents(
        MetricComputationInputs(
            run_id="regional-run",
            input_revision="regional-revision",
            window_end=2,
            regional_population=_inputs(window_end=2),
            regional_destination_evidence=(),
            regional_destination_expected_owner_count=1,
        )
    ).documents
    assert {
        "regional_population",
        "regional_migration",
        "regional_destination_beliefs",
    } <= {doc.metric_family for doc in docs}
    assert METRIC_FAMILY_COUNT == 130
    assert len(validate_metric_catalog()) == 130


def test_destination_belief_coverage_distinguishes_unavailable_from_empty() -> None:
    unavailable = compute_regional_destination_beliefs(
        None,
        run_id="regional-run",
        input_revision="regional-revision",
        as_of_tick=5,
        expected_owner_count=3,
    )
    empty = compute_regional_destination_beliefs(
        (),
        run_id="regional-run",
        input_revision="regional-revision",
        as_of_tick=5,
        expected_owner_count=3,
    )
    assert unavailable.availability is MetricAvailability.UNKNOWN
    assert empty.availability is MetricAvailability.ABSENT
    assert empty.coverage is not None
    assert empty.coverage.observed == 0
    assert empty.coverage.expected == 3

    partial = compute_regional_destination_beliefs(
        (
            RegionalDestinationEvidenceRow(
                owner_id="agent-1",
                destination_id="loc-remote",
                region_id="far",
                source_kind="communicated",
                source_tick=2,
                confidence=0.7,
            ),
        ),
        run_id="regional-run",
        input_revision="regional-revision",
        as_of_tick=5,
        expected_owner_count=2,
    )
    assert partial.availability is MetricAvailability.PARTIAL
    assert partial.coverage is not None
    assert partial.coverage.ratio == 0.5
    assert partial.values["communicated_count"] == 1
    assert partial.values["mean_source_age_ticks"] == 3
