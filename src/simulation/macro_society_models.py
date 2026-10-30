"""Immutable macro-society snapshot contract.

This module is deliberately independent of ``analysis``: ``experiments`` maps
analytical results into these DTOs, and ``persistence`` stores them. Analysis
never imports this module and this module never imports analysis.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MACRO_SOCIETY_SNAPSHOT_SCHEMA_VERSION",
    "MACRO_SOCIETY_STORE_SCHEMA_VERSION",
    "MAX_SNAPSHOT_BYTES",
    "MAX_SNAPSHOT_CANDIDATES",
    "MAX_SNAPSHOT_EDGES",
    "MAX_SNAPSHOT_MEMBERS",
    "MAX_SNAPSHOT_OBJECTIVE_ROWS",
    "MAX_SNAPSHOT_WINDOWS",
    "MacroSocietyArtifactError",
    "MacroSocietyCandidateRecord",
    "MacroSocietyCoverage",
    "MacroSocietyLineageEdgeRecord",
    "MacroSocietyObjectiveRow",
    "MacroSocietySnapshot",
    "MacroSocietySnapshotRef",
    "MacroSocietyWindowRecord",
    "require_macro_society_id",
]

MACRO_SOCIETY_SNAPSHOT_SCHEMA_VERSION: Final[str] = "macro-society-snapshot-v1"
MACRO_SOCIETY_STORE_SCHEMA_VERSION: Final[str] = "macro-society-store-v1"

MAX_SNAPSHOT_BYTES: Final[int] = 4 * 1024 * 1024
MAX_SNAPSHOT_CANDIDATES: Final[int] = 4096
MAX_SNAPSHOT_MEMBERS: Final[int] = 512
MAX_SNAPSHOT_EDGES: Final[int] = 16384
MAX_SNAPSHOT_WINDOWS: Final[int] = 512
MAX_SNAPSHOT_OBJECTIVE_ROWS: Final[int] = 4096

SOCIETY_STATUS_VALUES: Final[tuple[str, ...]] = (
    "supported",
    "fragmented",
    "contested",
)
LINEAGE_KIND_VALUES: Final[tuple[str, ...]] = (
    "continued",
    "transformed",
    "split",
    "merge",
    "dissolved",
    "emerged",
)

_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^msoc-[0-9a-f]{16}$")
_PUBLICATION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^msoc-edge-[0-9a-f]{16}$"
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.macro_society_models"
)


class MacroSocietyArtifactError(ValueError):
    """Fail-closed snapshot error with a stable reason code only."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        _LOG.debug(
            "macro_society_artifact_invalid reason_code=%s", reason_code
        )
        super().__init__(reason_code)


def require_macro_society_id(value: object) -> str:
    """Validate an exact ``msoc-`` plus 16 lowercase hex characters id."""
    if not isinstance(value, str) or not _ID_PATTERN.match(value):
        raise MacroSocietyArtifactError("macro_society_invalid_id")
    return value


def require_publication_id(value: object) -> str:
    """Validate an exact ``msoc-edge-`` plus 16 lowercase hex characters id."""
    if not isinstance(value, str) or not _PUBLICATION_PATTERN.match(value):
        raise MacroSocietyArtifactError("macro_society_invalid_publication_id")
    return value


def _stable(name: str, value: object) -> str:
    try:
        return require_stable_id(name, value)
    except ValueError as exc:
        raise MacroSocietyArtifactError("macro_society_invalid_value") from exc


def _tick(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except ValueError as exc:
        raise MacroSocietyArtifactError("macro_society_invalid_value") from exc


@dataclass(frozen=True, slots=True)
class MacroSocietyCoverage:
    """Observed-versus-expected counts for one snapshot."""

    observed: int
    expected: int
    ratio: float | None

    def __post_init__(self) -> None:
        observed = _tick("observed", self.observed)
        expected = _tick("expected", self.expected)
        if observed > expected:
            raise MacroSocietyArtifactError("macro_society_invalid_coverage")
        if self.ratio is not None and not isinstance(self.ratio, (int, float)):
            raise MacroSocietyArtifactError("macro_society_invalid_coverage")
        object.__setattr__(self, "observed", observed)
        object.__setattr__(self, "expected", expected)
        object.__setattr__(
            self, "ratio", None if self.ratio is None else float(self.ratio)
        )


@dataclass(frozen=True, slots=True)
class MacroSocietyWindowRecord:
    """One observation window in the published snapshot."""

    window_index: int
    tick_start: int
    tick_end: int
    candidate_ids: tuple[str, ...]
    overlap_person_count: int
    known_person_count: int
    lane_presence: tuple[tuple[str, bool], ...]

    def __post_init__(self) -> None:
        first = _tick("tick_start", self.tick_start)
        last = _tick("tick_end", self.tick_end)
        if last < first:
            raise MacroSocietyArtifactError("macro_society_invalid_tick_range")
        ids = tuple(sorted(set(self.candidate_ids)))
        if len(ids) != len(self.candidate_ids):
            raise MacroSocietyArtifactError("macro_society_duplicate_candidate")
        for candidate_id in ids:
            require_macro_society_id(candidate_id)
        lanes = tuple(
            sorted((str(lane), bool(present)) for lane, present in self.lane_presence)
        )
        object.__setattr__(
            self, "window_index", _tick("window_index", self.window_index)
        )
        object.__setattr__(self, "tick_start", first)
        object.__setattr__(self, "tick_end", last)
        object.__setattr__(self, "candidate_ids", ids)
        object.__setattr__(
            self,
            "overlap_person_count",
            _tick("overlap_person_count", self.overlap_person_count),
        )
        object.__setattr__(
            self,
            "known_person_count",
            _tick("known_person_count", self.known_person_count),
        )
        object.__setattr__(self, "lane_presence", lanes)


@dataclass(frozen=True, slots=True)
class MacroSocietyCandidateRecord:
    """One analytical candidate in the published snapshot."""

    macro_society_id: str
    creation_tick: int
    first_tick: int
    last_tick: int
    status: str
    member_ids: tuple[str, ...]
    lane_signature: tuple[str, ...]
    overlap_person_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        macro_id = require_macro_society_id(self.macro_society_id)
        creation = _tick("creation_tick", self.creation_tick)
        first = _tick("first_tick", self.first_tick)
        last = _tick("last_tick", self.last_tick)
        if last < first:
            raise MacroSocietyArtifactError("macro_society_invalid_tick_range")
        if creation != first:
            raise MacroSocietyArtifactError("macro_society_invalid_creation_tick")
        if self.status not in SOCIETY_STATUS_VALUES:
            raise MacroSocietyArtifactError("macro_society_invalid_status")
        members: list[str] = []
        seen: set[str] = set()
        for raw in self.member_ids:
            member = _stable("member_id", raw)
            if member in seen:
                raise MacroSocietyArtifactError("macro_society_duplicate_member")
            seen.add(member)
            members.append(member)
        if not members:
            raise MacroSocietyArtifactError("macro_society_empty_member_set")
        if len(members) > MAX_SNAPSHOT_MEMBERS:
            raise MacroSocietyArtifactError("macro_society_size_limit")
        lanes = tuple(
            sorted(set(_stable("lane", lane) for lane in self.lane_signature))
        )
        if not lanes:
            raise MacroSocietyArtifactError("macro_society_unknown_lane")
        overlap = tuple(
            sorted(
                set(
                    _stable("overlap_person_id", item)
                    for item in self.overlap_person_ids
                )
            )
        )
        object.__setattr__(self, "macro_society_id", macro_id)
        object.__setattr__(self, "creation_tick", creation)
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        object.__setattr__(self, "member_ids", tuple(sorted(members)))
        object.__setattr__(self, "lane_signature", lanes)
        object.__setattr__(self, "overlap_person_ids", overlap)


@dataclass(frozen=True, slots=True)
class MacroSocietyLineageEdgeRecord:
    """One forward-only lineage edge in the published snapshot."""

    from_id: str | None
    to_id: str | None
    kind: str
    from_tick: int
    to_tick: int
    jaccard: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in LINEAGE_KIND_VALUES:
            raise MacroSocietyArtifactError("macro_society_invalid_lineage_kind")
        if self.from_id is None and self.kind != "emerged":
            raise MacroSocietyArtifactError("macro_society_invalid_lineage_endpoint")
        if self.to_id is None and self.kind != "dissolved":
            raise MacroSocietyArtifactError("macro_society_invalid_lineage_endpoint")
        if self.from_id is not None:
            require_macro_society_id(self.from_id)
        if self.to_id is not None:
            require_macro_society_id(self.to_id)
        first = _tick("from_tick", self.from_tick)
        last = _tick("to_tick", self.to_tick)
        if last < first:
            raise MacroSocietyArtifactError("macro_society_invalid_tick_range")
        object.__setattr__(self, "from_tick", first)
        object.__setattr__(self, "to_tick", last)
        if self.jaccard is not None:
            object.__setattr__(self, "jaccard", float(self.jaccard))


@dataclass(frozen=True, slots=True)
class MacroSocietyObjectiveRow:
    """Objective population counts; never membership."""

    region_id: str
    tick: int
    population_count: int
    cohort_id: str | None = None
    stage_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "region_id", _stable("region_id", self.region_id))
        object.__setattr__(self, "tick", _tick("tick", self.tick))
        object.__setattr__(
            self,
            "population_count",
            _tick("population_count", self.population_count),
        )
        for name in ("cohort_id", "stage_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _stable(name, value))


@dataclass(frozen=True, slots=True)
class MacroSocietySnapshotRef:
    """A publication identity plus the digest of its canonical bytes."""

    publication_id: str
    digest: str
    schema_version: str = MACRO_SOCIETY_SNAPSHOT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "publication_id", require_publication_id(self.publication_id)
        )
        digest = _stable("digest", self.digest)
        if len(digest) != 64:
            raise MacroSocietyArtifactError("macro_society_invalid_digest")
        object.__setattr__(self, "digest", digest)
        if self.schema_version != MACRO_SOCIETY_SNAPSHOT_SCHEMA_VERSION:
            raise MacroSocietyArtifactError("macro_society_unsupported_schema")


@dataclass(frozen=True, slots=True)
class MacroSocietySnapshot:
    """One immutable macro-society publication."""

    schema_version: str
    policy_version: str
    run_id: str
    input_revision: str
    generated_tick: int
    publication_id: str
    windows: tuple[MacroSocietyWindowRecord, ...]
    candidates: tuple[MacroSocietyCandidateRecord, ...]
    edges: tuple[MacroSocietyLineageEdgeRecord, ...]
    objective_rows: tuple[MacroSocietyObjectiveRow, ...]
    coverage: MacroSocietyCoverage
    provenance_code: str

    def __post_init__(self) -> None:
        if self.schema_version != MACRO_SOCIETY_SNAPSHOT_SCHEMA_VERSION:
            raise MacroSocietyArtifactError("macro_society_unsupported_schema")
        object.__setattr__(
            self, "policy_version", _stable("policy_version", self.policy_version)
        )
        object.__setattr__(self, "run_id", _stable("run_id", self.run_id))
        object.__setattr__(
            self, "input_revision", _stable("input_revision", self.input_revision)
        )
        object.__setattr__(
            self, "generated_tick", _tick("generated_tick", self.generated_tick)
        )
        object.__setattr__(
            self, "publication_id", require_publication_id(self.publication_id)
        )
        windows = tuple(self.windows)
        candidates = tuple(self.candidates)
        edges = tuple(self.edges)
        objective = tuple(self.objective_rows)
        if len(windows) > MAX_SNAPSHOT_WINDOWS:
            raise MacroSocietyArtifactError("macro_society_size_limit")
        if len(candidates) > MAX_SNAPSHOT_CANDIDATES:
            raise MacroSocietyArtifactError("macro_society_size_limit")
        if len(edges) > MAX_SNAPSHOT_EDGES:
            raise MacroSocietyArtifactError("macro_society_size_limit")
        if len(objective) > MAX_SNAPSHOT_OBJECTIVE_ROWS:
            raise MacroSocietyArtifactError("macro_society_size_limit")
        indexes = [window.window_index for window in windows]
        if indexes != sorted(indexes) or len(set(indexes)) != len(indexes):
            raise MacroSocietyArtifactError("macro_society_invalid_window")
        ids = [candidate.macro_society_id for candidate in candidates]
        if len(set(ids)) != len(ids):
            raise MacroSocietyArtifactError("macro_society_duplicate_candidate")
        known = set(ids)
        for candidate in candidates:
            if not set(candidate.overlap_person_ids) <= set(candidate.member_ids):
                raise MacroSocietyArtifactError("macro_society_unknown_person")
        for window in windows:
            unknown = set(window.candidate_ids) - known
            if unknown:
                raise MacroSocietyArtifactError("macro_society_unknown_society")
        for edge in edges:
            for endpoint in (edge.from_id, edge.to_id):
                if endpoint is not None and endpoint not in known:
                    raise MacroSocietyArtifactError("macro_society_unknown_society")
        if type(self.coverage) is not MacroSocietyCoverage:
            raise MacroSocietyArtifactError("macro_society_invalid_coverage")
        object.__setattr__(self, "windows", windows)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(
            self,
            "edges",
            tuple(
                sorted(
                    edges,
                    key=lambda item: (
                        item.from_tick,
                        item.from_id or "",
                        item.to_id or "",
                        item.kind,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "objective_rows",
            tuple(
                sorted(
                    objective,
                    key=lambda item: (
                        item.tick,
                        item.region_id,
                        item.cohort_id or "",
                        item.stage_id or "",
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "provenance_code",
            _stable("provenance_code", self.provenance_code),
        )
