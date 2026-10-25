"""Pure physical civilization projection at one detached objective cursor."""

from __future__ import annotations

import logging
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, replace

from simulation.civilization_models import (
    CivilizationAnchor,
    CivilizationAnchorKind,
    CivilizationCoverage,
    CivilizationCoverageState,
    CivilizationCursor,
    CivilizationError,
    CivilizationSection,
    CivilizationSourceRef,
)
from simulation.civilization_rows import (
    CivilizationContribution,
    CivilizationLocationRow,
    CivilizationMapRow,
    CivilizationProjectRow,
    CivilizationPublicActs,
    CivilizationRecordRow,
    CivilizationRegionRow,
    CivilizationRepositoryRow,
    CivilizationRouteRow,
    CivilizationRowContext,
)
from simulation.observer_facts import ObjectiveScene
from world.collective_projects import CollectiveProject, catalog_row
from world.models import LifeStatus

__all__ = ["CivilizationMapProjection", "project_civilization_map"]

_LOG = logging.getLogger(__name__)


def _route_id(endpoint_a: str, endpoint_b: str) -> str:
    return f"{len(endpoint_a)}:{endpoint_a}:{endpoint_b}"


@dataclass(frozen=True, slots=True)
class CivilizationMapProjection:
    cursor: CivilizationCursor
    section: CivilizationSection
    coverage: CivilizationCoverage
    rows: tuple[CivilizationMapRow, ...]
    source_has_more: bool = False


def _context(
    scene: ObjectiveScene,
    section: CivilizationSection,
    entity_id: str,
    *,
    location_id: str | None = None,
    kind: CivilizationAnchorKind = CivilizationAnchorKind.LOCATION,
    detail_truncated: bool = False,
) -> CivilizationRowContext:
    row_id = f"{section.value}:{entity_id}"
    ref = CivilizationSourceRef("scene", row_id, scene.tick)
    anchor = (
        CivilizationAnchor(CivilizationAnchorKind.NONE)
        if location_id is None
        else CivilizationAnchor(kind, location_id, entity_id, ref, scene.tick)
    )
    return CivilizationRowContext(row_id, (ref,), (anchor,), detail_truncated)


def _validate_scene(scene: ObjectiveScene, cursor: CivilizationCursor) -> None:
    if type(scene) is not ObjectiveScene or type(cursor) is not CivilizationCursor:
        raise CivilizationError()
    if (scene.run_id, scene.world_id, scene.tick, scene.revision) != (
        cursor.run_id,
        cursor.world_id,
        cursor.tick,
        cursor.revision,
    ):
        raise CivilizationError()
    location_ids = {row.entity_id for row in scene.locations}
    body_ids = {row.entity_id for row in scene.bodies}
    bindings = {row.entity_id: row.agent_id.value for row in scene.registrations}
    if (
        len(location_ids) != len(scene.locations)
        or len(body_ids) != len(scene.bodies)
        or len(bindings) != len(scene.registrations)
        or len(set(bindings.values())) != len(bindings)
        or not set(bindings) <= body_ids
        or any(body.location_id not in location_ids for body in scene.bodies)
    ):
        raise CivilizationError()
    if scene.lifecycle_records is not None:
        if len({r.body_id for r in scene.lifecycle_records}) != len(
            scene.lifecycle_records
        ) or any(
            bindings.get(r.body_id) != r.agent_id for r in scene.lifecycle_records
        ):
            raise CivilizationError()
    for values, id_field in (
        (scene.structures, "entity_id"),
        (scene.repositories, "repository_id"),
        (scene.collective_projects, "project_id"),
    ):
        if len({getattr(row, id_field) for row in values}) != len(values) or any(
            row.location_id not in location_ids for row in values
        ):
            raise CivilizationError()
    if len({r.artifact_id for r in scene.artifacts}) != len(scene.artifacts):
        raise CivilizationError()
    for journey in scene.journeys:
        if (
            journey.origin_location_id not in location_ids
            or journey.destination_location_id not in location_ids
            or any(
                participant not in body_ids
                for participant in journey.participant_body_ids
            )
        ):
            raise CivilizationError()
    if scene.regions_migration is not None:
        try:
            scene.regions_migration.validate_topology(
                {row.entity_id: row.adjacent for row in scene.locations}
            )
        except (TypeError, ValueError):
            raise CivilizationError() from None


def _regional_rows(
    scene: ObjectiveScene,
    section: CivilizationSection,
    selected_ids: frozenset[str],
) -> tuple[CivilizationMapRow, ...]:
    spec = scene.regions_migration
    if spec is None:
        return ()
    assignments = {
        row.location_id.value: row.region_id for row in spec.location_regions
    }
    if section is CivilizationSection.REGIONS:
        rows: list[CivilizationMapRow] = []
        for region in spec.regions:
            if region.region_id not in selected_ids:
                continue
            locations = tuple(
                sorted(
                    key
                    for key, value in assignments.items()
                    if value == region.region_id
                )
            )
            rows.append(
                CivilizationRegionRow(
                    _context(
                        scene,
                        section,
                        region.region_id,
                        detail_truncated=len(locations) > 64,
                    ),
                    region.region_id,
                    len(locations),
                    locations[:64],
                    region.label,
                )
            )
        return tuple(rows)
    return tuple(
        CivilizationRouteRow(
            _context(
                scene,
                section,
                _route_id(route.endpoint_a.value, route.endpoint_b.value),
            ),
            _route_id(route.endpoint_a.value, route.endpoint_b.value),
            route.endpoint_a.value,
            route.endpoint_b.value,
            assignments.get(route.endpoint_a.value),
            assignments.get(route.endpoint_b.value),
            route.duration_ticks,
            route.fatigue_cost,
        )
        for route in spec.routes
        if _route_id(route.endpoint_a.value, route.endpoint_b.value) in selected_ids
    )


def _location_rows(
    scene: ObjectiveScene, selected_ids: frozenset[str]
) -> tuple[CivilizationMapRow, ...]:
    living = Counter(
        b.location_id.value for b in scene.bodies if b.life_status is LifeStatus.ALIVE
    )
    dead = Counter(
        b.location_id.value for b in scene.bodies if b.life_status is LifeStatus.DEAD
    )
    bodies = {body.entity_id: body for body in scene.bodies}
    registered = Counter(
        bodies[r.entity_id].location_id.value for r in scene.registrations
    )
    lifecycle_live: Counter[str] = Counter()
    lifecycle_dead: Counter[str] = Counter()
    lifecycle_ids = {row.body_id for row in scene.lifecycle_records or ()}
    incomplete_lifecycle_locations = {
        bodies[row.entity_id].location_id.value
        for row in scene.registrations
        if row.entity_id not in lifecycle_ids
    }
    for record in scene.lifecycle_records or ():
        body = bodies[record.body_id]
        target = (
            lifecycle_live if body.life_status is LifeStatus.ALIVE else lifecycle_dead
        )
        target[body.location_id.value] += 1
    structures = Counter(r.location_id.value for r in scene.structures)
    repositories = Counter(r.location_id.value for r in scene.repositories)
    projects = Counter(r.location_id.value for r in scene.collective_projects)
    assignments = (
        {}
        if scene.regions_migration is None
        else {
            r.location_id.value: r.region_id
            for r in scene.regions_migration.location_regions
        }
    )
    journeys: dict[str, list[str]] = {}
    for journey in scene.journeys:
        journeys.setdefault(journey.origin_location_id.value, []).append(
            journey.journey_id
        )
    result: list[CivilizationMapRow] = []
    for location in scene.locations:
        key = location.entity_id.value
        if key not in selected_ids:
            continue
        active = tuple(sorted(journeys.get(key, ())))
        result.append(
            CivilizationLocationRow(
                _context(
                    scene,
                    CivilizationSection.LOCATIONS,
                    key,
                    location_id=key,
                    detail_truncated=len(active) > 64,
                ),
                key,
                assignments.get(key),
                living[key],
                dead[key],
                registered[key],
                None
                if scene.lifecycle_records is None
                or key in incomplete_lifecycle_locations
                else lifecycle_live[key],
                None
                if scene.lifecycle_records is None
                or key in incomplete_lifecycle_locations
                else lifecycle_dead[key],
                structures[key],
                repositories[key],
                projects[key],
                len(active),
                active[:64],
            )
        )
    return tuple(result)


def _project_row(
    scene: ObjectiveScene, project: CollectiveProject
) -> CivilizationProjectRow:
    contributions = tuple(
        CivilizationContribution(
            row.actor_id.value,
            row.tick,
            row.labor_delta,
            int(row.item_id is not None),
            None if row.item_id is None else row.item_id.value,
        )
        for row in project.contributions
        if row.accepted
    )
    acts = Counter(row.act.value for row in project.public_acts)
    structure = next(
        (r for r in scene.structures if r.entity_id == project.linked_structure_id),
        None,
    )
    return CivilizationProjectRow(
        _context(
            scene,
            CivilizationSection.PROJECTS,
            project.project_id.value,
            location_id=project.location_id.value,
            kind=CivilizationAnchorKind.PROJECT,
            detail_truncated=len(contributions) > 64,
        ),
        project.project_id.value,
        project.location_id.value,
        project.kind,
        project.status,
        project.labor_done,
        project.labor_required,
        project.materials_done,
        project.materials_required,
        catalog_row(project.kind).material_kind,
        len(contributions),
        contributions[:64],
        None
        if project.linked_structure_id is None
        else project.linked_structure_id.value,
        None if structure is None else structure.kind,
        project.shortage_count,
        CivilizationPublicActs(
            acts["benefit"], acts["draw"], acts["maintain"], acts["oppose"]
        ),
    )


def _repository_rows(scene: ObjectiveScene) -> tuple[CivilizationMapRow, ...]:
    return tuple(
        CivilizationRepositoryRow(
            _context(
                scene,
                CivilizationSection.REPOSITORIES,
                repo.repository_id.value,
                location_id=repo.location_id.value,
                kind=CivilizationAnchorKind.REPOSITORY,
                detail_truncated=len(repo.member_artifact_ids) > 64,
            ),
            repo.repository_id.value,
            repo.location_id.value,
            repo.status,
            repo.access_mode,
            len(repo.member_artifact_ids),
            tuple(sorted(r.value for r in repo.member_artifact_ids))[:64],
            None if repo.structure_id is None else repo.structure_id.value,
            repo.established_tick,
            repo.last_maintained_tick,
            repo.neglect_streak,
        )
        for repo in scene.repositories
    )


def _record_rows(scene: ObjectiveScene) -> tuple[tuple[CivilizationMapRow, ...], bool]:
    holders = {body.entity_id: body.location_id.value for body in scene.bodies}
    result: list[CivilizationMapRow] = []
    unresolved = False
    for record in scene.artifacts:
        location = (
            holders.get(record.holder_id)
            if record.holder_id is not None
            else None
            if record.location_id is None
            else record.location_id.value
        )
        if record.holder_id is not None and location is None:
            unresolved = True
        result.append(
            CivilizationRecordRow(
                _context(
                    scene,
                    CivilizationSection.RECORDS,
                    record.artifact_id.value,
                    location_id=location,
                ),
                record.artifact_id.value,
                record.kind,
                record.record_genre,
                record.integrity,
                location,
                None if record.holder_id is None else record.holder_id.value,
                None
                if record.custodian_repository_id is None
                else record.custodian_repository_id.value,
                None
                if record.parent_artifact_id is None
                else record.parent_artifact_id.value,
                None
                if record.source_artifact_id is None
                else record.source_artifact_id.value,
                record.created_tick,
                record.copy_generation,
                record.annotation_revisions,
                record.lost_mark_count,
            )
        )
    return tuple(result), unresolved


def project_civilization_map(
    scene: ObjectiveScene,
    *,
    cursor: CivilizationCursor,
    section: str,
    entity_id: str | None = None,
    after_key: str | None = None,
    source_limit: int | None = None,
) -> CivilizationMapProjection:
    """No live engine, coordinates, subjective labels or historical head joins."""
    _validate_scene(scene, cursor)
    try:
        selected = CivilizationSection(section)
    except (TypeError, ValueError):
        raise CivilizationError() from None
    source_ids = _source_ids(scene, selected)
    if entity_id is not None:
        source_ids = tuple(key for key in source_ids if key == entity_id)
    source_count = len(source_ids)
    if source_limit is not None:
        if type(source_limit) is not int or not 1 <= source_limit <= 2000:
            raise CivilizationError()
    keys = tuple(selected.value + ":" + key for key in source_ids)
    start = 0 if after_key is None else bisect_right(keys, after_key)
    stop = len(keys) if source_limit is None else min(len(keys), start + source_limit)
    selected_ids = frozenset(source_ids[start:stop])
    # Raw identities are indexed first; at most source_limit detached rows are
    # materialized. Direct selection never walks preceding presentation pages.
    unresolved = False
    if selected is CivilizationSection.PROJECTS:
        scene = replace(
            scene,
            collective_projects=tuple(
                r
                for r in scene.collective_projects
                if r.project_id.value in selected_ids
            ),
        )
    elif selected is CivilizationSection.REPOSITORIES:
        scene = replace(
            scene,
            repositories=tuple(
                r for r in scene.repositories if r.repository_id.value in selected_ids
            ),
        )
    elif selected is CivilizationSection.RECORDS:
        holders = {body.entity_id for body in scene.bodies}
        unresolved = any(
            r.holder_id is not None and r.holder_id not in holders
            for r in scene.artifacts
        )
        scene = replace(
            scene,
            artifacts=tuple(
                r for r in scene.artifacts if r.artifact_id.value in selected_ids
            ),
        )
    if selected in (CivilizationSection.REGIONS, CivilizationSection.ROUTES):
        rows = _regional_rows(scene, selected, selected_ids)
    elif selected is CivilizationSection.LOCATIONS:
        rows = _location_rows(scene, selected_ids)
    elif selected is CivilizationSection.PROJECTS:
        rows = tuple(_project_row(scene, row) for row in scene.collective_projects)
    elif selected is CivilizationSection.REPOSITORIES:
        rows = _repository_rows(scene)
    else:
        rows, page_unresolved = _record_rows(scene)
        unresolved = unresolved or page_unresolved
    if entity_id is not None and selected in (
        CivilizationSection.REGIONS,
        CivilizationSection.ROUTES,
        CivilizationSection.LOCATIONS,
    ):
        rows = tuple(
            r for r in rows if r.context.row_id == f"{selected.value}:{entity_id}"
        )
    coverage = CivilizationCoverage(
        CivilizationCoverageState.COMPLETE,
        observed_count=source_count,
        expected_count=source_count,
    )
    if (
        selected in (CivilizationSection.REGIONS, CivilizationSection.ROUTES)
        and scene.regions_migration is None
    ):
        coverage = CivilizationCoverage(
            CivilizationCoverageState.UNAVAILABLE, "channel_absent"
        )
    elif unresolved:
        coverage = CivilizationCoverage(
            CivilizationCoverageState.PARTIAL,
            "unresolved_anchor",
            observed_count=source_count,
        )
        _LOG.warning("civilization_projection_partial reason_code=unresolved_anchor")
    result = CivilizationMapProjection(
        cursor,
        selected,
        coverage,
        tuple(sorted(rows, key=lambda row: row.context.row_id)),
        stop < len(keys),
    )
    _LOG.debug(
        "civilization_projected run_id=%s tick=%s section=%s row_count=%s state=%s",
        cursor.run_id,
        cursor.tick,
        selected.value,
        len(rows),
        coverage.state.value,
    )
    return result


def _source_ids(scene: ObjectiveScene, section: CivilizationSection) -> tuple[str, ...]:
    """Index raw identities without materializing/decoding presentation rows."""
    if section is CivilizationSection.LOCATIONS:
        ids = (row.entity_id.value for row in scene.locations)
    elif section is CivilizationSection.PROJECTS:
        ids = (row.project_id.value for row in scene.collective_projects)
    elif section is CivilizationSection.REPOSITORIES:
        ids = (row.repository_id.value for row in scene.repositories)
    elif section is CivilizationSection.RECORDS:
        ids = (row.artifact_id.value for row in scene.artifacts)
    elif scene.regions_migration is None:
        return ()
    elif section is CivilizationSection.REGIONS:
        ids = (row.region_id for row in scene.regions_migration.regions)
    else:
        ids = (
            _route_id(row.endpoint_a.value, row.endpoint_b.value)
            for row in scene.regions_migration.routes
        )
    return tuple(sorted(ids))
