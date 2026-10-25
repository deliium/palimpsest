"""Independent civilization contract, epistemic and resource invariants."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, fields, replace

import pytest

from simulation.civilization_codec import (
    civilization_digest,
    decode_civilization_value,
    encode_civilization_value,
)
from simulation.civilization_models import (
    CivilizationAnchor,
    CivilizationAnchorKind,
    CivilizationArtifactRef,
    CivilizationCoverage,
    CivilizationCoverageState,
    CivilizationCursor,
    CivilizationError,
    CivilizationEvidenceClass,
    CivilizationHashManifest,
    CivilizationLayer,
    CivilizationMarker,
    CivilizationMarkerType,
    CivilizationScope,
    CivilizationSection,
    CivilizationSourceRef,
    CivilizationWindow,
)
from simulation.civilization_paging import select_civilization_rows
from simulation.civilization_ports import (
    CivilizationBoundaryPublication,
    CivilizationPage,
    CivilizationReadBudget,
    CivilizationReadPort,
)
from simulation.civilization_rows import (
    CivilizationCapturedRow,
    CivilizationCultureRow,
    CivilizationGroupRow,
    CivilizationInstitutionRow,
    CivilizationLayerContext,
    CivilizationLocationRow,
    CivilizationMapRow,
    CivilizationMigrationRow,
    CivilizationProjectRow,
    CivilizationPublicActs,
    CivilizationRecordRow,
    CivilizationRegionRow,
    CivilizationRepositoryRow,
    CivilizationRouteRow,
    CivilizationRowContext,
    CivilizationSettlementRow,
    CivilizationTechnologyRow,
    CivilizationTradeRow,
)
from world.artifacts import ArtifactKind
from world.collective_projects import CollectiveProjectKind, CollectiveProjectStatus
from world.identifiers import EntityId
from world.repositories import RepositoryAccessMode, RepositoryStatus
from world.values import ItemKind

pytestmark = pytest.mark.unit

COMPLETE = CivilizationCoverage(CivilizationCoverageState.COMPLETE)
CURSOR = CivilizationCursor("run", "world", 4, None, 4, 4)
REF = CivilizationSourceRef("scene", "scene", 4)
CONTEXT = CivilizationRowContext("row", (REF,))


def _history(layer: CivilizationLayer) -> CivilizationLayerContext:
    evidence = (
        CivilizationEvidenceClass.OBJECTIVE
        if layer is CivilizationLayer.MIGRATION
        else CivilizationEvidenceClass.ANALYTICAL
    )
    return CivilizationLayerContext(
        CivilizationScope(layer, evidence),
        4,
        CivilizationWindow(0, 4),
        "civilization-overlays.v1",
        COMPLETE,
    )


def _row_cases() -> tuple[CivilizationMapRow | CivilizationCapturedRow, ...]:
    return (
        CivilizationRegionRow(CONTEXT, "region", 1, ("location",)),
        CivilizationRouteRow(CONTEXT, "route", "a", "b", "r1", "r2", 3, 2.0),
        CivilizationLocationRow(
            CONTEXT, "location", None, 2, 1, 2, None, None, 1, 0, 0, 0, ()
        ),
        CivilizationProjectRow(
            CONTEXT,
            "project",
            "location",
            CollectiveProjectKind.WELL,
            CollectiveProjectStatus.OPEN,
            1,
            3,
            1,
            2,
            ItemKind.MATERIAL,
            0,
            (),
            None,
            None,
            0,
            CivilizationPublicActs(),
        ),
        CivilizationRepositoryRow(
            CONTEXT,
            "repository",
            "location",
            RepositoryStatus.INTACT,
            RepositoryAccessMode.OPEN,
            1,
            ("record",),
            None,
            0,
            0,
            0,
        ),
        CivilizationRecordRow(
            CONTEXT,
            "record",
            ArtifactKind.NOTE,
            None,
            None,
            "location",
            None,
            None,
            None,
            None,
            0,
            0,
            0,
            0,
        ),
        CivilizationSettlementRow(
            CONTEXT,
            _history(CivilizationLayer.SETTLEMENTS),
            "candidate",
            "location",
            2,
            1,
            4,
            4,
            4,
            4,
            "active",
        ),
        CivilizationMigrationRow(
            CONTEXT,
            _history(CivilizationLayer.MIGRATION),
            "journey",
            "route",
            "a",
            "b",
            1,
            ("owner",),
            "arrived",
            1,
            3,
            None,
            1,
            1,
            0,
            0,
        ),
        CivilizationTradeRow(
            CONTEXT, _history(CivilizationLayer.TRADE), ("a", "b"), 1, (), (), None
        ),
        CivilizationCultureRow(
            CONTEXT,
            _history(CivilizationLayer.CULTURE),
            "trait",
            "representation",
            "living_population",
            1,
            ("owner",),
            2,
            0,
            0.5,
        ),
        CivilizationTechnologyRow(
            CONTEXT,
            _history(CivilizationLayer.TECHNOLOGY),
            "owner:knowledge",
            "owner",
            "acquired",
            4,
            "unknown",
            "unknown",
            None,
            None,
            1,
            2,
        ),
        CivilizationGroupRow(
            CONTEXT,
            _history(CivilizationLayer.SOCIAL_GROUPS),
            "group",
            "interaction_residence",
            1,
            ("owner",),
            ("trust",),
        ),
        CivilizationInstitutionRow(
            CONTEXT,
            _history(CivilizationLayer.INSTITUTIONS),
            "institution",
            "owner",
            "concept",
            "concept",
            "stable",
            4,
            4,
            1,
            3,
        ),
    )


@pytest.mark.parametrize("row", _row_cases(), ids=lambda row: type(row).__name__)
def test_every_closed_row_round_trips_without_coordinate_or_payload_fields(row):
    encoded = encode_civilization_value(row)
    assert decode_civilization_value(encoded) == row
    assert encoded.endswith(b"\n") and not encoded.endswith(b"\n\n")
    forbidden = {"x", "y", "coordinates", "payload", "marks", "index_entries", "label"}
    assert forbidden.isdisjoint(field.name for field in fields(row))


@pytest.mark.parametrize("layer", [*CivilizationSection, *CivilizationLayer])
@pytest.mark.parametrize("evidence", list(CivilizationEvidenceClass))
@pytest.mark.parametrize("owner", [None, "owner"])
def test_scope_supported_combinations_are_independent(layer, evidence, owner):
    objective = (
        isinstance(layer, CivilizationSection) or layer is CivilizationLayer.MIGRATION
    )
    mixed = layer in {
        CivilizationLayer.TECHNOLOGY,
        CivilizationLayer.SOCIAL_GROUPS,
        CivilizationLayer.INSTITUTIONS,
    }
    allowed = (
        (
            objective
            and evidence is CivilizationEvidenceClass.OBJECTIVE
            and owner is None
        )
        or (
            not objective
            and evidence is CivilizationEvidenceClass.ANALYTICAL
            and owner is None
        )
        or (
            mixed
            and evidence is CivilizationEvidenceClass.SUBJECTIVE
            and owner is not None
        )
    )
    if allowed:
        assert CivilizationScope(layer, evidence, owner).owner_id == owner
    else:
        with pytest.raises(CivilizationError, match="invalid_civilization_scope"):
            CivilizationScope(layer, evidence, owner)


@pytest.mark.parametrize("tick", [-1, True, 1.0, "1"])
def test_cursor_rejects_coercion_and_negative_ticks(tick):
    with pytest.raises(CivilizationError):
        replace(CURSOR, tick=tick)


def test_prefix_is_not_a_full_boundary_or_a_last_event_resume_pair():
    assert replace(CURSOR, through_sequence=2, boundary_tick=None).boundary_tick is None
    with pytest.raises(CivilizationError):
        replace(CURSOR, through_sequence=2)
    with pytest.raises(CivilizationError):
        replace(CURSOR, boundary_tick=3)


def test_complete_empty_disabled_and_missing_denominators_are_distinct():
    disabled = CivilizationCoverage(CivilizationCoverageState.DISABLED, "capture_off")
    assert disabled != COMPLETE
    assert COMPLETE.observed_count is None
    row = _row_cases()[9]
    empty = replace(
        row, carrier_count=0, carrier_ids=(), eligible_owner_count=0, proportion=None
    )
    assert (
        decode_civilization_value(encode_civilization_value(empty)).proportion is None
    )
    partial = replace(
        row,
        history=replace(
            row.history,
            coverage=CivilizationCoverage(
                CivilizationCoverageState.PARTIAL, "partial_owner_coverage"
            ),
        ),
        unavailable_owner_count=1,
        proportion=None,
    )
    assert partial.carrier_count == 1 and partial.proportion is None
    with pytest.raises(CivilizationError):
        replace(partial, proportion=0.5)
    with pytest.raises(CivilizationError):
        replace(COMPLETE, missing_intervals=(CivilizationWindow(0, 1),))
    with pytest.raises(CivilizationError):
        replace(COMPLETE, expected_count=2, observed_count=1)


def test_nested_values_are_frozen_and_input_aliases_detached():
    ids = ["location"]
    row = CivilizationRegionRow(CONTEXT, "region", 1, ids)
    ids.append("later")
    assert row.location_ids == ("location",)
    with pytest.raises(FrozenInstanceError):
        row.region_id = "changed"


@pytest.mark.parametrize(
    "change",
    [
        {"eligible_occupancy": True},
        {"status": "objective_city"},
        {"first_supported_boundary": 5},
        {"observed_streak": -1},
    ],
)
def test_closed_rows_reject_invalid_types_statuses_and_future_boundaries(change):
    with pytest.raises(CivilizationError):
        replace(_row_cases()[6], **change)


def test_anchors_require_exact_evidence_and_do_not_guess_unplaced_origin():
    assert CivilizationAnchor(CivilizationAnchorKind.NONE).location_id is None
    with pytest.raises(CivilizationError):
        CivilizationAnchor(CivilizationAnchorKind.NONE, "location")
    with pytest.raises(CivilizationError):
        CivilizationAnchor(
            CivilizationAnchorKind.PROJECT, "location", "project", REF, 3
        )
    future = CivilizationSourceRef("scene", "future", 5)
    anchor = CivilizationAnchor(
        CivilizationAnchorKind.PROJECT, "location", "project", future, 5
    )
    with pytest.raises(CivilizationError):
        replace(_row_cases()[6], context=replace(CONTEXT, anchors=(anchor,)))


@pytest.mark.parametrize("marker_type", list(CivilizationMarkerType))
def test_every_marker_round_trips_and_gaps_are_not_transitions(marker_type):
    layer = (
        CivilizationLayer.SETTLEMENTS
        if marker_type.value.startswith("settlement")
        else CivilizationLayer.MIGRATION
        if marker_type.value.startswith("journey")
        else CivilizationLayer.TECHNOLOGY
        if marker_type.value.startswith("technology")
        else CivilizationLayer.INSTITUTIONS
    )
    scope = _history(layer).scope
    marker = CivilizationMarker(
        "marker",
        marker_type,
        4,
        scope.evidence_class,
        None,
        layer,
        "row",
        (CivilizationSourceRef("event", "event", 3),),
        COMPLETE,
    )
    assert decode_civilization_value(encode_civilization_value(marker)) == marker
    with pytest.raises(CivilizationError):
        replace(
            marker,
            coverage=CivilizationCoverage(
                CivilizationCoverageState.PARTIAL, "capture_gap"
            ),
        )
    with pytest.raises(CivilizationError):
        replace(marker, seek_boundary=3)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda raw: raw.replace(b'"region_id":"region"', b'"region_id":"region","x":0'),
        lambda raw: raw.replace(
            b'"region_id":"region"', b'"region_id":"region","region_id":"x"'
        ),
        lambda raw: raw.replace(b'"location_count":1', b'"location_count":true'),
        lambda raw: raw.replace(b'"location_count":1', b'"location_count":NaN'),
        lambda raw: raw.replace(b'"location_count":1', b'"location_count":Infinity'),
        lambda raw: raw.replace(b'"region_id":"region"', b'"region_id":"\\ud800"'),
    ],
)
def test_strict_decode_rejects_unknown_duplicate_coerced_and_nonfinite(mutation):
    with pytest.raises(CivilizationError):
        decode_civilization_value(mutation(encode_civilization_value(_row_cases()[0])))


def test_float_nan_and_unknown_constructor_fields_fail():
    with pytest.raises(CivilizationError):
        replace(_row_cases()[1], fatigue_cost=float("nan"))
    with pytest.raises(TypeError):
        CivilizationRegionRow(CONTEXT, "region", 0, (), x=0)


def test_inline_caps_scalar_totals_and_duplicate_ids():
    row = _row_cases()[0]
    with pytest.raises(CivilizationError):
        replace(row, location_ids=("a", "a"), location_count=2)
    with pytest.raises(CivilizationError):
        replace(row, location_ids=tuple(f"id{i}" for i in range(65)), location_count=65)
    with pytest.raises(CivilizationError):
        replace(row, location_count=1000)
    truncated = replace(
        row, location_count=1000, context=replace(CONTEXT, detail_truncated=True)
    )
    assert truncated.location_count == 1000 and len(truncated.location_ids) == 1


def test_physical_budget_is_reserved_atomically_and_cache_hits_charge_scans():
    budget = CivilizationReadBudget()
    reservation = budget.reserve_file(100, metadata=True)
    with pytest.raises(CivilizationError, match="civilization_storage_corrupt"):
        reservation.require_actual_bytes(101)
    for _ in range(15):
        budget.reserve_file(100)
    before = (budget.physical_files, budget.physical_bytes)
    with pytest.raises(CivilizationError, match="civilization_read_budget"):
        budget.reserve_file(1)
    assert (budget.physical_files, budget.physical_bytes) == before
    budget.reserve_scan(2000)
    with pytest.raises(CivilizationError):
        budget.reserve_scan(1)
    assert budget.scanned_rows == 2000
    assert (budget.physical_files, budget.physical_bytes) == before


def test_physical_byte_metadata_and_row_caps():
    budget = CivilizationReadBudget()
    with pytest.raises(CivilizationError):
        budget.reserve_file(65537, metadata=True)
    for _ in range(12):
        budget.reserve_file(1024 * 1024)
    with pytest.raises(CivilizationError):
        budget.reserve_file(1)
    assert budget.physical_files == 12
    with pytest.raises(CivilizationError):
        CivilizationReadBudget(limit=True)
    with pytest.raises(CivilizationError):
        CivilizationReadBudget(limit=201)


def test_byte_limited_pages_keep_pending_row_and_make_progress():
    row = _row_cases()[0]
    source = tuple(
        replace(row, context=replace(CONTEXT, row_id=f"r{i:04}")) for i in range(4)
    )
    budget = CivilizationReadBudget()
    size = len(encode_civilization_value(source[0])) + 1
    budget.reserve_response(1024 * 1024 - size * 2)
    first = select_civilization_rows(source, budget=budget)
    assert first.rows == source[:2] and first.continuation_after == "r0001"
    second = select_civilization_rows(
        source, budget=CivilizationReadBudget(), after_key=first.continuation_after
    )
    assert second.rows == source[2:] and not second.truncated


def test_sparse_filter_page_can_be_empty_with_progress():
    row = _row_cases()[0]
    source = tuple(
        replace(row, context=replace(CONTEXT, row_id=f"r{i:04}")) for i in range(2001)
    )
    first = select_civilization_rows(
        source, budget=CivilizationReadBudget(), matches=lambda _: False
    )
    assert first.rows == () and first.truncated
    assert first.continuation_after == "r1999"
    second = select_civilization_rows(
        source, budget=CivilizationReadBudget(), after_key=first.continuation_after
    )
    assert second.rows == source[2000:]


def test_single_oversized_row_is_rejected_not_an_endless_continuation():
    refs = tuple(
        CivilizationSourceRef("scene", f"{i}:" + "s" * 500, 4) for i in range(32)
    )
    anchors = tuple(
        CivilizationAnchor(CivilizationAnchorKind.PROJECT, "l" * 512, "p" * 512, ref, 4)
        for ref in refs
    )
    context = replace(CONTEXT, source_refs=refs, anchors=anchors)
    row = replace(_row_cases()[0], context=context)
    with pytest.raises(CivilizationError, match="civilization_row_too_large"):
        select_civilization_rows((row,), budget=CivilizationReadBudget())


def test_duplicate_publication_rows_and_mixed_boundary_are_rejected():
    row = _row_cases()[6]
    boundary = CivilizationBoundaryPublication(CURSOR, (row.history.scope,), (row,), ())
    with pytest.raises(CivilizationError):
        replace(boundary, rows=(row, row))
    with pytest.raises(CivilizationError):
        replace(boundary, cursor=replace(CURSOR, tick=5, boundary_tick=5))
    assert not hasattr(CivilizationReadPort, "publish_boundary")


def test_complete_empty_page_round_trip_has_no_new_legacy_fields():
    scope = CivilizationScope(
        CivilizationSection.REGIONS, CivilizationEvidenceClass.OBJECTIVE
    )
    page = CivilizationPage(CURSOR, CURSOR, scope, COMPLETE, (), None, False, 4)
    assert decode_civilization_value(encode_civilization_value(page)) == page
    with pytest.raises(CivilizationError):
        replace(page, truncated=True)


def test_digest_dag_is_child_first_and_contains_no_self_or_parent_digest():
    child = encode_civilization_value(_row_cases()[0])
    assert (
        civilization_digest(b"abc\n")
        == "edeaaff3f1774ad2888673770c6d64097e391bc362d7d6fb34982ddf0efd18cb"
    )
    child_kind = "row_shard"
    digests = []
    for kind in ("boundary_manifest", "catalogue_page", "catalogue_index", "commit"):
        digest = civilization_digest(child)
        digests.append(digest)
        ref = CivilizationArtifactRef(
            child_kind, "children/file.json", digest, len(child), 1, "row", "row"
        )
        manifest = CivilizationHashManifest(
            kind,
            "run",
            "world",
            "publication",
            "config",
            "source",
            "policy",
            4 if kind == "boundary_manifest" else None,
            (ref,),
        )
        child = encode_civilization_value(manifest)
        decoded = json.loads(child)
        assert "digest" not in decoded and "root_digest" not in decoded
        child_kind = kind
    assert len(set(digests)) == 4
    # Independent fixed result pins the complete child-to-parent canonical DAG.
    assert (
        civilization_digest(child)
        == "4320c8f12dbb5db8adbc920cbb51f0b66b248f208891379e3986e2487d70db9c"
    )
    with pytest.raises(CivilizationError):
        replace(manifest, children=(replace(ref, kind="row_shard"),))


def _project(scene, section="locations", *, entity_id=None):
    from simulation.observer_civilization import project_civilization_map

    cursor = CivilizationCursor(
        scene.run_id, scene.world_id, scene.tick, None, scene.tick, scene.revision
    )
    return project_civilization_map(
        scene, cursor=cursor, section=section, entity_id=entity_id
    )


def _physical_scene():
    from agents.models import AgentId
    from simulation.observer_facts import ObjectiveScene
    from simulation.registrations import AgentRegistration
    from tests.physical_helpers import dead_body
    from tests.simulation_helpers import alive_body, make_location, make_weather

    return ObjectiveScene(
        "run-physical",
        "world-physical",
        4,
        4,
        (make_location("loc-1"), make_location("loc-2")),
        (
            alive_body("body-a"),
            alive_body("body-b", location_id="loc-2"),
            dead_body("body-dead", location_id="loc-1"),
        ),
        (),
        (),
        (make_weather("loc-1"), make_weather("loc-2")),
        (AgentRegistration(AgentId("not-the-body-id"), EntityId("body-a")),),
    )


def test_physical_population_uses_body_bindings_and_lifecycle_off_is_unknown():
    scene = _physical_scene()
    rows = _project(scene).rows
    assert [
        (r.living_body_count, r.dead_body_count, r.registered_agent_count) for r in rows
    ] == [(1, 1, 1), (1, 0, 0)]
    assert all(r.lifecycle_living_count is None for r in rows)
    assert all(r.region_id is None for r in rows)
    empty = replace(scene, locations=(), bodies=(), weather=(), registrations=())
    assert _project(empty).rows == ()
    assert _project(empty).coverage.state is CivilizationCoverageState.COMPLETE
    assert _project(scene, "regions").coverage.reason == "channel_absent"


def test_lifecycle_counts_use_exact_owner_body_binding_not_equal_ids():
    from tests.unit.test_observer_demographics import _record

    scene = _physical_scene()
    scene = replace(scene, lifecycle_records=(_record("body-a", "not-the-body-id"),))
    assert _project(scene).rows[0].lifecycle_living_count == 1
    assert _project(scene).rows[0].lifecycle_dead_count == 0
    missing = replace(scene, lifecycle_records=())
    assert _project(missing).rows[0].lifecycle_living_count is None
    with pytest.raises(CivilizationError):
        _project(replace(scene, lifecycle_records=(_record("body-a", "wrong-owner"),)))


def test_region_assignments_do_not_invent_adjacency_or_assign_unassigned_locations():
    from world.regions import (
        CognitionMode,
        LocationRegion,
        RegionDefinition,
        RegionsMigrationSpec,
    )

    scene = _physical_scene()
    spec = RegionsMigrationSpec(
        (RegionDefinition("region", "Region"),),
        (LocationRegion(EntityId("loc-1"), "region"),),
        (),
        1,
        1,
        1,
        1,
        CognitionMode.DISABLED,
    )
    scene = replace(scene, regions_migration=spec)
    assert [row.region_id for row in _project(scene).rows] == ["region", None]
    assert _project(scene, "routes").rows == ()
    assert (
        _project(scene, "routes").coverage.state is CivilizationCoverageState.COMPLETE
    )
    assert _project(scene, "regions").rows[0].location_ids == ("loc-1",)


def test_physical_scene_cursor_and_duplicate_id_mismatches_fail_closed():
    from simulation.observer_civilization import project_civilization_map

    scene = _physical_scene()
    with pytest.raises(CivilizationError):
        project_civilization_map(scene, cursor=CURSOR, section="locations")
    with pytest.raises(CivilizationError):
        _project(replace(scene, locations=scene.locations + scene.locations[:1]))
    with pytest.raises(CivilizationError):
        _project(scene, "institutions")


def test_regional_routes_population_arrival_and_checkpoint_projection_parity():
    from simulation.engine import WorldEngine
    from simulation.observer_facts import scene_from_facts, scene_from_snapshot
    from tests.unit.test_regional_travel_checkpoint import _snapshot
    from tests.unit.test_regional_travel_lifecycle import _engine, _move

    engine = _engine(destination_capacity=2, blocker=False)
    _move(engine)
    pending = scene_from_facts(engine.detached_objective_facts())
    assert _project(pending).rows[0].active_journey_count == 1
    assert [r.living_body_count for r in _project(pending).rows] == [1, 0]
    assert len(_project(pending, "routes").rows) == 1
    route = _project(pending, "routes").rows[0]
    assert (
        route.endpoint_a,
        route.endpoint_b,
        route.duration_ticks,
        route.fatigue_cost,
    ) == ("loc-1", "loc-2", 2, 3.0)
    assert {r.region_label for r in _project(pending, "regions").rows} == {
        "East",
        "West",
    }
    engine.observe()
    engine.resolve_tick(())
    arrived = scene_from_facts(engine.detached_objective_facts())
    assert [r.living_body_count for r in _project(arrived).rows] == [0, 1]
    assert all(r.active_journey_count == 0 for r in _project(arrived).rows)
    snapshot = _snapshot()
    restored = scene_from_facts(
        WorldEngine.restore_from_snapshot(snapshot).detached_objective_facts()
    )
    for section in CivilizationSection:
        assert _project(restored, section) == _project(
            scene_from_snapshot(snapshot), section
        )


def test_projects_public_acts_structure_link_and_contribution_facts_are_distinct():
    from world.collective_projects import (
        CollectiveProject,
        ProjectContribution,
        PublicGoodAct,
        PublicGoodActKind,
        PublicGoodActSource,
    )
    from world.production import Structure, StructureKind

    scene = _physical_scene()
    project = CollectiveProject(
        EntityId("project"),
        EntityId("loc-1"),
        CollectiveProjectKind.WELL,
        CollectiveProjectStatus.COMPLETED,
        3,
        3,
        2,
        2,
        0,
        3,
        0,
        (
            ProjectContribution(EntityId("body-a"), 1, True, 1),
            ProjectContribution(EntityId("body-b"), 2, False, 0),
        ),
        linked_structure_id=EntityId("well"),
        public_acts=tuple(
            PublicGoodAct(EntityId("body-a"), 3, kind, PublicGoodActSource.COMMAND)
            for kind in PublicGoodActKind
        ),
    )
    scene = replace(
        scene,
        collective_projects=(project,),
        structures=(
            Structure(EntityId("well"), EntityId("loc-1"), StructureKind.WELL, 1.0, 0),
        ),
    )
    row = _project(scene, "projects").rows[0]
    assert row.accepted_contribution_count == 1
    assert row.linked_structure_kind is StructureKind.WELL
    assert row.public_acts == CivilizationPublicActs(1, 1, 1, 1)
    assert row.labor_progress == row.labor_required == 3
    assert _project(scene).rows[0].project_count == 1
    assert _project(scene).rows[0].structure_count == 1
    destroyed = replace(scene, structures=())
    assert _project(destroyed, "projects").rows[0].linked_structure_kind is None
    assert _project(scene, "projects", entity_id="project").rows == (row,)
    assert not _project(scene, "projects", entity_id="missing").rows


def test_repository_record_placement_custody_and_private_content_do_not_mix(caplog):
    from world.artifacts import ArtifactContent, InformationArtifact, RecordIntegrity
    from world.repositories import KnowledgeRepository

    scene = _physical_scene()
    record = InformationArtifact(
        EntityId("record"),
        ArtifactKind.NOTE,
        EntityId("body-a"),
        1,
        ArtifactContent(("canary_secret",), ()),
        holder_id=EntityId("body-b"),
        integrity=RecordIntegrity.DAMAGED,
    )
    repository = KnowledgeRepository(
        EntityId("repo"),
        EntityId("loc-1"),
        (EntityId("body-a"),),
        1,
        RepositoryAccessMode.OPEN,
        member_artifact_ids=(EntityId("record"),),
    )
    scene = replace(scene, artifacts=(record,), repositories=(repository,))
    caplog.set_level("DEBUG")
    row = _project(scene, "records").rows[0]
    assert row.location_id == "loc-2" and row.integrity is RecordIntegrity.DAMAGED
    assert row.custodian_repository_id is None
    assert _project(scene, "repositories").rows[0].member_count == 1
    assert b"canary_secret" not in encode_civilization_value(row)
    assert "canary_secret" not in caplog.text
    missing_holder = replace(
        scene, artifacts=(replace(record, holder_id=EntityId("absent")),)
    )
    projection = _project(missing_holder, "records")
    assert projection.coverage.reason == "unresolved_anchor"
    assert projection.rows[0].location_id is None
    assert projection.rows[0].context.anchors[0].kind is CivilizationAnchorKind.NONE
    deposited = replace(
        record,
        holder_id=None,
        location_id=EntityId("loc-1"),
        custodian_repository_id=EntityId("repo"),
    )
    row = _project(replace(scene, artifacts=(deposited,)), "records").rows[0]
    assert row.location_id == "loc-1" and row.custodian_repository_id == "repo"
