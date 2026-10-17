"""Cross-candidate-community isolation audit.

Every cross-community evidence edge is classified as ``journey_explained`` or
``unexplained`` against objective arrival evidence ordered by logical tick.
``unexplained > 0`` is a reported finding only; nothing is auto-remediated.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.society_emergence import CandidateCommunityRow
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "SOCIETY_EVIDENCE_KINDS",
    "SOCIETY_ISOLATION_METRIC_VERSION",
    "SocietyEvidenceEdge",
    "SocietyIsolationError",
    "SocietyIsolationResult",
    "SocietyIsolationRow",
    "SocietyJourneyRow",
    "compute_society_isolation",
    "compute_society_isolation_metric",
]

SOCIETY_ISOLATION_METRIC_VERSION: Final[str] = "society_isolation@1"
SOCIETY_EVIDENCE_KINDS: Final[tuple[str, ...]] = (
    "communication",
    "testimony",
    "narrative",
    "knowledge",
    "artifact",
)
_LOG: Final[logging.Logger] = logging.getLogger("analysis.society_isolation")


class SocietyIsolationError(ValueError):
    """Fail-closed isolation-audit error with a stable reason code only."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class SocietyEvidenceEdge:
    """One detached evidence edge that may imply information transfer."""

    edge_id: str
    kind: str
    source_person_id: str
    target_person_id: str
    tick: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", require_stable_id("edge_id", self.edge_id))
        kind = require_stable_id("kind", self.kind)
        if kind not in SOCIETY_EVIDENCE_KINDS:
            raise SocietyIsolationError("unknown_evidence_kind")
        source = require_stable_id("source_person_id", self.source_person_id)
        target = require_stable_id("target_person_id", self.target_person_id)
        if source == target:
            raise SocietyIsolationError("self_edge_rejected")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "source_person_id", source)
        object.__setattr__(self, "target_person_id", target)
        object.__setattr__(self, "tick", require_exact_nonneg_int("tick", self.tick))


@dataclass(frozen=True, slots=True)
class SocietyJourneyRow:
    """One completed objective arrive-between-regions fact."""

    person_id: str
    origin_region_id: str
    destination_region_id: str
    arrival_tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "person_id", require_stable_id("person_id", self.person_id)
        )
        origin = require_stable_id("origin_region_id", self.origin_region_id)
        destination = require_stable_id(
            "destination_region_id", self.destination_region_id
        )
        if origin == destination:
            raise SocietyIsolationError("same_region_journey")
        object.__setattr__(self, "origin_region_id", origin)
        object.__setattr__(self, "destination_region_id", destination)
        object.__setattr__(
            self,
            "arrival_tick",
            require_exact_nonneg_int("arrival_tick", self.arrival_tick),
        )


@dataclass(frozen=True, slots=True)
class SocietyIsolationRow:
    """Audit outcome for one cross-community evidence edge."""

    edge_id: str
    kind: str
    status: str
    reason_code: str

    def __post_init__(self) -> None:
        for name in ("edge_id", "kind", "status", "reason_code"):
            object.__setattr__(self, name, require_stable_id(name, getattr(self, name)))
        if self.status not in {"journey_explained", "unexplained"}:
            raise SocietyIsolationError("invalid_audit_status")


@dataclass(frozen=True, slots=True)
class SocietyIsolationResult:
    """Audit rows and explicit counts; unexplained is a finding."""

    rows: tuple[SocietyIsolationRow, ...]
    coverage: MetricCoverage

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "rows",
            tuple(sorted(self.rows, key=lambda row: (row.edge_id, row.kind))),
        )
        if type(self.coverage) is not MetricCoverage:
            raise SocietyIsolationError("invalid_coverage")

    @property
    def explained_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "journey_explained")

    @property
    def unexplained_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "unexplained")

    def kind_counts(self) -> dict[str, int]:
        counts = Counter(row.kind for row in self.rows)
        return {kind: counts.get(kind, 0) for kind in SOCIETY_EVIDENCE_KINDS}


def _journey_explains(
    edge: SocietyEvidenceEdge,
    source_regions: frozenset[str],
    target_regions: frozenset[str],
    journeys: Sequence[SocietyJourneyRow],
) -> bool:
    """True when any completed arrival between the communities precedes the edge."""
    for journey in journeys:
        if journey.arrival_tick > edge.tick:
            continue
        if (
            journey.origin_region_id in target_regions
            and journey.destination_region_id in source_regions
        ) or (
            journey.origin_region_id in source_regions
            and journey.destination_region_id in target_regions
        ):
            return True
    return False


def compute_society_isolation(
    communities: Sequence[CandidateCommunityRow],
    cross_edges: Sequence[SocietyEvidenceEdge],
    journeys: Sequence[SocietyJourneyRow],
) -> SocietyIsolationResult:
    """Classify every cross-community evidence edge against arrival evidence."""
    if isinstance(communities, (str, bytes)) or not isinstance(communities, Sequence):
        raise SocietyIsolationError("invalid_communities")
    community_rows = tuple(communities)
    if any(type(item) is not CandidateCommunityRow for item in community_rows):
        raise SocietyIsolationError("invalid_communities")
    owner_of: dict[str, str] = {}
    regions_of: dict[str, frozenset[str]] = {}
    for community in community_rows:
        regions = frozenset(community.residence_region_ids)
        regions_of[community.community_id] = regions
        for person in community.person_ids:
            if person in owner_of:
                raise SocietyIsolationError("duplicate_person_across_communities")
            owner_of[person] = community.community_id

    journeys_by_person: dict[str, list[SocietyJourneyRow]] = {}
    for journey in journeys:
        if type(journey) is not SocietyJourneyRow:
            raise SocietyIsolationError("invalid_journey_row")
        journeys_by_person.setdefault(journey.person_id, []).append(journey)
    for rows in journeys_by_person.values():
        rows.sort(key=lambda item: (item.arrival_tick, item.destination_region_id))

    audit: list[SocietyIsolationRow] = []
    seen_edges: set[str] = set()
    for edge in cross_edges:
        if type(edge) is not SocietyEvidenceEdge:
            raise SocietyIsolationError("invalid_evidence_edge")
        if edge.edge_id in seen_edges:
            raise SocietyIsolationError("duplicate_edge_id")
        seen_edges.add(edge.edge_id)
        source_community = owner_of.get(edge.source_person_id)
        target_community = owner_of.get(edge.target_person_id)
        if (
            source_community is None
            or target_community is None
            or source_community == target_community
        ):
            continue
        source_regions = regions_of.get(source_community, frozenset())
        target_regions = regions_of.get(target_community, frozenset())
        if not source_regions or not target_regions:
            audit.append(
                SocietyIsolationRow(
                    edge_id=edge.edge_id,
                    kind=edge.kind,
                    status="unexplained",
                    reason_code="missing_region_linkage",
                )
            )
            continue
        if _journey_explains(edge, source_regions, target_regions, journeys):
            audit.append(
                SocietyIsolationRow(
                    edge_id=edge.edge_id,
                    kind=edge.kind,
                    status="journey_explained",
                    reason_code="arrival_precedes_edge",
                )
            )
            continue
        reason = "no_journey_evidence" if not journeys_by_person else "no_prior_arrival"
        audit.append(
            SocietyIsolationRow(
                edge_id=edge.edge_id,
                kind=edge.kind,
                status="unexplained",
                reason_code=reason,
            )
        )

    expected = len(audit)
    ratio = 1.0 if expected else None
    result = SocietyIsolationResult(
        rows=tuple(audit),
        coverage=MetricCoverage(
            observed=expected,
            expected=expected,
            ratio=(
                quantize_float(require_finite(ratio)) if ratio is not None else None
            ),
        ),
    )
    _LOG.info(
        "society_isolation_audit explained=%s unexplained=%s cross_edges=%s",
        result.explained_count,
        result.unexplained_count,
        expected,
    )
    if result.unexplained_count:
        _LOG.warning(
            "society_isolation_unexplained count=%s reason_code=unexplained_transfer",
            result.unexplained_count,
        )
    return result


def compute_society_isolation_metric(
    result: SocietyIsolationResult,
    *,
    run_id: str,
    input_revision: str,
    community_count: int,
) -> MetricDocument:
    """Pin one isolation-audit document; unexplained counts are findings."""
    if type(result) is not SocietyIsolationResult:
        raise SocietyIsolationError("invalid_isolation_result")
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    community_count = require_exact_nonneg_int("community_count", community_count)
    spec = metric_specification(MetricFamilyId.SOCIETY_ISOLATION)
    counts = result.kind_counts()
    values: dict[str, object] = {
        "community_count": community_count,
        "cross_edge_count": len(result.rows),
        "explained_count": result.explained_count,
        "unexplained_count": result.unexplained_count,
    }
    for kind in SOCIETY_EVIDENCE_KINDS:
        values[f"{kind}_count"] = counts[kind]
    if not result.rows:
        availability = MetricAvailability.ABSENT
    elif result.unexplained_count:
        availability = MetricAvailability.PARTIAL
    else:
        availability = MetricAvailability.PRESENT
    _LOG.debug(
        "society_isolation_document family_id=%s availability=%s "
        "explained=%s unexplained=%s",
        spec.family_id.value,
        availability.value,
        result.explained_count,
        result.unexplained_count,
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
        values=values,
        provenance=MetricProvenance(
            source_kind="society_isolation",
            source_ids=(),
            notes_code=("unexplained_edges" if result.unexplained_count else "ok"),
        ),
    )
