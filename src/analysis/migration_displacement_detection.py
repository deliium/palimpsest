"""Deterministic wave, displacement-like, cluster, and integration detection.

Everything here is a pure, researcher-only function of token rows. A wave is an
analytical candidate over independent committed movements, never a world
object, and no participant shares knowledge implicitly. Classification labels
are closed and describe causal evidence with coverage; the closed vocabularies
below are the only labels this module can emit. This module imports no
cognition, runtime, experiments, API, persistence, or observer module.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from analysis.migration_displacement_contract import analysis_migration_candidate_id
from analysis.migration_displacement_events import (
    MigrationIntegrationEvidenceRow,
    MigrationMovementRow,
)
from analysis.migration_displacement_policy import MigrationDisplacementAnalysisPolicy
from analysis.migration_displacement_rows import (
    MigrationCauseRow,
    MigrationClusterRow,
    MigrationOutcomeRow,
    MigrationWaveRow,
)

__all__ = [
    "DISPLACEMENT_BASES",
    "DISPLACEMENT_CLASSIFICATIONS",
    "INTEGRATION_CLASSIFICATIONS",
    "OPPORTUNITY_BASES",
    "MigrationDisplacementResult",
    "classify_displacement",
    "classify_integration_outcomes",
    "detect_migration_clusters",
    "detect_migration_waves",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.migration_displacement.detection"
)

DISPLACEMENT_CLASSIFICATIONS: Final[frozenset[str]] = frozenset(
    {"not_displacement_like", "displacement_like", "mixed", "unknown"}
)
DISPLACEMENT_BASES: Final[frozenset[str]] = frozenset(
    {
        "immediate_threat",
        "resource_deprivation",
        "environmental_hazard",
        "coercion",
        "route_denial",
        "institutional_exclusion",
        "unknown",
    }
)
OPPORTUNITY_BASES: Final[frozenset[str]] = frozenset(
    {"opportunity", "social_network", "institution"}
)
INTEGRATION_CLASSIFICATIONS: Final[frozenset[str]] = frozenset(
    {"settled", "transient", "returned", "onward", "unknown"}
)

# Closed anchor classes. An anchor token is a class or ``<class>-<opaque suffix>``.
_THREAT_ANCHORS: Final[frozenset[str]] = frozenset({"attack", "flee", "death"})
_COERCION_ANCHORS: Final[frozenset[str]] = frozenset({"threat", "coercion"})
_ROUTE_DENIAL_ANCHORS: Final[frozenset[str]] = frozenset(
    {"blocked-route", "denied-route", "route-blocked", "route-denied"}
)
_DEPRIVATION_ANCHORS: Final[frozenset[str]] = frozenset({"need", "depletion"})
_EXCLUSION_ANCHORS: Final[frozenset[str]] = frozenset(
    {"rule-denial", "office-denial", "participation-denial"}
)
_OPPORTUNITY_KINDS: Final[dict[str, str]] = {
    "opportunity": "opportunity",
    "social_network": "social_network",
}

_ACCESS_DOMAINS: Final[frozenset[str]] = frozenset({"resource_access"})
_PARTICIPATION_DOMAINS: Final[frozenset[str]] = frozenset(
    {"organization_participation", "institution_participation"}
)


def _require_policy(policy: object) -> MigrationDisplacementAnalysisPolicy:
    if type(policy) is not MigrationDisplacementAnalysisPolicy:
        raise ValueError("migration_detection: invalid_policy")
    for name in (
        "wave_window_ticks",
        "max_wave_gap_ticks",
        "min_wave_participants",
        "min_wave_distinct_origins",
        "min_wave_route_overlap",
        "cause_window_ticks",
        "integration_window_ticks",
        "min_residence_ticks",
        "cluster_window_ticks",
        "min_cluster_members",
        "max_candidates_per_run",
    ):
        value = getattr(policy, name)
        if type(value) is not int or value < 1:
            raise ValueError(f"migration_detection: {name}")
    return policy


def _anchor_is(anchor: str, classes: frozenset[str]) -> bool:
    if not anchor:
        return False
    return any(anchor == item or anchor.startswith(f"{item}-") for item in classes)


@dataclass(frozen=True, slots=True)
class MigrationDisplacementResult:
    """Researcher-only classification of one wave from independent causes."""

    classification: str
    displacement_bases: tuple[str, ...]
    opportunity_bases: tuple[str, ...]
    independent_cause_count: int
    cause_support_counts: tuple[tuple[str, int], ...]
    same_root_suppressed_count: int


def _base_for(row: MigrationCauseRow) -> tuple[str, str] | None:
    """Return exactly one ``(group, base)`` for a cause row, or ``None``."""
    kind = row.cause_kind
    anchor = row.anchor_token
    if kind == "environmental_hazard":
        return "displacement", "environmental_hazard"
    if kind == "conflict":
        if _anchor_is(anchor, _THREAT_ANCHORS):
            return "displacement", "immediate_threat"
        if _anchor_is(anchor, _COERCION_ANCHORS):
            return "displacement", "coercion"
        if _anchor_is(anchor, _ROUTE_DENIAL_ANCHORS):
            return "displacement", "route_denial"
        return None
    if kind == "resource_scarcity":
        if _anchor_is(anchor, _DEPRIVATION_ANCHORS):
            return "displacement", "resource_deprivation"
        return None
    if kind == "institution":
        if _anchor_is(anchor, _EXCLUSION_ANCHORS):
            return "displacement", "institutional_exclusion"
        return "opportunity", "institution"
    if kind in _OPPORTUNITY_KINDS:
        return "opportunity", _OPPORTUNITY_KINDS[kind]
    return None


def classify_displacement(
    wave: MigrationWaveRow,
    causes: Sequence[MigrationCauseRow],
    policy: MigrationDisplacementAnalysisPolicy,
) -> MigrationDisplacementResult:
    """Classify one wave from independent owner cause evidence.

    Missing cause rows yield ``unknown``; a cause is never invented from
    movement or silence, and same-root testimony counts once.
    """
    resolved = _require_policy(policy)
    participants = set(wave.participant_tokens)
    low = wave.start_tick - resolved.cause_window_ticks
    high = wave.end_tick + resolved.cause_window_ticks
    usable = sorted(
        (
            row
            for row in causes
            if row.owner_token in participants
            and low <= row.tick <= high
            and row.status == "active"
            and row.cause_kind != "unknown"
        ),
        key=lambda row: (row.tick, row.owner_token, row.cause_token),
    )
    accepted: list[MigrationCauseRow] = []
    suppressed = 0
    for row in usable:
        duplicate = False
        for kept in accepted:
            if kept.cause_kind != row.cause_kind:
                continue
            same_owner = (
                kept.owner_token == row.owner_token
                and kept.anchor_token == row.anchor_token
            )
            same_root = bool(set(kept.lineage_refs) & set(row.lineage_refs))
            if same_owner or same_root:
                duplicate = True
                break
        if duplicate:
            suppressed += 1
        else:
            accepted.append(row)
    displacement: set[str] = set()
    opportunity: set[str] = set()
    displacement_rows = 0
    opportunity_rows = 0
    kind_counts: dict[str, int] = {}
    for row in accepted:
        kind_counts[row.cause_kind] = kind_counts.get(row.cause_kind, 0) + 1
        mapped = _base_for(row)
        if mapped is None:
            continue
        group, base = mapped
        if group == "displacement":
            displacement.add(base)
            displacement_rows += 1
        else:
            opportunity.add(base)
            opportunity_rows += 1
    has_displacement = displacement_rows >= max(
        resolved.displacement_min_independent_causes, 1
    )
    if (
        displacement_rows >= resolved.mixed_min_displacement_causes
        and opportunity_rows >= resolved.mixed_min_opportunity_causes
    ):
        label = "mixed"
    elif has_displacement:
        label = "displacement_like"
    elif opportunity_rows >= 1:
        label = "not_displacement_like"
    else:
        label = "unknown"
    return MigrationDisplacementResult(
        classification=label,
        displacement_bases=tuple(sorted(displacement)),
        opportunity_bases=tuple(sorted(opportunity)),
        independent_cause_count=len(accepted),
        cause_support_counts=tuple(sorted(kind_counts.items())),
        same_root_suppressed_count=suppressed,
    )


def _route_overlap(group: Sequence[MigrationMovementRow], destination: str) -> int:
    holders: dict[str, set[str]] = {}
    for row in group:
        tokens = {*row.route_tokens, row.origin_token}
        tokens.discard(destination)
        for token in tokens:
            holders.setdefault(token, set()).add(row.participant_token)
    return sum(1 for owners in holders.values() if len(owners) >= 2)


def _wave_groups(
    movements: Sequence[MigrationMovementRow],
    policy: MigrationDisplacementAnalysisPolicy,
) -> list[list[MigrationMovementRow]]:
    arrived = [row for row in movements if row.arrival_status == "arrived"]
    ordered = sorted(
        arrived,
        key=lambda row: (
            row.destination_token,
            row.start_tick,
            row.participant_token,
            row.origin_token,
        ),
    )
    groups: list[list[MigrationMovementRow]] = []
    current: list[MigrationMovementRow] = []
    for row in ordered:
        if current:
            same_destination = current[-1].destination_token == row.destination_token
            gap = row.start_tick - current[-1].start_tick
            span = row.start_tick - current[0].start_tick
            if (
                not same_destination
                or gap > policy.max_wave_gap_ticks
                or span > policy.wave_window_ticks
            ):
                groups.append(current)
                current = []
        current.append(row)
    if current:
        groups.append(current)
    return groups


def _ordered_tokens(routes: Sequence[tuple[str, ...]]) -> tuple[str, ...]:
    seen: list[str] = []
    for route in sorted(routes):
        for token in route:
            if token not in seen:
                seen.append(token)
    return tuple(seen)


def detect_migration_waves(
    movements: Sequence[MigrationMovementRow],
    causes: Sequence[MigrationCauseRow],
    clusters: Sequence[MigrationClusterRow],
    policy: MigrationDisplacementAnalysisPolicy,
) -> tuple[MigrationWaveRow, ...]:
    """Group independent committed movements into deterministic wave candidates."""
    resolved = _require_policy(policy)
    waves: list[MigrationWaveRow] = []
    for group in _wave_groups(movements, resolved):
        participants = sorted({row.participant_token for row in group})
        origins = sorted({row.origin_token for row in group})
        destination = group[0].destination_token
        if len(participants) < resolved.min_wave_participants:
            continue
        if len(origins) < resolved.min_wave_distinct_origins:
            continue
        if _route_overlap(group, destination) < resolved.min_wave_route_overlap:
            continue
        routes = [row.route_tokens for row in group]
        first = min(row.start_tick for row in group)
        material = "|".join(
            (
                destination,
                ",".join(participants),
                ",".join(origins),
                str(first),
                ";".join(sorted(",".join(route) for route in routes)),
            )
        )
        member_set = set(participants)
        cluster_tokens = tuple(
            sorted(
                item.cluster_token
                for item in clusters
                if len(member_set & set(item.member_tokens)) >= 2
            )
        )
        base = MigrationWaveRow(
            wave_token=analysis_migration_candidate_id("wave", material),
            origin_token=origins[0],
            destination_token=destination,
            participant_tokens=tuple(participants),
            route_tokens=_ordered_tokens(routes),
            start_tick=first,
            end_tick=max(row.end_tick for row in group),
            cause_support_counts=(),
            displacement_classification="unknown",
            displacement_bases=(),
            independent_cause_count=0,
            cluster_tokens=cluster_tokens,
            coverage=(
                "complete"
                if all(row.coverage == "complete" for row in group)
                else "partial"
            ),
        )
        result = classify_displacement(base, causes, resolved)
        waves.append(
            replace(
                base,
                cause_support_counts=result.cause_support_counts,
                displacement_classification=result.classification,
                displacement_bases=result.displacement_bases,
                independent_cause_count=result.independent_cause_count,
                same_root_suppressed_count=result.same_root_suppressed_count,
            )
        )
    waves.sort(key=lambda item: item.wave_token)
    if len(waves) > resolved.max_candidates_per_run:
        _LOG.warning(
            "migration_waves_truncated cap=%s", resolved.max_candidates_per_run
        )
        waves = waves[: resolved.max_candidates_per_run]
    _LOG.debug(
        "migration_waves movements=%s waves=%s displacement_like=%s mixed=%s "
        "unknown=%s",
        len(movements),
        len(waves),
        sum(
            1
            for item in waves
            if item.displacement_classification == "displacement_like"
        ),
        sum(1 for item in waves if item.displacement_classification == "mixed"),
        sum(1 for item in waves if item.displacement_classification == "unknown"),
    )
    return tuple(waves)


def _pair_edges(
    name: str, pairs: Sequence[tuple[str, str]], members: set[str]
) -> list[tuple[str, str, str]]:
    edges: list[tuple[str, str, str]] = []
    if isinstance(pairs, (str, bytes)) or not isinstance(pairs, Sequence):
        raise ValueError(f"migration_detection: {name}")
    for item in pairs:
        if type(item) is not tuple or len(item) != 2:
            raise ValueError(f"migration_detection: {name}")
        left, right = item
        if left == right or left not in members or right not in members:
            continue
        edges.append((min(left, right), max(left, right), name))
    return edges


def detect_migration_clusters(
    movements: Sequence[MigrationMovementRow],
    kinship_pairs: Sequence[tuple[str, str]],
    organization_pairs: Sequence[tuple[str, str]],
    communication_pairs: Sequence[tuple[str, str]],
    policy: MigrationDisplacementAnalysisPolicy,
    *,
    relationship_pairs: Sequence[tuple[str, str]] = (),
) -> tuple[MigrationClusterRow, ...]:
    """Union participants by shared kinship, organization, communication, or
    co-movement. Never creates an ``org-`` or ``msoc-`` identity."""
    resolved = _require_policy(policy)
    by_participant: dict[str, list[MigrationMovementRow]] = {}
    for row in movements:
        by_participant.setdefault(row.participant_token, []).append(row)
    members = set(by_participant)
    edges: set[tuple[str, str, str]] = set()
    edges.update(_pair_edges("kinship", kinship_pairs, members))
    edges.update(_pair_edges("organization", organization_pairs, members))
    edges.update(_pair_edges("communication", communication_pairs, members))
    edges.update(_pair_edges("relationship", relationship_pairs, members))
    arrived = sorted(
        (row for row in movements if row.arrival_status == "arrived"),
        key=lambda row: (row.start_tick, row.participant_token),
    )
    for index, early in enumerate(arrived):
        for late in arrived[index + 1 :]:
            if late.start_tick - early.start_tick > resolved.cluster_window_ticks:
                break
            if (
                early.participant_token != late.participant_token
                and early.origin_token == late.origin_token
                and early.destination_token == late.destination_token
            ):
                a, b = sorted((early.participant_token, late.participant_token))
                edges.add((a, b, "co_movement"))
    parent: dict[str, str] = {}

    def find(item: str) -> str:
        parent.setdefault(item, item)
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    for left, right, _basis in sorted(edges):
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[max(root_left, root_right)] = min(root_left, root_right)
    components: dict[str, set[str]] = {}
    for item in sorted(parent):
        components.setdefault(find(item), set()).add(item)
    rows: list[MigrationClusterRow] = []
    for component in components.values():
        if len(component) < resolved.min_cluster_members:
            continue
        basis_counts: dict[str, int] = {}
        for left, right, basis in edges:
            if left in component and right in component:
                basis_counts[basis] = basis_counts.get(basis, 0) + 1
        if not basis_counts:
            continue
        member_rows = [row for item in component for row in by_participant[item]]
        rows.append(
            MigrationClusterRow(
                cluster_token=analysis_migration_candidate_id(
                    "cluster", ",".join(sorted(component))
                ),
                member_tokens=tuple(sorted(component)),
                basis_counts=tuple(sorted(basis_counts.items())),
                coverage=(
                    "complete"
                    if all(row.coverage == "complete" for row in member_rows)
                    else "partial"
                ),
                first_tick=min(row.start_tick for row in member_rows),
                last_tick=max(row.end_tick for row in member_rows),
            )
        )
    rows.sort(key=lambda item: item.cluster_token)
    if len(rows) > resolved.max_candidates_per_run:
        rows = rows[: resolved.max_candidates_per_run]
    return tuple(rows)


def classify_integration_outcomes(
    movements: Sequence[MigrationMovementRow],
    integration_evidence: Sequence[MigrationIntegrationEvidenceRow],
    policy: MigrationDisplacementAnalysisPolicy,
    *,
    waves: Sequence[MigrationWaveRow] | None = None,
    run_end: int | None = None,
) -> tuple[MigrationOutcomeRow, ...]:
    """Label each wave participant's destination outcome. Counts and labels only."""
    resolved = _require_policy(policy)
    ordered = sorted(
        movements,
        key=lambda row: (row.start_tick, row.participant_token, row.destination_token),
    )
    horizon = run_end
    if horizon is None:
        ticks = [row.end_tick for row in ordered]
        ticks.extend(item.last_tick for item in integration_evidence)
        horizon = max(ticks) if ticks else 0
    wave_cells: set[tuple[str, str]] | None = None
    if waves is not None:
        wave_cells = set()
        for wave in waves:
            for participant in wave.participant_tokens:
                wave_cells.add((participant, wave.destination_token))
    evidence_by_cell: dict[tuple[str, str], list[MigrationIntegrationEvidenceRow]] = {}
    for item in integration_evidence:
        evidence_by_cell.setdefault(
            (item.participant_token, item.destination_token), []
        ).append(item)
    outcomes: list[MigrationOutcomeRow] = []
    for index, row in enumerate(ordered):
        if row.arrival_status != "arrived":
            continue
        cell = (row.participant_token, row.destination_token)
        if wave_cells is not None and cell not in wave_cells:
            continue
        arrival = row.end_tick
        later = [
            item
            for item in ordered[index + 1 :]
            if item.participant_token == row.participant_token
            and item.start_tick >= arrival
            and item is not row
        ]
        departure = later[0] if later else None
        if departure is not None:
            residence = departure.start_tick - arrival
        else:
            residence = max(horizon - arrival, 0)
        censored = departure is None and (horizon - arrival) < (
            resolved.integration_window_ticks
        )
        window_end = arrival + resolved.integration_window_ticks
        access = participation = relationship = conflict = 0
        for item in evidence_by_cell.get(cell, ()):
            if item.last_tick < arrival or item.first_tick > window_end:
                continue
            if item.domain in _ACCESS_DOMAINS:
                access += item.evidence_count
            elif item.domain in _PARTICIPATION_DOMAINS:
                participation += item.evidence_count
            elif item.domain == "relationships":
                relationship += item.evidence_count
            elif item.domain == "conflict_status":
                conflict += item.evidence_count
        within = (
            departure is not None
            and departure.start_tick - arrival <= resolved.integration_window_ticks
        )
        if row.coverage == "missing":
            label = "unknown"
        elif (
            within
            and departure is not None
            and (departure.destination_token == row.origin_token)
        ):
            label = "returned"
        elif (
            within
            and departure is not None
            and (departure.destination_token != row.destination_token)
        ):
            label = "onward"
        elif residence >= resolved.min_residence_ticks and (
            access + participation + relationship > 0
        ):
            label = "settled"
        else:
            label = "transient"
        outcomes.append(
            MigrationOutcomeRow(
                outcome_token=analysis_migration_candidate_id(
                    "outcome",
                    f"{row.participant_token}|{row.destination_token}|"
                    f"{row.origin_token}|{row.start_tick}",
                ),
                participant_token=row.participant_token,
                destination_token=row.destination_token,
                residence_ticks=residence,
                access_evidence_count=access,
                participation_evidence_count=participation,
                relationship_evidence_count=relationship,
                conflict_evidence_count=conflict,
                classification=label,
                coverage=row.coverage,
                censored=censored,
            )
        )
    outcomes.sort(key=lambda item: item.outcome_token)
    if len(outcomes) > resolved.max_candidates_per_run:
        outcomes = outcomes[: resolved.max_candidates_per_run]
    return tuple(outcomes)
