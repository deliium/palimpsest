"""Detached analysis of institution-like pattern bundles.

Nothing here is a world entity or an institution type. A candidate is an opaque
content-derived bundle of six evidence lanes: persistent role, repeated
procedure, social expectation, legitimacy belief, succession, and
cross-generational continuity. Missing lanes stay absent, never zero.
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.institution_emergence")

_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_DIGEST_LEN: Final[int] = 16
_MIN_PERSISTENCE_SPAN: Final[int] = 4
_LANE_PATTERN_FLOOR: Final[float] = 0.45
_BUNDLE_FLOOR: Final[float] = 1.80
_MAX_ACTORS: Final[int] = 32


class InstitutionAnalysisError(ValueError):
    """Fail-closed analysis error; messages are codes only."""


class InstitutionLane(StrEnum):
    """Closed analysis lane identifiers."""

    ROLE = "role_persistence"
    PROCEDURE = "procedure_recurrence"
    EXPECTATION = "social_expectation"
    LEGITIMACY = "legitimacy_belief"
    SUCCESSION = "succession"
    CONTINUITY = "cross_generational_continuity"


_LANE_ORDER: Final[tuple[InstitutionLane, ...]] = (
    InstitutionLane.ROLE,
    InstitutionLane.PROCEDURE,
    InstitutionLane.EXPECTATION,
    InstitutionLane.LEGITIMACY,
    InstitutionLane.SUCCESSION,
    InstitutionLane.CONTINUITY,
)


def _sha256_hex(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _require_digest(field_name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _DIGEST_LEN
        or any(char not in _HEX for char in value)
    ):
        raise InstitutionAnalysisError(f"invalid_digest:{field_name}")
    return value


def _require_int(field_name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise InstitutionAnalysisError(f"invalid_int:{field_name}")
    return value


@dataclass(frozen=True, slots=True)
class InstitutionLaneRow:
    """One detached evidence item for one analytical lane."""

    lane: InstitutionLane
    subject_digest: str
    evidence_digest: str
    tick_start: int
    tick_end: int
    occurrence_count: int = 1
    actor_digests: tuple[str, ...] = ()
    generation_start: int | None = None
    generation_end: int | None = None
    function_token: str | None = None

    def __post_init__(self) -> None:
        if type(self.lane) is not InstitutionLane:
            raise InstitutionAnalysisError("unknown_lane")
        object.__setattr__(
            self,
            "subject_digest",
            _require_digest("subject_digest", self.subject_digest),
        )
        object.__setattr__(
            self,
            "evidence_digest",
            _require_digest("evidence_digest", self.evidence_digest),
        )
        object.__setattr__(
            self, "tick_start", _require_int("tick_start", self.tick_start)
        )
        object.__setattr__(self, "tick_end", _require_int("tick_end", self.tick_end))
        if self.tick_end < self.tick_start:
            raise InstitutionAnalysisError("tick_end_before_start")
        object.__setattr__(
            self,
            "occurrence_count",
            _require_int("occurrence_count", self.occurrence_count),
        )
        if self.occurrence_count < 1:
            raise InstitutionAnalysisError("occurrence_count")
        actors: list[str] = []
        seen: set[str] = set()
        for actor in self.actor_digests:
            digest = _require_digest("actor_digest", actor)
            if digest in seen:
                raise InstitutionAnalysisError("duplicate_actor")
            seen.add(digest)
            actors.append(digest)
        if len(actors) > _MAX_ACTORS:
            raise InstitutionAnalysisError("actor_cap")
        object.__setattr__(self, "actor_digests", tuple(actors))
        for name in ("generation_start", "generation_end"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or type(value) is not int or value < 0
            ):
                raise InstitutionAnalysisError(f"invalid_int:{name}")
        if (
            self.generation_start is not None
            and self.generation_end is not None
            and self.generation_end < self.generation_start
        ):
            raise InstitutionAnalysisError("generation_end_before_start")
        if self.function_token is not None and (
            not isinstance(self.function_token, str) or not self.function_token
        ):
            raise InstitutionAnalysisError("invalid_function_token")


@dataclass(frozen=True, slots=True)
class InstitutionCandidateRow:
    """One analytical candidate bundle. Never an institution type."""

    candidate_id: str
    lane_strengths: tuple[tuple[str, str], ...]
    evidence_digests: tuple[str, ...]
    lane_coverage: tuple[str, ...]
    actor_digests: tuple[str, ...]
    tick_start: int
    tick_end: int
    generation_span: int
    row_count: int
    above_floor: bool
    lane_rows: tuple[InstitutionLaneRow, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.candidate_id, str)
            or len(self.candidate_id) != 64
            or any(char not in _HEX for char in self.candidate_id)
        ):
            raise InstitutionAnalysisError("invalid_candidate_id")
        strengths: list[tuple[str, str]] = []
        for item in self.lane_strengths:
            if not isinstance(item, tuple) or len(item) != 2:
                raise InstitutionAnalysisError("invalid_lane_strength")
            lane, value = item
            if lane not in {entry.value for entry in InstitutionLane}:
                raise InstitutionAnalysisError("unknown_lane")
            strengths.append((lane, str(value)))
        object.__setattr__(self, "lane_strengths", tuple(strengths))
        object.__setattr__(
            self,
            "evidence_digests",
            tuple(_require_digest("evidence", item) for item in self.evidence_digests),
        )
        if len(set(self.lane_coverage)) != len(self.lane_coverage):
            raise InstitutionAnalysisError("duplicate_lane_coverage")
        object.__setattr__(
            self,
            "actor_digests",
            tuple(_require_digest("actor", item) for item in self.actor_digests),
        )
        object.__setattr__(
            self, "tick_start", _require_int("tick_start", self.tick_start)
        )
        object.__setattr__(self, "tick_end", _require_int("tick_end", self.tick_end))
        object.__setattr__(
            self,
            "generation_span",
            _require_int("generation_span", self.generation_span),
        )
        object.__setattr__(self, "row_count", _require_int("row_count", self.row_count))
        if type(self.above_floor) is not bool:
            raise InstitutionAnalysisError("invalid_above_floor")
        rows = tuple(self.lane_rows)
        for row in rows:
            if type(row) is not InstitutionLaneRow:
                raise InstitutionAnalysisError("invalid_lane_row")
        object.__setattr__(self, "lane_rows", rows)

    def strength_for(self, lane: InstitutionLane) -> float:
        for name, value in self.lane_strengths:
            if name == lane.value:
                return float(value)
        return 0.0


@dataclass(frozen=True, slots=True)
class InstitutionEmergenceResult:
    """Detached candidates, sub-threshold bundles, and coverage."""

    candidates: tuple[InstitutionCandidateRow, ...]
    sub_threshold: tuple[InstitutionCandidateRow, ...]
    coverage: MetricCoverage
    known_person_ids: tuple[str, ...]
    lane_row_counts: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        for row in (*self.candidates, *self.sub_threshold):
            if type(row) is not InstitutionCandidateRow:
                raise InstitutionAnalysisError("invalid_candidate")
        if type(self.coverage) is not MetricCoverage:
            raise InstitutionAnalysisError("invalid_coverage")
        people = tuple(
            require_stable_id("known_person_id", item) for item in self.known_person_ids
        )
        if len(set(people)) != len(people):
            raise InstitutionAnalysisError("duplicate_person")
        object.__setattr__(self, "known_person_ids", people)
        counts: list[tuple[str, int]] = []
        for item in self.lane_row_counts:
            if not isinstance(item, tuple) or len(item) != 2:
                raise InstitutionAnalysisError("invalid_lane_counts")
            lane, count = item
            if lane not in {entry.value for entry in InstitutionLane}:
                raise InstitutionAnalysisError("unknown_lane")
            counts.append((lane, _require_int("lane_count", count)))
        object.__setattr__(self, "lane_row_counts", tuple(counts))


def _normalize_rows(rows: Sequence[object] | None) -> tuple[InstitutionLaneRow, ...]:
    out: list[InstitutionLaneRow] = []
    for row in rows or ():
        if type(row) is InstitutionLaneRow:
            out.append(row)
            continue
        if isinstance(row, Mapping):
            lane = row.get("lane")
            if not isinstance(lane, str):
                raise InstitutionAnalysisError("invalid_lane_row")
            try:
                lane_value = InstitutionLane(lane)
            except (TypeError, ValueError) as exc:
                raise InstitutionAnalysisError("invalid_lane_row") from exc
            out.append(
                InstitutionLaneRow(
                    lane=lane_value,
                    subject_digest=str(row.get("subject_digest", "")),
                    evidence_digest=str(row.get("evidence_digest", "")),
                    tick_start=row.get("tick_start", 0),
                    tick_end=row.get("tick_end", 0),
                    occurrence_count=row.get("occurrence_count", 1),
                    actor_digests=tuple(row.get("actor_digests", ())),
                    generation_start=row.get("generation_start"),
                    generation_end=row.get("generation_end"),
                    function_token=row.get("function_token"),
                )
            )
            continue
        raise InstitutionAnalysisError("invalid_lane_row")
    return tuple(out)


def _lane_strength(row: InstitutionLaneRow) -> float:
    base = min(1.0, float(row.occurrence_count) / 3.0)
    span = row.tick_end - row.tick_start
    if span >= _MIN_PERSISTENCE_SPAN:
        base = min(1.0, base + 0.20)
    return quantize_float(require_finite(base))


def _candidate_id(rows: Sequence[InstitutionLaneRow]) -> str:
    material = "|".join(sorted(row.evidence_digest for row in rows))
    return _sha256_hex(f"institution-candidate|{material}")


def _build_candidate(rows: Sequence[InstitutionLaneRow]) -> InstitutionCandidateRow:
    ordered = sorted(
        rows,
        key=lambda row: (row.lane.value, row.evidence_digest, row.tick_start),
    )
    lane_values: dict[InstitutionLane, list[float]] = defaultdict(list)
    actors: set[str] = set()
    generation_starts: list[int] = []
    generation_ends: list[int] = []
    for row in ordered:
        lane_values[row.lane].append(_lane_strength(row))
        actors.update(row.actor_digests)
        if row.generation_start is not None:
            generation_starts.append(row.generation_start)
        if row.generation_end is not None:
            generation_ends.append(row.generation_end)
    strengths = tuple(
        (
            lane.value,
            str(
                quantize_float(
                    require_finite(
                        min(
                            1.0, sum(lane_values[lane]) / max(1, len(lane_values[lane]))
                        )
                    )
                )
            ),
        )
        for lane in _LANE_ORDER
        if lane in lane_values
    )
    total = sum(float(value) for _, value in strengths)
    above = total >= _BUNDLE_FLOOR and any(
        float(value) >= _LANE_PATTERN_FLOOR for _, value in strengths
    )
    generation_span = 0
    if generation_starts and generation_ends:
        generation_span = max(generation_ends) - min(generation_starts)
    return InstitutionCandidateRow(
        candidate_id=_candidate_id(ordered),
        lane_strengths=strengths,
        evidence_digests=tuple(sorted({row.evidence_digest for row in ordered})),
        lane_coverage=tuple(lane.value for lane in _LANE_ORDER if lane in lane_values),
        actor_digests=tuple(sorted(actors)),
        tick_start=min(row.tick_start for row in ordered),
        tick_end=max(row.tick_end for row in ordered),
        generation_span=generation_span,
        row_count=len(ordered),
        above_floor=above,
        lane_rows=tuple(ordered),
    )


def compute_institution_candidates(
    *,
    role_rows: Sequence[object] | None = None,
    procedure_rows: Sequence[object] | None = None,
    expectation_rows: Sequence[object] | None = None,
    legitimacy_rows: Sequence[object] | None = None,
    succession_rows: Sequence[object] | None = None,
    continuity_rows: Sequence[object] | None = None,
    known_person_ids: Sequence[str] = (),
    tick: int = 0,
) -> InstitutionEmergenceResult:
    """Bundle detached lane rows into deterministic candidates.

    Structural lanes (role/procedure/succession/continuity) anchor candidates.
    Expectation and legitimacy rows attach to the deterministic lowest anchored
    candidate; when no structural row exists they form their own bundle.
    """
    tick = require_exact_nonneg_int("tick", tick)
    lanes = {
        InstitutionLane.ROLE: _normalize_rows(role_rows),
        InstitutionLane.PROCEDURE: _normalize_rows(procedure_rows),
        InstitutionLane.EXPECTATION: _normalize_rows(expectation_rows),
        InstitutionLane.LEGITIMACY: _normalize_rows(legitimacy_rows),
        InstitutionLane.SUCCESSION: _normalize_rows(succession_rows),
        InstitutionLane.CONTINUITY: _normalize_rows(continuity_rows),
    }
    by_subject: dict[str, list[InstitutionLaneRow]] = defaultdict(list)
    structural: list[InstitutionLaneRow] = []
    for lane in (
        InstitutionLane.ROLE,
        InstitutionLane.PROCEDURE,
        InstitutionLane.SUCCESSION,
        InstitutionLane.CONTINUITY,
    ):
        structural.extend(lanes[lane])
    if structural:
        anchor_key = min(row.subject_digest for row in structural)
        by_subject[anchor_key].extend(structural)
        for lane in (InstitutionLane.EXPECTATION, InstitutionLane.LEGITIMACY):
            by_subject[anchor_key].extend(lanes[lane])
    else:
        for lane in (InstitutionLane.EXPECTATION, InstitutionLane.LEGITIMACY):
            for row in lanes[lane]:
                by_subject[row.subject_digest].append(row)

    candidates: list[InstitutionCandidateRow] = []
    for subject in sorted(by_subject):
        candidates.append(_build_candidate(by_subject[subject]))
    above = tuple(row for row in candidates if row.above_floor)
    below = tuple(row for row in candidates if not row.above_floor)
    known = tuple(
        require_stable_id("known_person_id", item) for item in known_person_ids
    )
    observed = len(above)
    expected = len(known) if known else len(candidates)
    ratio = None
    if expected:
        ratio = quantize_float(require_finite(float(observed) / float(expected)))
    coverage = MetricCoverage(observed=observed, expected=expected, ratio=ratio)
    counts = tuple((lane.value, len(lanes[lane])) for lane in _LANE_ORDER)
    result = InstitutionEmergenceResult(
        candidates=above,
        sub_threshold=below,
        coverage=coverage,
        known_person_ids=known,
        lane_row_counts=counts,
    )
    _LOG.debug(
        "institution_candidates_computed candidate_count=%s sub_threshold=%s "
        "tick=%s lane_counts=%s",
        len(result.candidates),
        len(result.sub_threshold),
        tick,
        counts,
    )
    _LOG.info(
        "institution_candidates_summary candidate_count=%s sub_threshold=%s",
        len(result.candidates),
        len(result.sub_threshold),
    )
    return result


def compute_institution_emergence(
    result: InstitutionEmergenceResult,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Pin one institution-emergence document for a run revision."""
    if type(result) is not InstitutionEmergenceResult:
        raise InstitutionAnalysisError("invalid_result")
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    tick = require_exact_nonneg_int("tick", tick)
    spec = metric_specification(MetricFamilyId.INSTITUTION_EMERGENCE)
    lane_counts = {lane: count for lane, count in result.lane_row_counts}
    if not result.candidates and not result.sub_threshold:
        availability = MetricAvailability.ABSENT
    elif not result.candidates:
        availability = MetricAvailability.PARTIAL
    else:
        availability = MetricAvailability.PRESENT
    max_span = 0
    if result.candidates:
        max_span = max(row.tick_end - row.tick_start for row in result.candidates)
    generation_spans = [
        row.generation_span for row in result.candidates if row.generation_span > 0
    ]
    multi_generation = sum(
        1
        for row in result.candidates
        if InstitutionLane.CONTINUITY.value in row.lane_coverage
    )
    _LOG.debug(
        "institution_emergence_document family_id=%s availability=%s "
        "candidate_count=%s lane_counts=%s",
        spec.family_id.value,
        availability.value,
        len(result.candidates),
        lane_counts,
    )
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=result.coverage,
        availability=availability,
        values={
            "candidate_count": len(result.candidates),
            "sub_threshold_count": len(result.sub_threshold),
            "lane_row_counts": ";".join(
                f"{lane.value}:{lane_counts.get(lane.value, 0)}" for lane in _LANE_ORDER
            ),
            "max_tick_span": max_span,
            "multi_generation_candidate_count": multi_generation,
            "max_generation_span": max(generation_spans) if generation_spans else 0,
            "as_of_tick": tick,
        },
        provenance=MetricProvenance(
            source_kind="institution_emergence",
            source_ids=(),
            notes_code="ok"
            if availability is not MetricAvailability.ABSENT
            else "empty",
        ),
    )
