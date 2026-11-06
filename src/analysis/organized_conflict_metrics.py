# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Four detached organized-conflict metric families.

Counts, durations, ratios, and closed labels only. No war score, violence score,
legitimacy, winner, or composite exists.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from itertools import pairwise
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.organized_conflict_alignment import (
    ConflictAlignmentRow,
    ConflictAnalysisSummary,
)
from analysis.organized_conflict_contract import ConflictAlignment
from analysis.organized_conflict_detection import ConflictEpisodeCandidate
from analysis.organized_conflict_policy import (
    ORGANIZED_CONFLICT_ANALYSIS_POLICY_VERSION,
)
from analysis.organized_conflict_rows import OrganizedConflictHarvestRows
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "compute_organized_conflict_interpretation",
    "compute_organized_conflict_outcomes",
    "compute_organized_conflict_participation",
    "compute_organized_conflict_persistence",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organized_conflict.metrics")

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _availability(rows: OrganizedConflictHarvestRows | None) -> MetricAvailability:
    if rows is None:
        return MetricAvailability.ABSENT
    if rows.coverage is ConflictAlignment.CONSISTENT and not rows.objective_events:
        return MetricAvailability.PARTIAL
    return MetricAvailability.PRESENT


def _coverage(
    rows: OrganizedConflictHarvestRows | None,
    candidates: Sequence[ConflictEpisodeCandidate],
) -> MetricCoverage:
    if rows is None:
        return _ABSENT_COVERAGE
    observed = len(rows.objective_events) + sum(
        len(getattr(rows, name))
        for name in (
            "owner_plans",
            "owner_participations",
            "owner_interpretations",
            "owner_outcomes",
        )
    )
    expected = max(observed, len(candidates), 1)
    return MetricCoverage(
        observed=observed,
        expected=expected,
        ratio=quantize_float(observed / expected),
    )


def _document(
    family: MetricFamilyId,
    rows: OrganizedConflictHarvestRows | None,
    candidates: Sequence[ConflictEpisodeCandidate],
    *,
    run_id: str,
    input_revision: str,
    values: dict[str, object],
    notes_code: str,
) -> MetricDocument:
    spec = metric_specification(family)
    availability = _availability(rows)
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
        coverage=_coverage(rows, candidates),
        availability=availability,
        values={} if availability is MetricAvailability.ABSENT else values,
        provenance=MetricProvenance(
            source_kind="organized_conflict_analysis",
            source_ids=(
                run_id,
                input_revision,
                ORGANIZED_CONFLICT_ANALYSIS_POLICY_VERSION,
            ),
            notes_code=notes_code,
        ),
    )


def _classes(candidates: Sequence[ConflictEpisodeCandidate]) -> dict[str, int]:
    counts = {
        "individual_violence": 0,
        "coordinated_conflict": 0,
        "persistent_inter_group_conflict": 0,
    }
    for candidate in candidates:
        counts[candidate.classification] = counts.get(candidate.classification, 0) + 1
    return counts


_ROLE_NAMES: Final[tuple[str, ...]] = (
    "attacker",
    "defender",
    "scout",
    "blocker",
    "capturer",
    "assistant",
    "retreater",
    "messenger",
    "unknown",
)


def _role_value(value: object) -> str:
    raw = str(getattr(value, "value", value))
    return raw.split(".")[-1]


def _role_participants(rows: object | None) -> dict[str, set[str]]:
    """Collect distinct participant tokens per closed role from owner rows."""

    roles: dict[str, set[str]] = {name: set() for name in _ROLE_NAMES}
    for participation in getattr(rows, "owner_participations", ()) or ():
        role = _role_value(getattr(participation, "role", "unknown"))
        participant = str(getattr(participation, "participant_ref", ""))
        if participant:
            roles.setdefault(role, set()).add(participant)
    for plan in getattr(rows, "owner_plans", ()) or ():
        role = _role_value(getattr(plan, "role", "unknown"))
        for participant in getattr(plan, "participant_refs", ()) or ():
            if participant:
                roles.setdefault(role, set()).add(str(participant))
    return roles


def _hostile_tick_counts(rows: object | None) -> dict[int, int]:
    counts: dict[int, int] = {}
    for event in getattr(rows, "objective_events", ()) or ():
        if event.event_class in {
            "attack",
            "structure_opposition",
            "death",
            "route_denial",
        } or (
            event.event_class == "retreat"
            and event.success is False
            and bool(event.other_token)
        ):
            counts[event.tick] = counts.get(event.tick, 0) + 1
    return counts


def _escalation_counts(rows: object | None) -> tuple[int, int]:
    counts = _hostile_tick_counts(rows)
    ticks = sorted(counts)
    escalation = 0
    deescalation = 0
    for previous, current in pairwise(ticks):
        if counts[current] > counts[previous]:
            escalation += 1
        elif counts[current] < counts[previous]:
            deescalation += 1
    return escalation, deescalation


def compute_organized_conflict_participation(
    rows: OrganizedConflictHarvestRows | None,
    candidates: Sequence[ConflictEpisodeCandidate],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    classes = _classes(candidates)
    participants = {
        token for candidate in candidates for token in candidate.participant_tokens
    }
    organized = sum(
        1
        for candidate in candidates
        if candidate.classification != "individual_violence"
    )
    roles: dict[str, set[str]] = _role_participants(rows)
    all_role_participants = {token for tokens in roles.values() for token in tokens}
    known_role_participants = {
        token
        for role, tokens in roles.items()
        if role != "unknown"
        for token in tokens
    }
    values = {
        "episode_count": len(candidates),
        "individual_episode_count": classes["individual_violence"],
        "coordinated_episode_count": classes["coordinated_conflict"],
        "persistent_inter_group_episode_count": classes[
            "persistent_inter_group_conflict"
        ],
        "participant_count": len(participants),
        "side_count": sum(candidate.side_count for candidate in candidates),
        "attacker_count": len(roles["attacker"]),
        "defender_count": len(roles["defender"]),
        "scout_count": len(roles["scout"]),
        "blocker_count": len(roles["blocker"]),
        "capturer_count": len(roles["capturer"]),
        "assistant_count": len(roles["assistant"]),
        "retreater_count": len(roles["retreater"]),
        "messenger_count": len(roles["messenger"]),
        "unknown_role_count": len(roles["unknown"]),
        "organized_episode_ratio": _ratio(organized, len(candidates)),
        "role_coverage_ratio": _ratio(
            len(known_role_participants), len(all_role_participants)
        ),
    }
    return _document(
        MetricFamilyId.ORGANIZED_CONFLICT_PARTICIPATION,
        rows,
        candidates,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="organized_conflict_participation",
    )


def compute_organized_conflict_persistence(
    rows: OrganizedConflictHarvestRows | None,
    candidates: Sequence[ConflictEpisodeCandidate],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    durations = [candidate.end_tick - candidate.start_tick for candidate in candidates]
    escalation, deescalation = _escalation_counts(rows)
    values = {
        "active_window_count": sum(
            candidate.active_window_count for candidate in candidates
        ),
        "episode_duration_ticks_total": sum(durations),
        "episode_duration_ticks_max": max(durations, default=0),
        "recurrent_episode_count": sum(
            1 for candidate in candidates if candidate.recurrent
        ),
        "sustained_episode_count": sum(
            1 for candidate in candidates if candidate.sustained
        ),
        "inter_group_episode_count": _classes(candidates)[
            "persistent_inter_group_conflict"
        ],
        "reciprocal_window_count": sum(
            candidate.reciprocal_window_count for candidate in candidates
        ),
        "escalation_count": escalation,
        "deescalation_count": deescalation,
        "hostile_event_count": sum(
            candidate.hostile_event_count for candidate in candidates
        ),
        "persistence_ratio": _ratio(
            sum(1 for candidate in candidates if candidate.sustained),
            len(candidates),
        ),
    }
    return _document(
        MetricFamilyId.ORGANIZED_CONFLICT_PERSISTENCE,
        rows,
        candidates,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="organized_conflict_persistence",
    )


def compute_organized_conflict_outcomes(
    rows: OrganizedConflictHarvestRows | None,
    candidates: Sequence[ConflictEpisodeCandidate],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    events = tuple(getattr(rows, "objective_events", ()) or ())
    classes = [event.event_class for event in events]
    attack_events = [event for event in events if event.event_class == "attack"]
    values = {
        "attack_event_count": len(attack_events),
        "hit_count": sum(1 for event in attack_events if event.success is True),
        "miss_count": sum(1 for event in attack_events if event.success is False),
        "damage_total": sum(
            event.magnitude for event in attack_events if event.success is not False
        ),
        "lethal_attack_count": sum(
            1 for event in attack_events if event.magnitude >= 100
        ),
        "death_count": classes.count("death"),
        "flee_success_count": sum(
            1
            for event in events
            if event.event_class == "retreat" and event.success is True
        ),
        "flee_failure_count": sum(
            1
            for event in events
            if event.event_class == "retreat" and event.success is False
        ),
        "custody_capture_count": classes.count("custody_capture"),
        "structure_opposition_count": classes.count("structure_opposition"),
        "assistance_count": classes.count("assistance"),
        "co_movement_count": classes.count("co_movement"),
        "route_denial_evidence_count": max(
            classes.count("route_denial"),
            sum(
                1
                for candidate in candidates
                if "route_denial" in candidate.event_classes
            ),
        ),
        "outcome_coverage_ratio": _ratio(
            sum(
                1
                for event in events
                if event.event_class
                in {
                    "attack",
                    "death",
                    "custody_capture",
                    "structure_opposition",
                    "assistance",
                    "co_movement",
                }
            ),
            len(events),
        ),
    }
    return _document(
        MetricFamilyId.ORGANIZED_CONFLICT_OUTCOMES,
        rows,
        candidates,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="organized_conflict_outcomes",
    )


def compute_organized_conflict_interpretation(
    rows: OrganizedConflictHarvestRows | None,
    candidates: Sequence[ConflictEpisodeCandidate],
    alignment: Sequence[ConflictAlignmentRow],
    summary: ConflictAnalysisSummary,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    interpretations = tuple(getattr(rows, "owner_interpretations", ()) or ())
    kinds = [str(getattr(row, "kind", "")).split(".")[-1] for row in interpretations]
    values = {
        "interpretation_count": len(interpretations),
        "individual_interpretation_count": sum(
            1 for kind in kinds if kind == "individual_violence"
        ),
        "coordinated_interpretation_count": sum(
            1 for kind in kinds if kind == "coordinated_conflict"
        ),
        "persistent_inter_group_interpretation_count": sum(
            1 for kind in kinds if kind == "persistent_inter_group_conflict"
        ),
        "defense_interpretation_count": sum(1 for kind in kinds if kind == "defense"),
        "retreat_interpretation_count": sum(1 for kind in kinds if kind == "retreat"),
        "assistance_interpretation_count": sum(
            1 for kind in kinds if kind == "assistance"
        ),
        "resource_capture_interpretation_count": sum(
            1 for kind in kinds if kind == "resource_capture"
        ),
        "route_blocking_interpretation_count": sum(
            1 for kind in kinds if kind == "route_blocking"
        ),
        "structure_attack_interpretation_count": sum(
            1 for kind in kinds if kind == "structure_attack"
        ),
        "unclear_interpretation_count": sum(1 for kind in kinds if kind == "unclear"),
        "aligned_count": summary.consistent_count,
        "unresolved_count": summary.unresolved_count,
        "inconsistent_count": summary.inconsistent_count,
        "not_applicable_count": summary.not_applicable_count,
        "owner_disagreement_count": summary.owner_disagreement_count,
        "interpretation_coverage_ratio": _ratio(len(alignment), len(interpretations)),
    }
    return _document(
        MetricFamilyId.ORGANIZED_CONFLICT_INTERPRETATION,
        rows,
        candidates,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="organized_conflict_interpretation",
    )
