"""Independent, framework-free civilization presentation contracts.

These values confer no simulation authority. A finalized boundary B is the
start of tick B; an event prefix is not a finalized private-state boundary.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal
from unicodedata import category

__all__ = [
    "CIVILIZATION_CATALOGUE_SCHEMA",
    "CIVILIZATION_MAP_SCHEMA",
    "CIVILIZATION_MARKERS_SCHEMA",
    "CIVILIZATION_OVERLAY_SCHEMA",
    "CIVILIZATION_SNAPSHOT_SCHEMA",
    "CIVILIZATION_STORAGE_CATALOGUE_SCHEMA",
    "CivilizationAnchor",
    "CivilizationAnchorKind",
    "CivilizationArtifactRef",
    "CivilizationCoverage",
    "CivilizationCoverageState",
    "CivilizationCursor",
    "CivilizationError",
    "CivilizationEvidenceClass",
    "CivilizationHashManifest",
    "CivilizationLayer",
    "CivilizationMarker",
    "CivilizationMarkerType",
    "CivilizationPublicationRef",
    "CivilizationScope",
    "CivilizationSection",
    "CivilizationSourceRef",
    "CivilizationWindow",
]

_LOG = logging.getLogger(__name__)
CIVILIZATION_MAP_SCHEMA: Final = "observer-civilization-map-v1"
CIVILIZATION_CATALOGUE_SCHEMA: Final = "observer-civilization-catalogue-v1"
CIVILIZATION_OVERLAY_SCHEMA: Final = "observer-civilization-overlay-v1"
CIVILIZATION_MARKERS_SCHEMA: Final = "observer-civilization-markers-v1"
CIVILIZATION_SNAPSHOT_SCHEMA: Final = "civilization-snapshot-v1"
CIVILIZATION_STORAGE_CATALOGUE_SCHEMA: Final = "civilization-catalogue-v1"


class CivilizationError(ValueError):
    """Only closed metadata codes cross the boundary; never input reprs."""

    def __init__(self, code: str = "invalid_civilization_contract") -> None:
        if code not in {
            "invalid_civilization_contract",
            "invalid_civilization_scope",
            "civilization_row_too_large",
            "civilization_read_budget",
            "civilization_response_budget",
            "civilization_storage_corrupt",
        }:
            code = "invalid_civilization_contract"
        self.code = code
        _LOG.debug("civilization_rejected reason_code=%s", code)
        super().__init__(code)


def _id(value: object) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 512
        or value != value.strip()
        or any(category(c) == "Cc" for c in value)
    ):
        raise CivilizationError()
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise CivilizationError() from None
    return value


def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise CivilizationError()
    return value


def _enum(value: object, expected: type[StrEnum]) -> None:
    if type(value) is not expected:
        raise CivilizationError()


class CivilizationEvidenceClass(StrEnum):
    OBJECTIVE = "OBJECTIVE"
    SUBJECTIVE = "SUBJECTIVE"
    ANALYTICAL = "ANALYTICAL"


class CivilizationSection(StrEnum):
    REGIONS = "regions"
    ROUTES = "routes"
    LOCATIONS = "locations"
    PROJECTS = "projects"
    REPOSITORIES = "repositories"
    RECORDS = "records"


class CivilizationLayer(StrEnum):
    SETTLEMENTS = "settlements"
    MIGRATION = "migration"
    TRADE = "trade"
    CULTURE = "culture"
    TECHNOLOGY = "technology"
    SOCIAL_GROUPS = "social_groups"
    INSTITUTIONS = "institutions"


@dataclass(frozen=True, slots=True)
class CivilizationCursor:
    run_id: str
    world_id: str
    tick: int
    through_sequence: int | None
    boundary_tick: int | None
    revision: int

    def __post_init__(self) -> None:
        _id(self.run_id)
        _id(self.world_id)
        _count(self.tick)
        _count(self.revision)
        if self.through_sequence is not None:
            _count(self.through_sequence)
            if self.boundary_tick is not None:
                raise CivilizationError()
        if self.boundary_tick is not None:
            _count(self.boundary_tick)
            if self.boundary_tick != self.tick:
                raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationScope:
    layer: CivilizationSection | CivilizationLayer
    evidence_class: CivilizationEvidenceClass
    owner_id: str | None = None

    def __post_init__(self) -> None:
        _enum(self.evidence_class, CivilizationEvidenceClass)
        if type(self.layer) not in (CivilizationSection, CivilizationLayer):
            raise CivilizationError("invalid_civilization_scope")
        if self.owner_id is not None:
            _id(self.owner_id)
        subjective = self.evidence_class is CivilizationEvidenceClass.SUBJECTIVE
        if subjective != (self.owner_id is not None):
            raise CivilizationError("invalid_civilization_scope")
        if type(self.layer) is CivilizationSection:
            allowed = {CivilizationEvidenceClass.OBJECTIVE}
        elif self.layer is CivilizationLayer.MIGRATION:
            allowed = {CivilizationEvidenceClass.OBJECTIVE}
        elif self.layer in {
            CivilizationLayer.TECHNOLOGY,
            CivilizationLayer.SOCIAL_GROUPS,
            CivilizationLayer.INSTITUTIONS,
        }:
            allowed = {
                CivilizationEvidenceClass.SUBJECTIVE,
                CivilizationEvidenceClass.ANALYTICAL,
            }
        else:
            allowed = {CivilizationEvidenceClass.ANALYTICAL}
        if self.evidence_class not in allowed:
            raise CivilizationError("invalid_civilization_scope")


class CivilizationCoverageState(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class CivilizationWindow:
    """Half-open [start_tick, end_tick); also used for missing intervals."""

    start_tick: int
    end_tick: int

    def __post_init__(self) -> None:
        _count(self.start_tick)
        _count(self.end_tick)
        if self.start_tick > self.end_tick:
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationCoverage:
    state: CivilizationCoverageState
    reason: str | None = None
    capture_start: int | None = None
    capture_end: int | None = None
    missing_intervals: tuple[CivilizationWindow, ...] = ()
    observed_count: int | None = None
    expected_count: int | None = None

    def __post_init__(self) -> None:
        _enum(self.state, CivilizationCoverageState)
        if self.reason is not None:
            if self.reason not in {
                "capture_off",
                "channel_absent",
                "boundary_not_captured",
                "finalized_boundary_required",
                "publication_pending",
                "capture_gap",
                "capture_failed",
                "capture_limit",
                "unresolved_anchor",
                "missing_denominator",
                "partial_owner_coverage",
                "insufficient_history",
                "event_gap",
                "grounding_unavailable",
                "source_conflict",
            }:
                raise CivilizationError()
        for value in (
            self.capture_start,
            self.capture_end,
            self.observed_count,
            self.expected_count,
        ):
            if value is not None:
                _count(value)
        if (self.capture_start is None) != (self.capture_end is None):
            raise CivilizationError()
        if (
            self.capture_start is not None
            and self.capture_end is not None
            and self.capture_start > self.capture_end
        ):
            raise CivilizationError()
        if (
            self.observed_count is not None
            and self.expected_count is not None
            and self.observed_count > self.expected_count
        ):
            raise CivilizationError()
        intervals = tuple(self.missing_intervals)
        previous_end = -1
        for interval in intervals:
            if (
                type(interval) is not CivilizationWindow
                or interval.start_tick >= interval.end_tick
                or interval.start_tick < previous_end
            ):
                raise CivilizationError()
            if (
                self.capture_start is not None
                and self.capture_end is not None
                and not self.capture_start
                <= interval.start_tick
                < interval.end_tick
                <= self.capture_end
            ):
                raise CivilizationError()
            previous_end = interval.end_tick
        object.__setattr__(self, "missing_intervals", intervals)
        if self.state is CivilizationCoverageState.COMPLETE:
            if intervals or self.reason is not None:
                raise CivilizationError()
            if (
                self.expected_count is not None
                and self.observed_count != self.expected_count
            ):
                raise CivilizationError()
        elif self.reason is None:
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationSourceRef:
    """Qualified identity only, never source text or an interpreted label."""

    source_kind: str
    source_id: str
    tick: int
    owner_id: str | None = None

    def __post_init__(self) -> None:
        if self.source_kind not in {
            "scene",
            "event",
            "inventory",
            "knowledge",
            "group",
            "concept",
            "office",
            "institution_episode",
            "project",
            "repository",
            "record",
            "journey",
            "lineage",
        }:
            raise CivilizationError()
        _id(self.source_id)
        _count(self.tick)
        if self.owner_id is not None:
            _id(self.owner_id)
        if (
            self.source_kind in {"inventory", "knowledge", "group", "concept", "office"}
            and self.owner_id is None
        ):
            raise CivilizationError()


class CivilizationAnchorKind(StrEnum):
    LOCATION = "location"
    STRUCTURE = "structure"
    REPOSITORY = "repository"
    PROJECT = "project"
    AGENT_AT_EVIDENCE = "agent_at_evidence"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class CivilizationAnchor:
    kind: CivilizationAnchorKind
    location_id: str | None = None
    entity_id: str | None = None
    evidence_ref: CivilizationSourceRef | None = None
    evidence_tick: int | None = None

    def __post_init__(self) -> None:
        _enum(self.kind, CivilizationAnchorKind)
        for value in (self.location_id, self.entity_id):
            if value is not None:
                _id(value)
        if self.kind is CivilizationAnchorKind.NONE:
            if any(
                value is not None
                for value in (
                    self.location_id,
                    self.entity_id,
                    self.evidence_ref,
                    self.evidence_tick,
                )
            ):
                raise CivilizationError()
            return
        if (
            self.location_id is None
            or self.evidence_tick is None
            or type(self.evidence_ref) is not CivilizationSourceRef
        ):
            raise CivilizationError()
        _count(self.evidence_tick)
        if self.evidence_ref.tick != self.evidence_tick:
            raise CivilizationError()
        if self.kind is not CivilizationAnchorKind.LOCATION and self.entity_id is None:
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationPublicationRef:
    publication_id: str
    digest: str
    policy_version: str

    def __post_init__(self) -> None:
        _id(self.publication_id)
        _id(self.policy_version)
        if (
            type(self.digest) is not str
            or len(self.digest) != 64
            or any(c not in "0123456789abcdef" for c in self.digest)
        ):
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationArtifactRef:
    """A parent references a child, never itself or an ancestor."""

    kind: Literal["row_shard", "boundary_manifest", "catalogue_page", "catalogue_index"]
    key: str
    digest: str
    byte_count: int
    row_count: int
    first_key: str
    last_key: str

    def __post_init__(self) -> None:
        if self.kind not in {
            "row_shard",
            "boundary_manifest",
            "catalogue_page",
            "catalogue_index",
        }:
            raise CivilizationError()
        _id(self.key)
        if (
            self.key.startswith(("/", "\\"))
            or "\\" in self.key
            or any(part in ("", ".", "..") for part in self.key.split("/"))
        ):
            raise CivilizationError()
        CivilizationPublicationRef("validation", self.digest, "validation")
        _count(self.byte_count)
        _count(self.row_count)
        _id(self.first_key)
        _id(self.last_key)
        cap = 1024 * 1024 if self.kind in ("row_shard", "catalogue_page") else 65536
        if self.byte_count > cap or self.first_key > self.last_key:
            raise CivilizationError()
        if self.kind in ("row_shard", "catalogue_page") and self.row_count > 200:
            raise CivilizationError()


@dataclass(frozen=True, slots=True)
class CivilizationHashManifest:
    """Acyclic hash payload; the commit alone names the catalogue-index hash.

    Publication ID predates hashing. There is deliberately no self/root digest
    field. Each layer has exactly one permitted child kind.
    """

    kind: Literal["boundary_manifest", "catalogue_page", "catalogue_index", "commit"]
    run_id: str
    world_id: str
    publication_id: str
    config_id: str
    source_id: str
    policy_version: str
    boundary_tick: int | None
    children: tuple[CivilizationArtifactRef, ...]

    def __post_init__(self) -> None:
        for value in (
            self.run_id,
            self.world_id,
            self.publication_id,
            self.config_id,
            self.source_id,
            self.policy_version,
        ):
            _id(value)
        child_kind = {
            "boundary_manifest": "row_shard",
            "catalogue_page": "boundary_manifest",
            "catalogue_index": "catalogue_page",
            "commit": "catalogue_index",
        }.get(self.kind)
        if child_kind is None:
            raise CivilizationError()
        if (self.kind == "boundary_manifest") != (self.boundary_tick is not None):
            raise CivilizationError()
        if self.boundary_tick is not None:
            _count(self.boundary_tick)
        children = tuple(self.children)
        if len(children) > 200 or len({ref.key for ref in children}) != len(children):
            raise CivilizationError()
        previous: str | None = None
        for ref in children:
            if type(ref) is not CivilizationArtifactRef or ref.kind != child_kind:
                raise CivilizationError()
            if previous is not None and ref.first_key <= previous:
                raise CivilizationError()
            previous = ref.last_key
        if self.kind == "commit" and len(children) != 1:
            raise CivilizationError()
        object.__setattr__(self, "children", children)


class CivilizationMarkerType(StrEnum):
    SETTLEMENT_ACTIVATED = "settlement_activated"
    SETTLEMENT_DEACTIVATED = "settlement_deactivated"
    JOURNEY_STARTED = "journey_started"
    JOURNEY_ARRIVED = "journey_arrived"
    JOURNEY_ENDED = "journey_ended"
    TECHNOLOGY_ACQUIRED = "technology_acquired"
    INSTITUTION_TRANSITION = "institution_transition"


@dataclass(frozen=True, slots=True)
class CivilizationMarker:
    marker_id: str
    marker_type: CivilizationMarkerType
    seek_boundary: int
    evidence_class: CivilizationEvidenceClass
    owner_id: str | None
    layer: CivilizationLayer
    row_id: str
    source_refs: tuple[CivilizationSourceRef, ...]
    coverage: CivilizationCoverage

    def __post_init__(self) -> None:
        _id(self.marker_id)
        _id(self.row_id)
        _count(self.seek_boundary)
        _enum(self.marker_type, CivilizationMarkerType)
        CivilizationScope(self.layer, self.evidence_class, self.owner_id)
        expected_layer = {
            CivilizationMarkerType.SETTLEMENT_ACTIVATED: CivilizationLayer.SETTLEMENTS,
            CivilizationMarkerType.SETTLEMENT_DEACTIVATED: (
                CivilizationLayer.SETTLEMENTS
            ),
            CivilizationMarkerType.JOURNEY_STARTED: CivilizationLayer.MIGRATION,
            CivilizationMarkerType.JOURNEY_ARRIVED: CivilizationLayer.MIGRATION,
            CivilizationMarkerType.JOURNEY_ENDED: CivilizationLayer.MIGRATION,
            CivilizationMarkerType.TECHNOLOGY_ACQUIRED: CivilizationLayer.TECHNOLOGY,
            CivilizationMarkerType.INSTITUTION_TRANSITION: (
                CivilizationLayer.INSTITUTIONS
            ),
        }[self.marker_type]
        if self.layer is not expected_layer:
            raise CivilizationError()
        refs = tuple(self.source_refs)
        if not refs or len(refs) > 32 or len(set(refs)) != len(refs):
            raise CivilizationError()
        for ref in refs:
            if type(ref) is not CivilizationSourceRef or ref.tick >= self.seek_boundary:
                raise CivilizationError()
            if self.owner_id is not None and ref.owner_id not in (None, self.owner_id):
                raise CivilizationError()
        object.__setattr__(self, "source_refs", refs)
        if (
            type(self.coverage) is not CivilizationCoverage
            or self.coverage.state is not CivilizationCoverageState.COMPLETE
        ):
            raise CivilizationError()
