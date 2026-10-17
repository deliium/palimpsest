"""Composition harvests for candidate-society analysis stay detached."""

from __future__ import annotations

from types import SimpleNamespace

from analysis.models import RelationshipEdgeRow
from analysis.society_divergence import SocietyDigestRow
from analysis.society_emergence import SocietyEdgeRow, SocietyResidenceRow
from analysis.society_isolation import SocietyEvidenceEdge, SocietyJourneyRow
from experiments.composition import (
    society_digest_rows_from_channel_rows,
    society_emission_inputs_from_context,
    society_interaction_edges_from_events,
    society_trust_edges_from_relationship_rows,
)


def test_context_composition_is_deterministic() -> None:
    kwargs = dict(
        run_id="run-c",
        input_revision="rev-c",
        tick=8,
        living_person_ids=("a", "b", "c", "d"),
        residence_rows=(
            SocietyResidenceRow("a", "north", 0, 8),
            SocietyResidenceRow("b", "north", 0, 8),
            SocietyResidenceRow("c", "south", 0, 8),
            SocietyResidenceRow("d", "south", 0, 8),
        ),
        interaction_edges=(
            SocietyEdgeRow("a", "b", 1),
            SocietyEdgeRow("c", "d", 2),
        ),
        dimension_rows=(
            SocietyDigestRow("vocabulary", "a", "t1"),
            SocietyDigestRow("vocabulary", "b", "t1"),
            SocietyDigestRow("vocabulary", "c", "t2"),
            SocietyDigestRow("vocabulary", "d", "t2"),
        ),
    )
    first = society_emission_inputs_from_context(**kwargs)
    second = society_emission_inputs_from_context(**kwargs)
    assert first.emission == second.emission
    assert first.divergence == second.divergence
    assert first.isolation == second.isolation
    assert len(first.emission.communities) == 2


def test_communication_events_become_interaction_edges() -> None:
    class Talked:
        recipient_id = "listener"

    events = (SimpleNamespace(tick=3, actor_id="speaker", details=Talked()),)
    edges = society_interaction_edges_from_events(events)
    assert edges == (SocietyEdgeRow("speaker", "listener", 3),)


def test_trust_projection_takes_latest_nonnegative_active_revision() -> None:
    rows = (
        RelationshipEdgeRow(
            source_id="a",
            target_id="b",
            logical_tick=1,
            activation_state="active",
            trust=0.4,
        ),
        RelationshipEdgeRow(
            source_id="a",
            target_id="b",
            logical_tick=2,
            activation_state="active",
            trust=0.7,
        ),
        RelationshipEdgeRow(
            source_id="a",
            target_id="c",
            logical_tick=2,
            activation_state="active",
            trust=-0.5,
        ),
    )
    edges = society_trust_edges_from_relationship_rows(rows)
    assert edges == (SocietyEdgeRow("a", "b", 2, lane="trust", weight=0.7),)


def test_channel_rows_project_to_digest_rows() -> None:
    rows = (
        SimpleNamespace(agent_id="a", digest_id_token="digest-a"),
        SimpleNamespace(agent_id="b", token="digest-b"),
        SimpleNamespace(agent_id=None, token="orphan"),
    )
    digest_rows = society_digest_rows_from_channel_rows("vocabulary", rows)
    assert digest_rows == (
        SocietyDigestRow("vocabulary", "a", "digest-a"),
        SocietyDigestRow("vocabulary", "b", "digest-b"),
    )


def test_journey_evidence_explains_cross_edge() -> None:
    inputs = society_emission_inputs_from_context(
        run_id="run-j",
        input_revision="rev-j",
        tick=9,
        living_person_ids=("a", "b", "c", "d"),
        residence_rows=(
            SocietyResidenceRow("a", "north", 0, 9),
            SocietyResidenceRow("b", "north", 0, 9),
            SocietyResidenceRow("c", "south", 0, 9),
            SocietyResidenceRow("d", "south", 0, 9),
        ),
        interaction_edges=(
            SocietyEdgeRow("a", "b", 1),
            SocietyEdgeRow("c", "d", 1),
            SocietyEdgeRow("a", "c", 6),
        ),
        evidence_edges=(SocietyEvidenceEdge("e1", "communication", "a", "c", 6),),
        journeys=(SocietyJourneyRow("a", "north", "south", 5),),
    )
    assert inputs.isolation.explained_count == 1
    assert inputs.isolation.unexplained_count == 0


def test_snapshot_digest_harvest_and_manifest_scope() -> None:
    import pytest

    from analysis.models import RelationshipEdgeRow  # noqa: F401
    from experiments.composition import (
        EvidenceCompositionError,
        society_digest_rows_from_snapshot,
        society_emission_inputs_from_snapshot,
    )
    from experiments.persistence import (
        PersistedAnalysisSnapshot,
        PersistedRegionalContext,
        PersistedRegionalInitialPlacement,
        PersistedRegionalLocation,
    )
    from simulation.evidence import EvidenceHighWaterMarks, build_evidence_manifest

    context = PersistedRegionalContext(
        region_ids=("north",),
        known_location_ids=("loc-north",),
        locations=(PersistedRegionalLocation("loc-north", "north"),),
        initial_placements=(
            PersistedRegionalInitialPlacement("a", "loc-north", True),
            PersistedRegionalInitialPlacement("b", "loc-north", True),
        ),
        owner_ids=("a", "b"),
        residence_min_ticks=1,
    )
    snapshot = PersistedAnalysisSnapshot(
        experiment_id="multiple_societies@1",
        run_id="run-snapshot",
        owner_id="a",
        traces=(),
        reconstructions=(),
        derivation_edges=(),
        events=(),
        regional_context=context,
        objective_complete_through_boundary=2,
    )
    digest_rows = society_digest_rows_from_snapshot(
        snapshot,
        dimension_sources={
            "vocabulary": (
                SimpleNamespace(agent_id="a", token="term:a"),
                SimpleNamespace(agent_id="b", token="term:b"),
            )
        },
    )
    assert {row.dimension for row in digest_rows} == {"vocabulary"}

    manifest = build_evidence_manifest(
        run_id="run-snapshot",
        objective_commit_hash="c" * 64,
        high_water=EvidenceHighWaterMarks(
            direct_memories=0,
            communicated_memories=0,
            reconstructions=0,
            beliefs=0,
            relationships=0,
            goals=0,
            resolutions=0,
            truth_specs=0,
        ),
    )
    inputs = society_emission_inputs_from_snapshot(
        snapshot,
        input_revision="rev-snapshot",
        manifest=manifest,
    )
    assert inputs is not None
    assert inputs.emission.singleton_person_ids == ("a", "b")

    wrong = build_evidence_manifest(
        run_id="other-run",
        objective_commit_hash="d" * 64,
        high_water=EvidenceHighWaterMarks(
            direct_memories=0,
            communicated_memories=0,
            reconstructions=0,
            beliefs=0,
            relationships=0,
            goals=0,
            resolutions=0,
            truth_specs=0,
        ),
    )
    with pytest.raises(EvidenceCompositionError, match="manifest_run_scope_mismatch"):
        society_emission_inputs_from_snapshot(
            snapshot,
            input_revision="rev-snapshot",
            manifest=wrong,
        )
