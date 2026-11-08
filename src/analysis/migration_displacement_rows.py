# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Harvest row contracts and owner-row ingestion for migration displacement.

Rows are token-only. Owner export rows stay subjective (cause and route rows);
objective movement rows come from committed events; waves, clusters, outcomes,
lineage, and alignment are researcher-only analytical rows. Nothing here feeds
cognition, prompts, memory, or world state, and this module imports no
cognition, runtime, experiments, API, persistence, or observer module.

The detection, identity, and alignment modules are imported lazily inside the
harvest function to avoid a module cycle.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from analysis.migration_displacement_events import (
    MigrationIntegrationEvidenceRow,
    MigrationMovementRow,
)
from analysis.migration_displacement_policy import (
    MigrationDisplacementAnalysisPolicy,
)

__all__ = [
    "CAUSE_KINDS",
    "CAUSE_SOURCES",
    "CAUSE_STATUSES",
    "MIGRATION_OWNER_FAMILIES",
    "MigrationAlignmentRow",
    "MigrationCandidateRow",
    "MigrationCauseRow",
    "MigrationClusterRow",
    "MigrationDisplacementHarvestRows",
    "MigrationLineageRow",
    "MigrationOutcomeRow",
    "MigrationRouteRow",
    "MigrationWaveRow",
    "harvest_migration_displacement_rows",
    "migration_rows_summary",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.migration_displacement.rows")

_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_COVERAGES: Final[frozenset[str]] = frozenset({"complete", "partial", "missing"})
NONE_TOKEN: Final[str] = "none"

MIGRATION_OWNER_FAMILIES: Final[tuple[str, ...]] = (
    "cause",
    "cluster",
    "integration",
    "intent",
    "notice",
    "route",
    "wave",
)
CAUSE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "resource_scarcity",
        "environmental_hazard",
        "conflict",
        "opportunity",
        "social_network",
        "institution",
        "unknown",
    }
)
CAUSE_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "direct_observation",
        "own_need",
        "own_journey",
        "own_relationship",
        "own_kinship",
        "organization_belief",
        "institution_belief",
        "formal_rule_belief",
        "dispute_belief",
        "evidence_belief",
        "diplomacy_belief",
        "conflict_belief",
        "border_belief",
        "testimony",
        "inference",
        "unknown",
    }
)
CAUSE_STATUSES: Final[frozenset[str]] = frozenset(
    {"active", "superseded", "contradicted", "expired", "unknown"}
)
_ROUTE_BASES: Final[frozenset[str]] = frozenset(
    {
        "direct_observation",
        "own_journey",
        "testimony",
        "inference",
        "unresolved",
        "unknown",
    }
)
_ROUTE_STATUSES: Final[frozenset[str]] = frozenset(
    {"open", "blocked_belief", "unresolved", "expired", "unknown"}
)
_CANDIDATE_KINDS: Final[frozenset[str]] = frozenset({"wave", "cluster", "outcome"})
_CLUSTER_BASES: Final[frozenset[str]] = frozenset(
    {"kinship", "organization", "co_movement", "communication", "relationship"}
)
_DISPLACEMENT_CLASSES: Final[frozenset[str]] = frozenset(
    {"not_displacement_like", "displacement_like", "mixed", "unknown"}
)
_INTEGRATION_CLASSES: Final[frozenset[str]] = frozenset(
    {"settled", "transient", "returned", "onward", "unknown"}
)
_LINEAGE_RELATIONS: Final[frozenset[str]] = frozenset(
    {"continued", "transformed", "split", "merge", "dissolved", "emerged"}
)
_PARTIAL_NOTICES: Final[frozenset[str]] = frozenset(
    {"truncated", "malformed_frame", "ledger_cap_reached"}
)
_ALIGNMENTS: Final[frozenset[str]] = frozenset(
    {"consistent", "unresolved", "inconsistent", "not_applicable"}
)


def _token(field_name: str, value: object) -> str:
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        raise ValueError(f"migration_rows: {field_name}")
    return value


def _tokens(field_name: str, value: object) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise ValueError(f"migration_rows: {field_name}")
    return tuple(_token(field_name, item) for item in value)


def _tick(field_name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"migration_rows: {field_name}")
    return value


def _count(field_name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"migration_rows: {field_name}")
    return value


def _closed(field_name: str, value: object, allowed: frozenset[str]) -> str:
    if type(value) is not str or value not in allowed:
        raise ValueError(f"migration_rows: {field_name}")
    return value


def _unit(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"migration_rows: {field_name}")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"migration_rows: {field_name}")
    return number


def _pairs(field_name: str, value: object) -> tuple[tuple[str, int], ...]:
    if type(value) is not tuple:
        raise ValueError(f"migration_rows: {field_name}")
    out: list[tuple[str, int]] = []
    for item in value:
        if type(item) is not tuple or len(item) != 2:
            raise ValueError(f"migration_rows: {field_name}")
        label, number = item
        if type(label) is not str or not label:
            raise ValueError(f"migration_rows: {field_name}")
        out.append((label, _count(field_name, number)))
    if out != sorted(out):
        raise ValueError(f"migration_rows: {field_name}")
    return tuple(out)


@dataclass(frozen=True, slots=True)
class MigrationCauseRow:
    """Subjective owner cause belief. Never an objective cause or a verdict."""

    owner_token: str
    cause_token: str
    cause_kind: str
    source_kind: str
    anchor_token: str
    lineage_refs: tuple[str, ...]
    confidence: float
    tick: int
    status: str
    coverage: str = "resolved"

    def __post_init__(self) -> None:
        _token("owner_token", self.owner_token)
        _token("cause_token", self.cause_token)
        _closed("cause_kind", self.cause_kind, CAUSE_KINDS)
        _closed("source_kind", self.source_kind, CAUSE_SOURCES)
        if self.anchor_token != "":
            _token("anchor_token", self.anchor_token)
        _tokens("lineage_refs", self.lineage_refs)
        if list(self.lineage_refs) != sorted(set(self.lineage_refs)):
            raise ValueError("migration_rows: lineage_refs")
        _unit("confidence", self.confidence)
        _tick("tick", self.tick)
        _closed("status", self.status, CAUSE_STATUSES)
        _closed(
            "coverage",
            self.coverage,
            frozenset({"resolved", "unresolved", "unknown"}),
        )


@dataclass(frozen=True, slots=True)
class MigrationRouteRow:
    """Subjective owner route belief."""

    owner_token: str
    route_token: str
    origin_token: str
    destination_token: str
    route_tokens: tuple[str, ...]
    observed_duration_ticks: int
    fatigue_cost: float
    basis: str
    status: str
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _token("owner_token", self.owner_token)
        _token("route_token", self.route_token)
        _token("origin_token", self.origin_token)
        _token("destination_token", self.destination_token)
        _tokens("route_tokens", self.route_tokens)
        _count("observed_duration_ticks", self.observed_duration_ticks)
        if isinstance(self.fatigue_cost, bool) or not isinstance(
            self.fatigue_cost, (int, float)
        ):
            raise ValueError("migration_rows: fatigue_cost")
        if float(self.fatigue_cost) < 0.0:
            raise ValueError("migration_rows: fatigue_cost")
        _closed("basis", self.basis, _ROUTE_BASES)
        _closed("status", self.status, _ROUTE_STATUSES)
        first = _tick("first_tick", self.first_tick)
        if _tick("last_tick", self.last_tick) < first:
            raise ValueError("migration_rows: last_tick")


@dataclass(frozen=True, slots=True)
class MigrationClusterRow:
    """Analytical social cluster candidate. Not a world or knowledge object."""

    cluster_token: str
    member_tokens: tuple[str, ...]
    basis_counts: tuple[tuple[str, int], ...]
    coverage: str
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _token("cluster_token", self.cluster_token)
        _tokens("member_tokens", self.member_tokens)
        counts = _pairs("basis_counts", self.basis_counts)
        for label, _number in counts:
            _closed("basis_counts", label, _CLUSTER_BASES)
        _closed("coverage", self.coverage, _COVERAGES)
        first = _tick("first_tick", self.first_tick)
        if _tick("last_tick", self.last_tick) < first:
            raise ValueError("migration_rows: last_tick")


@dataclass(frozen=True, slots=True)
class MigrationWaveRow:
    """Analytical wave candidate with a researcher-only displacement label."""

    wave_token: str
    origin_token: str
    destination_token: str
    participant_tokens: tuple[str, ...]
    route_tokens: tuple[str, ...]
    start_tick: int
    end_tick: int
    cause_support_counts: tuple[tuple[str, int], ...]
    displacement_classification: str
    displacement_bases: tuple[str, ...]
    independent_cause_count: int
    cluster_tokens: tuple[str, ...]
    coverage: str
    same_root_suppressed_count: int = 0

    def __post_init__(self) -> None:
        _token("wave_token", self.wave_token)
        _token("origin_token", self.origin_token)
        _token("destination_token", self.destination_token)
        _tokens("participant_tokens", self.participant_tokens)
        _tokens("route_tokens", self.route_tokens)
        start = _tick("start_tick", self.start_tick)
        if _tick("end_tick", self.end_tick) < start:
            raise ValueError("migration_rows: end_tick")
        counts = _pairs("cause_support_counts", self.cause_support_counts)
        for label, _number in counts:
            _closed("cause_support_counts", label, CAUSE_KINDS)
        _closed(
            "displacement_classification",
            self.displacement_classification,
            _DISPLACEMENT_CLASSES,
        )
        if type(self.displacement_bases) is not tuple:
            raise ValueError("migration_rows: displacement_bases")
        _count("independent_cause_count", self.independent_cause_count)
        _count("same_root_suppressed_count", self.same_root_suppressed_count)
        _tokens("cluster_tokens", self.cluster_tokens)
        _closed("coverage", self.coverage, _COVERAGES)


@dataclass(frozen=True, slots=True)
class MigrationOutcomeRow:
    """Descriptive integration outcome label with counts. Never a score."""

    outcome_token: str
    participant_token: str
    destination_token: str
    residence_ticks: int
    access_evidence_count: int
    participation_evidence_count: int
    relationship_evidence_count: int
    conflict_evidence_count: int
    classification: str
    coverage: str
    censored: bool

    def __post_init__(self) -> None:
        _token("outcome_token", self.outcome_token)
        _token("participant_token", self.participant_token)
        _token("destination_token", self.destination_token)
        for name in (
            "residence_ticks",
            "access_evidence_count",
            "participation_evidence_count",
            "relationship_evidence_count",
            "conflict_evidence_count",
        ):
            _count(name, getattr(self, name))
        _closed("classification", self.classification, _INTEGRATION_CLASSES)
        _closed("coverage", self.coverage, _COVERAGES)
        if type(self.censored) is not bool:
            raise ValueError("migration_rows: censored")


@dataclass(frozen=True, slots=True)
class MigrationLineageRow:
    """Forward-only lineage edge between analytical candidates."""

    candidate_token: str
    previous_token: str
    relation: str
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        _token("candidate_token", self.candidate_token)
        _token("previous_token", self.previous_token)
        _closed("relation", self.relation, _LINEAGE_RELATIONS)
        first = _tick("first_tick", self.first_tick)
        if _tick("last_tick", self.last_tick) < first:
            raise ValueError("migration_rows: last_tick")


@dataclass(frozen=True, slots=True)
class MigrationAlignmentRow:
    """Researcher-only owner-versus-analysis alignment label."""

    owner_token: str
    candidate_token: str
    alignment: str
    basis: str

    def __post_init__(self) -> None:
        _token("owner_token", self.owner_token)
        _token("candidate_token", self.candidate_token)
        _closed("alignment", self.alignment, _ALIGNMENTS)
        _token("basis", self.basis)


@dataclass(frozen=True, slots=True)
class MigrationCandidateRow:
    """Content-addressed ``mig-`` analytical candidate summary."""

    candidate_token: str
    kind: str
    status: str
    first_tick: int
    last_tick: int
    member_count: int
    origin_token: str
    destination_token: str
    classification: str
    coverage: str
    member_tokens: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.candidate_token) is not str or not self.candidate_token.startswith(
            "mig-"
        ):
            raise ValueError("migration_identity: candidate_token")
        try:
            _token("candidate_token", self.candidate_token)
        except ValueError as exc:
            raise ValueError("migration_identity: candidate_token") from exc
        _closed("kind", self.kind, _CANDIDATE_KINDS)
        _closed("status", self.status, frozenset({"observed", "partial"}))
        first = _tick("first_tick", self.first_tick)
        if _tick("last_tick", self.last_tick) < first:
            raise ValueError("migration_rows: last_tick")
        _count("member_count", self.member_count)
        _token("origin_token", self.origin_token)
        _token("destination_token", self.destination_token)
        if type(self.classification) is not str or not self.classification:
            raise ValueError("migration_rows: classification")
        _closed("coverage", self.coverage, _COVERAGES)
        _tokens("member_tokens", self.member_tokens)


@dataclass(frozen=True, slots=True)
class MigrationDisplacementHarvestRows:
    """Normalized, deterministic harvest with the four layers kept separate."""

    movements: tuple[MigrationMovementRow, ...] = ()
    routes: tuple[MigrationRouteRow, ...] = ()
    causes: tuple[MigrationCauseRow, ...] = ()
    clusters: tuple[MigrationClusterRow, ...] = ()
    waves: tuple[MigrationWaveRow, ...] = ()
    outcomes: tuple[MigrationOutcomeRow, ...] = ()
    lineage: tuple[MigrationLineageRow, ...] = ()
    alignment: tuple[MigrationAlignmentRow, ...] = ()
    coverage: str = "missing"
    integration_evidence: tuple[MigrationIntegrationEvidenceRow, ...] = ()
    candidates: tuple[MigrationCandidateRow, ...] = ()
    owner_tokens: tuple[str, ...] = ()
    notices: tuple[str, ...] = ()
    joins: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _closed("coverage", self.coverage, _COVERAGES)
        for name in (
            "movements",
            "routes",
            "causes",
            "clusters",
            "waves",
            "outcomes",
            "lineage",
            "alignment",
            "integration_evidence",
            "candidates",
            "owner_tokens",
            "notices",
            "joins",
        ):
            if type(getattr(self, name)) is not tuple:
                raise ValueError(f"migration_rows: {name}")


def _attr(row: object, name: str, default: object = None) -> object:
    return getattr(row, name, default)


def _flatten(owner_rows: Sequence[object]) -> list[object]:
    out: list[object] = []
    for item in owner_rows:
        if isinstance(item, (tuple, list)):
            out.extend(item)
        else:
            out.append(item)
    return out


def _owner_rows_to_subjective(
    rows: Sequence[object],
    *,
    max_rows: int,
) -> tuple[
    tuple[MigrationCauseRow, ...],
    tuple[MigrationRouteRow, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    causes: list[MigrationCauseRow] = []
    routes: list[MigrationRouteRow] = []
    owners: set[str] = set()
    notices: set[str] = set()
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        family = _attr(row, "family")
        if type(family) is not str or family not in MIGRATION_OWNER_FAMILIES:
            raise TypeError("exported row has an unsupported family")
        owner = _token("owner_token", _attr(row, "owner_token"))
        row_token = _token("row_token", _attr(row, "row_token"))
        key = (owner, family, row_token)
        if key in seen:
            raise ValueError("migration_harvest: duplicate_row")
        seen.add(key)
        owners.add(owner)
        status = _attr(row, "status")
        status_text = status.replace("-", "_") if type(status) is str else ""
        if family == "notice":
            if (
                not status_text
                or _TOKEN_RE.fullmatch(status_text.replace("_", "-")) is None
            ):
                raise ValueError("migration_rows: notice")
            notices.add(status_text)
            continue
        for name in ("origin_token", "destination_token"):
            _token(name, _attr(row, name))
        for name in ("route_tokens", "cause_tokens", "cluster_tokens"):
            _tokens(name, _attr(row, name))
        first = _tick("first_tick", _attr(row, "first_tick"))
        last = _tick("last_tick", _attr(row, "last_tick"))
        _closed(
            "coverage",
            _attr(row, "coverage"),
            frozenset({"resolved", "unresolved", "unknown"}),
        )
        if family == "cause":
            cause_tokens = _tokens("cause_tokens", _attr(row, "cause_tokens"))
            if len(cause_tokens) != 1:
                raise ValueError("migration_harvest: cause_kind")
            source = _attr(row, "source_kind", "unknown")
            anchor = _attr(row, "anchor_token", "")
            lineage = _attr(row, "lineage_refs", ())
            causes.append(
                MigrationCauseRow(
                    owner_token=owner,
                    cause_token=row_token,
                    cause_kind=cause_tokens[0].replace("-", "_"),
                    source_kind=(
                        source.replace("-", "_") if type(source) is str else "unknown"
                    ),
                    anchor_token=("" if anchor in (None, "none") else str(anchor)),
                    lineage_refs=tuple(sorted(set(lineage)))
                    if isinstance(lineage, (tuple, list))
                    else (),
                    confidence=float(_attr(row, "confidence", 0.0)),  # type: ignore[arg-type]
                    tick=first,
                    status=status_text,
                    coverage=str(_attr(row, "coverage")),
                )
            )
        elif family == "route":
            coverage = str(_attr(row, "coverage"))
            routes.append(
                MigrationRouteRow(
                    owner_token=owner,
                    route_token=row_token,
                    origin_token=str(_attr(row, "origin_token")),
                    destination_token=str(_attr(row, "destination_token")),
                    route_tokens=tuple(_attr(row, "route_tokens")),  # type: ignore[arg-type]
                    observed_duration_ticks=0,
                    fatigue_cost=0.0,
                    basis="unresolved" if coverage == "unresolved" else "unknown",
                    status=status_text,
                    first_tick=first,
                    last_tick=last,
                )
            )
    truncated = False
    if len(causes) > max_rows:
        causes = causes[:max_rows]
        truncated = True
    if len(routes) > max_rows:
        routes = routes[:max_rows]
        truncated = True
    if truncated:
        notices.add("truncated")
    causes.sort(key=lambda item: (item.owner_token, item.tick, item.cause_token))
    routes.sort(key=lambda item: (item.owner_token, item.first_tick, item.route_token))
    return tuple(causes), tuple(routes), tuple(sorted(owners)), tuple(sorted(notices))


def _merge_evidence(
    evidence: Sequence[MigrationIntegrationEvidenceRow],
) -> tuple[MigrationIntegrationEvidenceRow, ...]:
    merged: dict[tuple[str, str, str], MigrationIntegrationEvidenceRow] = {}
    for item in evidence:
        if type(item) is not MigrationIntegrationEvidenceRow:
            raise TypeError("integration_evidence entries must be evidence rows")
        key = (item.participant_token, item.destination_token, item.domain)
        old = merged.get(key)
        if old is None or item.evidence_count > old.evidence_count:
            merged[key] = item
    return tuple(merged[key] for key in sorted(merged))


def _validate_harvest(rows: MigrationDisplacementHarvestRows) -> None:
    seen: set[tuple[str, str]] = set()
    for cause in rows.causes:
        key = (cause.owner_token, cause.cause_token)
        if key in seen:
            raise ValueError("migration_harvest: duplicate_row")
        seen.add(key)
    wave_tokens = [item.wave_token for item in rows.waves]
    if len(set(wave_tokens)) != len(wave_tokens):
        raise ValueError("migration_harvest: duplicate_row")


def _normalized(
    rows: MigrationDisplacementHarvestRows,
) -> MigrationDisplacementHarvestRows:
    _validate_harvest(rows)
    return replace(
        rows,
        movements=tuple(
            sorted(
                rows.movements,
                key=lambda item: (
                    item.start_tick,
                    item.participant_token,
                    item.destination_token,
                    item.origin_token,
                    item.relocation_kind,
                ),
            )
        ),
        routes=tuple(
            sorted(
                rows.routes,
                key=lambda item: (item.owner_token, item.first_tick, item.route_token),
            )
        ),
        causes=tuple(
            sorted(
                rows.causes,
                key=lambda item: (item.owner_token, item.tick, item.cause_token),
            )
        ),
        clusters=tuple(sorted(rows.clusters, key=lambda item: item.cluster_token)),
        waves=tuple(sorted(rows.waves, key=lambda item: item.wave_token)),
        outcomes=tuple(sorted(rows.outcomes, key=lambda item: item.outcome_token)),
        lineage=tuple(
            sorted(
                rows.lineage,
                key=lambda item: (
                    item.first_tick,
                    item.candidate_token,
                    item.previous_token,
                ),
            )
        ),
        alignment=tuple(
            sorted(
                rows.alignment,
                key=lambda item: (item.owner_token, item.candidate_token),
            )
        ),
        integration_evidence=tuple(
            sorted(
                rows.integration_evidence,
                key=lambda item: (
                    item.participant_token,
                    item.destination_token,
                    item.domain,
                ),
            )
        ),
        candidates=tuple(
            sorted(rows.candidates, key=lambda item: item.candidate_token)
        ),
    )


def harvest_migration_displacement_rows(
    owner_rows: object,
    movements: Sequence[MigrationMovementRow] = (),
    integration_evidence: Sequence[MigrationIntegrationEvidenceRow] = (),
    *,
    kinship_pairs: Sequence[tuple[str, str]] = (),
    organization_pairs: Sequence[tuple[str, str]] = (),
    communication_pairs: Sequence[tuple[str, str]] = (),
    previous_candidates: Sequence[MigrationCandidateRow] = (),
    org_tokens: Mapping[str, Sequence[str]] | None = None,
    msoc_tokens: Mapping[str, Sequence[str]] | None = None,
    policy: MigrationDisplacementAnalysisPolicy,
) -> MigrationDisplacementHarvestRows:
    """Project owner export rows and objective rows into the four layers.

    An already-normalized ``MigrationDisplacementHarvestRows`` is returned
    through the duplicate check and deterministic ordering without
    re-projecting raw ledgers, so a collector harvest and the metric service
    stay idempotent.
    """
    if type(policy) is not MigrationDisplacementAnalysisPolicy:
        raise TypeError("policy must be MigrationDisplacementAnalysisPolicy")
    if type(owner_rows) is MigrationDisplacementHarvestRows:
        _LOG.debug("migration_harvest_idempotent")
        return _normalized(owner_rows)
    from analysis.migration_displacement_alignment import (
        align_migration_interpretations,
    )
    from analysis.migration_displacement_detection import (
        classify_integration_outcomes,
        detect_migration_clusters,
        detect_migration_waves,
    )
    from analysis.migration_displacement_identity import (
        join_read_only_identities,
        link_migration_lineage,
        migration_candidates_from_rows,
    )

    if owner_rows is None:
        owner_rows = ()
    if isinstance(owner_rows, (str, bytes, Mapping)) or not isinstance(
        owner_rows, Sequence
    ):
        raise TypeError("owner_rows must be a sequence")
    for name, value in (
        ("movements", movements),
        ("integration_evidence", integration_evidence),
    ):
        if isinstance(value, (str, bytes, Mapping)) or not isinstance(value, Sequence):
            raise TypeError(f"{name} must be a sequence")
    if any(type(item) is not MigrationMovementRow for item in movements):
        raise TypeError("movements entries must be MigrationMovementRow")
    flat = _flatten(owner_rows)
    causes, routes, owners, notices = _owner_rows_to_subjective(
        flat, max_rows=policy.max_rows_per_family
    )
    if not flat:
        _LOG.warning("migration_harvest_missing_owner_rows")
    ordered_movements = tuple(
        sorted(
            movements,
            key=lambda item: (
                item.start_tick,
                item.participant_token,
                item.destination_token,
                item.origin_token,
                item.relocation_kind,
            ),
        )
    )
    evidence = _merge_evidence(integration_evidence)
    clusters = detect_migration_clusters(
        ordered_movements,
        kinship_pairs,
        organization_pairs,
        communication_pairs,
        policy,
    )
    waves = detect_migration_waves(ordered_movements, causes, clusters, policy)
    outcomes = classify_integration_outcomes(
        ordered_movements, evidence, policy, waves=waves
    )
    candidates = migration_candidates_from_rows(waves, clusters, outcomes)
    lineage = link_migration_lineage(previous_candidates, candidates, policy)
    alignment = align_migration_interpretations(causes, waves, outcomes)
    joins = join_read_only_identities(candidates, org_tokens or {}, msoc_tokens or {})
    if not flat:
        coverage = "missing"
    elif (
        not ordered_movements
        or any(
            item in _PARTIAL_NOTICES or item.endswith("_cap_reached")
            for item in notices
        )
        or any(item.coverage != "complete" for item in ordered_movements)
    ):
        coverage = "partial"
    else:
        coverage = "complete"
    result = MigrationDisplacementHarvestRows(
        movements=ordered_movements,
        routes=routes,
        causes=causes,
        clusters=clusters,
        waves=waves,
        outcomes=outcomes,
        lineage=lineage,
        alignment=alignment,
        coverage=coverage,
        integration_evidence=evidence,
        candidates=candidates,
        owner_tokens=owners,
        notices=notices,
        joins=joins,
    )
    _validate_harvest(result)
    _LOG.debug(
        "migration_harvest movements=%s causes=%s waves=%s coverage=%s",
        len(result.movements),
        len(result.causes),
        len(result.waves),
        result.coverage,
    )
    return result


def migration_rows_summary(rows: MigrationDisplacementHarvestRows) -> Mapping[str, int]:
    """Counts per layer; metadata only."""
    if type(rows) is not MigrationDisplacementHarvestRows:
        raise TypeError("rows must be MigrationDisplacementHarvestRows")
    return {
        "movements": len(rows.movements),
        "routes": len(rows.routes),
        "causes": len(rows.causes),
        "clusters": len(rows.clusters),
        "waves": len(rows.waves),
        "outcomes": len(rows.outcomes),
        "lineage": len(rows.lineage),
        "alignment": len(rows.alignment),
    }
