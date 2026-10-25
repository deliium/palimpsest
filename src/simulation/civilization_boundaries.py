"""Detached physical boundary inputs and failure-isolated capture orchestration.

Owner inventories/grounding are deliberately unavailable until their dedicated
whitelisted export is implemented. This is not a subjective restart checkpoint.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Protocol

from simulation.civilization_capture import (
    CivilizationEventBatch,
    CivilizationGroundingObservation,
    CivilizationOwnerInventory,
    InstitutionGroundingWitness,
    civilization_events_from_result,
    institution_grounding_witnesses,
    project_grounding_observation,
    unavailable_civilization_events,
)
from simulation.civilization_codec import encode_civilization_value
from simulation.civilization_models import (
    CivilizationCoverage,
    CivilizationCoverageState,
    CivilizationCursor,
    CivilizationError,
    CivilizationSection,
    _count,
    _id,
)
from simulation.civilization_ports import CivilizationBoundarySink
from simulation.civilization_rows import CivilizationMapRow, _map_section
from simulation.lifecycle import TickResult
from simulation.observer_civilization import project_civilization_map
from simulation.observer_facts import ObjectiveFacts, ObjectiveScene, scene_from_facts
from world.models import LifeStatus
from world.production import StructureKind

__all__ = [
    "CivilizationBodyBinding",
    "CivilizationBoundaryInput",
    "CivilizationCaptureCoordinator",
    "CivilizationCaptureSink",
    "CivilizationJourneyFact",
    "CivilizationRunnerCaptureStatus",
    "CivilizationSectionCoverage",
    "CivilizationStructureFact",
    "civilization_boundary_bytes",
    "civilization_boundary_rows",
    "project_civilization_boundary",
]

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CivilizationBodyBinding:
    body_id: str
    owner_id: str | None
    location_id: str
    living: bool

    def __post_init__(self) -> None:
        _id(self.body_id)
        _id(self.location_id)
        if self.owner_id is not None:
            _id(self.owner_id)
        if type(self.living) is not bool:
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationStructureFact:
    structure_id: str
    location_id: str
    kind: StructureKind
    integrity: float

    def __post_init__(self) -> None:
        _id(self.structure_id)
        _id(self.location_id)
        if (
            type(self.kind) is not StructureKind
            or type(self.integrity) not in (int, float)
            or not math.isfinite(self.integrity)
            or not 0 <= self.integrity <= 1
        ):
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationSectionCoverage:
    section: CivilizationSection
    coverage: CivilizationCoverage

    def __post_init__(self) -> None:
        if (
            type(self.section) is not CivilizationSection
            or type(self.coverage) is not CivilizationCoverage
        ):
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationJourneyFact:
    journey_id: str
    participant_body_ids: tuple[str, ...]
    origin_location_id: str
    destination_location_id: str
    origin_region_id: str | None
    destination_region_id: str | None
    start_tick: int
    due_tick: int
    arrival_wait_deadline_tick: int
    fatigue_cost: float

    def __post_init__(self) -> None:
        for value in (
            self.journey_id,
            self.origin_location_id,
            self.destination_location_id,
        ):
            _id(value)
        for region_id in (self.origin_region_id, self.destination_region_id):
            if region_id is not None:
                _id(region_id)
        participants = tuple(self.participant_body_ids)
        if not participants or len(set(participants)) != len(participants):
            raise CivilizationError()
        for value in participants:
            _id(value)
        object.__setattr__(self, "participant_body_ids", participants)
        for tick in (self.start_tick, self.due_tick, self.arrival_wait_deadline_tick):
            _count(tick)
        if (
            not self.start_tick <= self.due_tick <= self.arrival_wait_deadline_tick
            or type(self.fatigue_cost) not in (int, float)
            or not math.isfinite(self.fatigue_cost)
            or self.fatigue_cost < 0
        ):
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationBoundaryInput:
    cursor: CivilizationCursor
    map_rows: tuple[CivilizationMapRow, ...]
    section_coverage: tuple[CivilizationSectionCoverage, ...]
    bodies: tuple[CivilizationBodyBinding, ...]
    structures: tuple[CivilizationStructureFact, ...]
    journeys: tuple[CivilizationJourneyFact, ...]
    private_coverage: CivilizationCoverage
    grounding_coverage: CivilizationCoverage
    owner_inventories: tuple[CivilizationOwnerInventory, ...] = ()
    grounding_witnesses: tuple[InstitutionGroundingWitness, ...] = ()

    def __post_init__(self) -> None:
        if (
            type(self.cursor) is not CivilizationCursor
            or self.cursor.boundary_tick is None
        ):
            raise CivilizationError()
        for name in (
            "map_rows",
            "section_coverage",
            "bodies",
            "structures",
            "journeys",
            "owner_inventories",
            "grounding_witnesses",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        for name, expected in (
            ("section_coverage", CivilizationSectionCoverage),
            ("bodies", CivilizationBodyBinding),
            ("structures", CivilizationStructureFact),
            ("journeys", CivilizationJourneyFact),
            ("owner_inventories", CivilizationOwnerInventory),
            ("grounding_witnesses", InstitutionGroundingWitness),
        ):
            if any(type(value) is not expected for value in getattr(self, name)):
                raise CivilizationError()
        if len({row.section for row in self.section_coverage}) != len(
            self.section_coverage
        ) or {row.section for row in self.section_coverage} != set(CivilizationSection):
            raise CivilizationError()
        keys = []
        for row in self.map_rows:
            _map_section(row)
            keys.append(row.context.row_id)
            if any(ref.tick != self.cursor.tick for ref in row.context.source_refs):
                raise CivilizationError()
        if keys != sorted(set(keys)):
            raise CivilizationError()
        if len({body.body_id for body in self.bodies}) != len(self.bodies) or len(
            {row.structure_id for row in self.structures}
        ) != len(self.structures):
            raise CivilizationError()
        # Missing private state must never be interpreted as complete-empty.
        for coverage in (self.private_coverage, self.grounding_coverage):
            if (
                type(coverage) is not CivilizationCoverage
                or coverage.state is CivilizationCoverageState.DISABLED
            ):
                raise CivilizationError()
        if (
            not self.owner_inventories
            and self.private_coverage.state
            is not CivilizationCoverageState.UNAVAILABLE
        ):
            raise CivilizationError()
        if (
            self.private_coverage.state is not CivilizationCoverageState.UNAVAILABLE
            and any(
                row.owner_id
                not in {inventory.owner_id for inventory in self.owner_inventories}
                for row in self.grounding_witnesses
            )
        ):
            raise CivilizationError()
        for witness in self.grounding_witnesses:
            if witness.evidence_tick >= (self.cursor.boundary_tick or 0):
                raise CivilizationError()


def project_civilization_boundary(
    scene: ObjectiveScene,
    *,
    owner_inventories: tuple[CivilizationOwnerInventory, ...] = (),
    grounding_observations: tuple[CivilizationGroundingObservation, ...] = (),
    grounding_observations_complete: bool = False,
) -> CivilizationBoundaryInput:
    cursor = CivilizationCursor(
        scene.run_id, scene.world_id, scene.tick, None, scene.tick, scene.revision
    )
    projections = tuple(
        project_civilization_map(scene, cursor=cursor, section=section.value)
        for section in CivilizationSection
    )
    bindings = {row.entity_id: row.agent_id.value for row in scene.registrations}
    owner_inventories = tuple(owner_inventories)
    grounding_observations = tuple(grounding_observations)
    private_coverage = (
        CivilizationCoverage(CivilizationCoverageState.COMPLETE)
        if owner_inventories
        else CivilizationCoverage(
            CivilizationCoverageState.UNAVAILABLE, "capture_gap"
        )
    )
    witnesses, grounding_coverage = institution_grounding_witnesses(
        owner_inventories,
        grounding_observations,
        complete=grounding_observations_complete,
    )
    return CivilizationBoundaryInput(
        cursor,
        tuple(
            sorted(
                (row for projection in projections for row in projection.rows),
                key=lambda row: row.context.row_id,
            )
        ),
        tuple(
            CivilizationSectionCoverage(projection.section, projection.coverage)
            for projection in projections
        ),
        tuple(
            CivilizationBodyBinding(
                body.entity_id.value,
                bindings.get(body.entity_id),
                body.location_id.value,
                body.life_status is LifeStatus.ALIVE,
            )
            for body in sorted(scene.bodies, key=lambda body: body.entity_id.value)
        ),
        tuple(
            CivilizationStructureFact(
                row.entity_id.value, row.location_id.value, row.kind, row.integrity
            )
            for row in sorted(scene.structures, key=lambda row: row.entity_id.value)
        ),
        tuple(
            CivilizationJourneyFact(
                row.journey_id,
                tuple(body.value for body in row.participant_body_ids),
                row.origin_location_id.value,
                row.destination_location_id.value,
                row.origin_region_id,
                row.destination_region_id,
                row.start_tick,
                row.due_tick,
                row.arrival_wait_deadline_tick,
                row.charged_fatigue_cost,
            )
            for row in sorted(scene.journeys, key=lambda row: row.journey_id)
        ),
        private_coverage,
        grounding_coverage,
        owner_inventories,
        witnesses,
    )


def civilization_boundary_rows(boundary: CivilizationBoundaryInput) -> int:
    """Count nested metadata records, not just the outer batch."""
    return (
        1
        + len(boundary.map_rows)
        + len(boundary.bodies)
        + len(boundary.structures)
        + len(boundary.section_coverage)
        + len(boundary.journeys)
        + sum(
            len(row.context.source_refs)
            + len(row.context.anchors)
            + len(getattr(row, "accepted_contributions", ()))
            for row in boundary.map_rows
        )
        + len(boundary.owner_inventories)
        + len(boundary.grounding_witnesses)
        + sum(
            len(inventory.channels)
            + len(inventory.cultural_traits)
            + len(inventory.terminology)
            + len(inventory.narratives)
            + len(inventory.knowledge)
            + len(inventory.groups)
            + len(inventory.concepts)
            + len(inventory.offices)
            + len(inventory.decay_samples)
            + sum(len(concept.evidence) for concept in inventory.concepts)
            for inventory in boundary.owner_inventories
        )
    )


def civilization_boundary_bytes(boundary: CivilizationBoundaryInput) -> bytes:
    if type(boundary) is not CivilizationBoundaryInput:
        raise CivilizationError()
    # Individually validate the exact row byte cap before accepting a boundary.
    for row in boundary.map_rows:
        encode_civilization_value(row)
    try:
        encoded = (
            json.dumps(
                asdict(boundary),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise CivilizationError() from None
    if len(encoded) > 64 * 1024 * 1024:
        raise CivilizationError("civilization_row_too_large")
    return encoded


class CivilizationCaptureSink(
    CivilizationBoundarySink[CivilizationBoundaryInput], Protocol
):
    def wants_events(self) -> bool: ...
    def wants_boundary(self, boundary_tick: int) -> bool: ...
    def capture_events(self, batch: CivilizationEventBatch) -> bool: ...


@dataclass(frozen=True, slots=True)
class CivilizationRunnerCaptureStatus:
    failed: bool
    failure_boundary: int | None
    failure_code: str | None
    last_finalized_boundary: int | None
    last_captured_boundary: int | None
    missing_prefix_through: int | None


class CivilizationCaptureCoordinator:
    """Inner orchestration; outer callbacks receive detached values only."""

    __slots__ = (
        "_failure_boundary",
        "_failure_code",
        "_last_captured",
        "_last_finalized",
        "_missing_prefix",
        "_run_id",
        "_sink",
        "_staging",
        "_staging_complete",
    )

    def __init__(self, sink: CivilizationCaptureSink, run_id: str) -> None:
        self._run_id = _id(run_id)
        self._sink = sink
        self._failure_boundary: int | None = None
        self._failure_code: str | None = None
        self._last_captured: int | None = None
        self._last_finalized: int | None = None
        self._missing_prefix: int | None = None
        self._staging: dict[str, CivilizationGroundingObservation] = {}
        self._staging_complete = False

    def stage_observation(self, owner_id: str, observation: object) -> None:
        """Keep only IDs/ordinals from the current tick; never full observations."""
        if self._failure_code is not None:
            return
        row = project_grounding_observation(owner_id, observation)
        self._staging[row.owner_id] = row

    def complete_staging(self) -> None:
        self._staging_complete = True

    def discard_staging(self) -> None:
        self._staging.clear()
        self._staging_complete = False

    @property
    def staged_observations(self) -> tuple[CivilizationGroundingObservation, ...]:
        return tuple(self._staging[key] for key in sorted(self._staging))

    @property
    def status(self) -> CivilizationRunnerCaptureStatus:
        return CivilizationRunnerCaptureStatus(
            self._failure_code is not None,
            self._failure_boundary,
            self._failure_code,
            self._last_finalized,
            self._last_captured,
            self._missing_prefix,
        )

    def mark_failure(self, boundary: int, code: str) -> None:
        if self._failure_code is not None:
            return
        if code not in {
            "capture_build_failed",
            "capture_failed",
            "capture_pending_check_failed",
        }:
            code = "capture_failed"
        self._failure_boundary, self._failure_code = boundary, code
        _LOG.warning(
            "civilization_capture_failed boundary_tick=%s reason_code=%s",
            boundary,
            code,
        )

    def wants_events(self) -> bool:
        if self._failure_code is not None:
            return False
        try:
            return self._sink.wants_events()
        except Exception:
            self.mark_failure(self._last_finalized or 0, "capture_failed")
            return False

    def note_missing_prefix(self, boundary: int) -> None:
        if self._missing_prefix is None:
            self._missing_prefix = _count(boundary)

    def publish(
        self,
        boundary: int,
        facts: Callable[[], ObjectiveFacts],
        *,
        result: TickResult | None = None,
        recovery: bool = False,
        event_batch: CivilizationEventBatch | None = None,
        owner_inventory_factory: (
            Callable[[], tuple[CivilizationOwnerInventory, ...]] | None
        ) = None,
    ) -> None:
        if self._failure_code is not None:
            return
        if self._last_finalized is not None and boundary <= self._last_finalized:
            return
        failure_code = "capture_failed"
        try:
            _count(boundary)
            if not self._sink.wants_events():
                return
            if self._last_finalized is None and boundary > 0:
                self._missing_prefix = boundary - 1
            if boundary > 0:
                failure_code = "capture_build_failed"
                if event_batch is not None:
                    if event_batch.tick != boundary - 1:
                        raise CivilizationError()
                    batch = event_batch
                # Recovery without a journal-proven batch is explicitly unknown.
                elif recovery or result is None:
                    batch = unavailable_civilization_events(
                        self._run_id, boundary - 1
                    )
                else:
                    if result.resulting_tick.value != boundary:
                        raise CivilizationError()
                    batch = civilization_events_from_result(self._run_id, result)
                failure_code = "capture_failed"
                if not self._sink.capture_events(batch):
                    self.mark_failure(boundary, "capture_failed")
                    return
            if self._sink.wants_boundary(boundary):
                failure_code = "capture_build_failed"
                scene = scene_from_facts(facts())
                if scene.tick != boundary:
                    raise CivilizationError()
                inventories = (
                    ()
                    if owner_inventory_factory is None
                    else tuple(owner_inventory_factory())
                )
                frame = project_civilization_boundary(
                    scene,
                    owner_inventories=inventories,
                    grounding_observations=self.staged_observations,
                    grounding_observations_complete=self._staging_complete,
                )
                failure_code = "capture_failed"
                if not self._sink.capture_boundary(frame):
                    self.mark_failure(boundary, "capture_failed")
                    return
                self._last_captured = boundary
            self._last_finalized = boundary
        except Exception:
            self.mark_failure(boundary, failure_code)
        finally:
            self.discard_staging()
