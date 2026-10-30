"""Detached overlay composition over finalized capture evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from analysis.civilization_overlays import (
    compose_culture_rows,
    compose_institution_rows,
    compose_settlement_rows,
    compose_technology_rows,
    compose_trade_rows,
)
from experiments.civilization_publication import (
    CivilizationCapturedHistory,
    compose_civilization_boundary,
)
from simulation.civilization_boundaries import (
    CivilizationBoundaryInput,
    project_civilization_boundary,
)
from simulation.civilization_capture import (
    CivilizationInventoryChannel,
    CivilizationInventoryCoverage,
    CivilizationOwnerConcept,
    CivilizationOwnerConceptEvidence,
    CivilizationOwnerDecaySample,
    CivilizationOwnerGroup,
    CivilizationOwnerInventory,
    CivilizationOwnerKnowledge,
    CivilizationOwnerTrait,
    project_civilization_events,
)
from simulation.civilization_models import (
    CivilizationCoverage,
    CivilizationCoverageState,
    CivilizationLayer,
)
from world.identifiers import EntityId
from world.production import Structure, StructureKind

pytestmark = pytest.mark.unit

_RUN = "run-capture"
_WORLD = "world-capture"


def _inventory(
    owner: str,
    *,
    living: bool = True,
    cultural: tuple[CivilizationOwnerTrait, ...] = (),
    terminology: tuple[CivilizationOwnerTrait, ...] = (),
    narratives: tuple[CivilizationOwnerTrait, ...] = (),
    knowledge: tuple[CivilizationOwnerKnowledge, ...] = (),
    groups: tuple[CivilizationOwnerGroup, ...] = (),
    concepts: tuple[CivilizationOwnerConcept, ...] = (),
    decay: tuple[CivilizationOwnerDecaySample, ...] = (),
) -> CivilizationOwnerInventory:
    present = {
        CivilizationInventoryChannel.CULTURAL_FEATURES: bool(cultural),
        CivilizationInventoryChannel.TERMINOLOGY: bool(terminology),
        CivilizationInventoryChannel.NARRATIVES: bool(narratives),
        CivilizationInventoryChannel.PRACTICAL_KNOWLEDGE: bool(knowledge),
        CivilizationInventoryChannel.GROUPS: bool(groups),
        CivilizationInventoryChannel.INSTITUTION_CONCEPTS: bool(concepts),
        CivilizationInventoryChannel.INSTITUTIONAL_DECAY: bool(decay),
        CivilizationInventoryChannel.OFFICES: False,
    }
    channels = tuple(
        CivilizationInventoryCoverage(
            channel,
            (
                CivilizationCoverage(CivilizationCoverageState.COMPLETE)
                if present[channel]
                else CivilizationCoverage(
                    CivilizationCoverageState.DISABLED, "capture_off"
                )
            ),
        )
        for channel in CivilizationInventoryChannel
    )
    return CivilizationOwnerInventory(
        owner,
        0,
        living,
        channels,
        cultural,
        terminology,
        narratives,
        knowledge,
        groups,
        concepts,
        (),
        decay,
    )


def _frame(
    tick: int,
    *,
    inventories: tuple[CivilizationOwnerInventory, ...] = (),
    structures: tuple[Structure, ...] = (),
) -> CivilizationBoundaryInput:
    from tests.unit.test_observer_civilization import _physical_scene

    scene = replace(
        _physical_scene(),
        run_id=_RUN,
        world_id=_WORLD,
        tick=tick,
        revision=tick,
        structures=structures,
    )
    return project_civilization_boundary(scene, owner_inventories=inventories)


def _structure(location: str = "loc-1") -> Structure:
    return Structure(
        EntityId("structure-1"), EntityId(location), StructureKind.SHELTER, 1.0, 0
    )


def test_settlements_need_four_complete_boundaries_and_intact_infrastructure() -> None:
    inventories = (_inventory("not-the-body-id"),)
    active = tuple(
        _frame(tick, inventories=inventories, structures=(_structure(),))
        for tick in range(5)
    )
    rows = {
        row.location_id: row for row in compose_settlement_rows(active, boundary_tick=4)
    }
    assert rows["loc-1"].status == "active"
    assert rows["loc-1"].observed_streak == 2
    assert rows["loc-1"].first_supported_boundary == 3
    assert rows["loc-2"].status == "inactive"

    gapped = tuple(frame for frame in active if frame.cursor.tick != 2)
    censored = {
        row.location_id: row for row in compose_settlement_rows(gapped, boundary_tick=4)
    }
    assert censored["loc-1"].status == "censored"
    assert censored["loc-1"].history.coverage.reason == "capture_gap"


def _knowledge(
    entry_id: str,
    *,
    acquired: int,
    origin: str,
    teacher: str | None = None,
    parents: tuple[str, ...] = (),
    active: bool = True,
) -> CivilizationOwnerKnowledge:
    return CivilizationOwnerKnowledge(
        entry_id,
        "crafting_process",
        "tech:canary",
        origin,
        parents,
        entry_id,
        0,
        False,
        (),
        acquired,
        active,
        "crafting",
        teacher,
        teacher,
    )


def test_technology_attribution_distinguishes_teaching_rediscovery_and_future() -> None:
    inventories = (
        _inventory(
            "agent-a",
            knowledge=(
                _knowledge(
                    "knowledge-taught",
                    acquired=1,
                    origin="teaching",
                    teacher="agent-b",
                    parents=("knowledge-source",),
                ),
                _knowledge(
                    "knowledge-alone", acquired=2, origin="independent_discovery"
                ),
                _knowledge(
                    "knowledge-future",
                    acquired=4,
                    origin="teaching",
                    teacher="agent-b",
                    parents=("source",),
                ),
            ),
        ),
    )
    frame = _frame(4, inventories=inventories)
    rows = {row.context.row_id: row for row in compose_technology_rows(frame)}
    taught = rows["technology:agent-a:knowledge-taught"]
    assert taught.attribution == "attributable"
    assert taught.modality == "teaching"
    assert taught.source_owner_id == "agent-b"
    alone = rows["technology:agent-a:knowledge-alone"]
    assert alone.attribution == "rediscovery"
    assert "technology:agent-a:knowledge-future" not in rows


def test_culture_uses_exact_representation_identity_and_unknown_denominators() -> None:
    trait = CivilizationOwnerTrait("trait-a", "fingerprint-1", 0, 1)
    duplicate = CivilizationOwnerTrait("trait-b", "fingerprint-1", 1, 2)
    first = _inventory("agent-a", cultural=(trait, duplicate))
    second = _inventory(
        "agent-b", cultural=(CivilizationOwnerTrait("trait-c", "fingerprint-2", 0, 1),)
    )
    unknown = replace(
        _inventory("agent-c"),
        channels=tuple(
            replace(
                channel,
                coverage=(
                    CivilizationCoverage(
                        CivilizationCoverageState.UNAVAILABLE, "capture_gap"
                    )
                    if channel.channel is CivilizationInventoryChannel.CULTURAL_FEATURES
                    else channel.coverage
                ),
            )
            for channel in _inventory("agent-c").channels
        ),
    )
    rows = compose_culture_rows(_frame(4, inventories=(first, second, unknown)))
    by_trait = {row.trait_id: row for row in rows}
    shared = by_trait["cultural_features:fingerprint-1"]
    assert shared.carrier_count == 1
    assert shared.carrier_ids == ("agent-a",)
    assert shared.eligible_owner_count == 2
    assert shared.unavailable_owner_count == 1
    assert shared.proportion is None


def test_trade_counts_only_completed_exchanges_and_keeps_event_time_location() -> None:
    from tests.unit.test_civilization_capture import _event, _exchange

    batches = (
        project_civilization_events(
            _RUN,
            0,
            (_event(_exchange(), tick=0, sequence=0),),
            expected_count=1,
            source="committed_result",
        ),
    )
    rows = compose_trade_rows(batches, boundary_tick=1)
    assert len(rows) == 1
    assert rows[0].completed_exchange_count == 1
    assert rows[0].occurrence_location_id == "loc-at-event"
    assert [(row.kind.value, row.count) for row in rows[0].forward_items] == [
        ("tool", 1)
    ]


def _decay(
    owner: str, tick: int, *, strength: float = 0.9, pruned: bool = False
) -> CivilizationOwnerDecaySample:
    return CivilizationOwnerDecaySample(
        local_pattern_id="pattern-1",
        group_key="group-1",
        concept_id="concept-1",
        inception_tick=0,
        observation_tick=tick,
        source_first_tick=0,
        source_last_tick=tick,
        role_recognition=strength,
        procedure_recurrence=strength,
        social_expectation=strength,
        legitimacy_belief=strength,
        succession_observed=strength,
        generational_continuity=strength,
        recognized=True,
        covered=True,
        pruned=pruned,
        anchor_digests=("anchor-1",),
        structural_components=("component-1",),
        context_key=None,
        office_id=None,
        observed_cohort=("agent-a", "agent-b"),
        participant_actions=(("agent-a", "practice"),),
        performed_procedure_keys=("procedure-1",),
    )


def test_cumulative_decay_samples_are_deduplicated_and_never_duplicated_rows() -> None:
    samples = tuple(_decay("agent-a", tick) for tick in range(8))
    inventories = (_inventory("agent-a", decay=samples),)
    frame = _frame(8, inventories=inventories)
    rows = compose_institution_rows(frame)
    episodes = [row for row in rows if row.kind == "episode"]
    assert len(episodes) == 1
    assert episodes[0].status == "stable"
    # Re-exporting identical samples at a later boundary does not duplicate.
    repeated = _inventory("agent-a", decay=(*samples, _decay("agent-a", 7)))
    assert len(compose_institution_rows(_frame(8, inventories=(repeated,)))) == len(
        rows
    )


def test_censored_episode_lifecycle_publishes_as_censored_instead_of_rejecting(
) -> None:
    # A single decay sample cannot form a complete four-tick window, so the
    # lifecycle state is `unknown`; the presentation row must still compose.
    inventories = (_inventory("agent-a", decay=(_decay("agent-a", 1),)),)
    rows = compose_institution_rows(_frame(2, inventories=inventories))
    episodes = [row for row in rows if row.kind == "episode"]
    assert len(episodes) == 1
    assert episodes[0].status == "censored"


def test_publication_requires_an_exact_boundary_and_keeps_owner_scope_separate(
) -> None:
    frame = _frame(0, inventories=(_inventory("agent-a"),))
    history = CivilizationCapturedHistory(_RUN, _WORLD, (frame,), ())
    publication = compose_civilization_boundary(history, 0)
    assert publication.cursor.boundary_tick == 0
    assert all(
        scope.evidence_class.value in {"OBJECTIVE", "SUBJECTIVE", "ANALYTICAL"}
        for scope in publication.scopes
    )
    with pytest.raises(ValueError):
        compose_civilization_boundary(history, 1)
    assert all(
        row.context.row_id.startswith(
            (
                "settlement:",
                "migration:",
                "trade:",
                "culture:",
                "technology:",
                "group:",
                "institution:",
            )
        )
        for row in publication.rows
    )


def test_analytical_groups_use_residence_without_inventing_trust() -> None:
    from agents.models import AgentId
    from analysis.civilization_overlays import compose_group_rows
    from simulation.registrations import AgentRegistration
    from tests.simulation_helpers import alive_body
    from tests.unit.test_observer_civilization import _physical_scene

    scene = replace(
        _physical_scene(),
        run_id=_RUN,
        world_id=_WORLD,
        tick=0,
        revision=0,
        bodies=(alive_body("body-a"), alive_body("body-b")),
        registrations=(
            AgentRegistration(AgentId("agent-a"), EntityId("body-a")),
            AgentRegistration(AgentId("agent-b"), EntityId("body-b")),
        ),
    )
    frame = project_civilization_boundary(
        scene,
        owner_inventories=(_inventory("agent-a"), _inventory("agent-b")),
    )
    rows = compose_group_rows(frame)
    analytical = [row for row in rows if row.basis == "interaction_residence"]
    assert analytical
    assert all(row.missing_lanes == ("interaction", "trust") for row in analytical)


def test_grounded_concept_keeps_evidence_site_anchor_and_unplaced_rows_do_not() -> None:
    evidence = CivilizationOwnerConceptEvidence(
        "evidence-1",
        3,
        "observed",
        "role_recognition",
        "project-0-0-3",
        "agent-a",
    )
    concept = CivilizationOwnerConcept(
        "concept-1", "recognized", "named_usual", 1, 3, 3, (evidence,)
    )
    from simulation.civilization_capture import (
        CivilizationGroundingObservation,
        CivilizationGroundingProject,
    )

    observation = CivilizationGroundingObservation(
        "agent-a",
        3,
        (CivilizationGroundingProject("project-1", "loc-1", ((0, 3),)),),
        (),
    )
    from tests.unit.test_observer_civilization import _physical_scene

    scene = replace(_physical_scene(), run_id=_RUN, world_id=_WORLD, tick=4, revision=4)
    frame = project_civilization_boundary(
        scene,
        owner_inventories=(_inventory("agent-a", concepts=(concept,)),),
        grounding_observations=(observation,),
        grounding_observations_complete=True,
    )
    rows = compose_institution_rows(frame)
    grounded = next(row for row in rows if row.native_id == "concept-1")
    assert [
        (anchor.kind.value, anchor.location_id) for anchor in grounded.context.anchors
    ] == [("project", "loc-1")]
    unplaced_frame = project_civilization_boundary(
        replace(scene, tick=4),
        owner_inventories=(_inventory("agent-a", concepts=(concept,)),),
    )
    unplaced = next(
        row
        for row in compose_institution_rows(unplaced_frame)
        if row.native_id == "concept-1"
    )
    assert unplaced.context.anchors == ()


def test_publication_layer_contracts_use_expected_scopes() -> None:
    frame = _frame(
        0,
        inventories=(
            _inventory(
                "agent-a",
                cultural=(CivilizationOwnerTrait("trait-a", "repr-1", 0, 0),),
            ),
        ),
    )
    history = CivilizationCapturedHistory(_RUN, _WORLD, (frame,), ())
    publication = compose_civilization_boundary(history, 0)
    layers = {scope.layer for scope in publication.scopes}
    assert CivilizationLayer.SETTLEMENTS in layers
    assert CivilizationLayer.CULTURE in layers


def test_boundary_markers_are_pinned_to_the_committed_boundary() -> None:
    from simulation.civilization_models import CivilizationMarkerType

    inventories = (_inventory("not-the-body-id"),)
    frames = tuple(
        _frame(
            tick,
            inventories=inventories,
            structures=(_structure(),) if tick == 4 else (),
        )
        for tick in range(5)
    )
    history = CivilizationCapturedHistory(_RUN, _WORLD, frames, ())
    publication = compose_civilization_boundary(history, 4)
    assert publication.markers
    assert all(marker.seek_boundary == 4 for marker in publication.markers)
    assert any(
        marker.marker_type is CivilizationMarkerType.SETTLEMENT_ACTIVATED
        for marker in publication.markers
    )
