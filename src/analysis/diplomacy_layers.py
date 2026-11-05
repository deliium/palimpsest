"""Three strictly separated detached diplomacy layers with a leakage guard."""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from typing import Any, Final, cast

from analysis.diplomacy_contract import (
    DIPLOMACY_FORBIDDEN_RESULT_FIELDS,
    DiplomacyAnalysisError,
    require_diplomacy_candidate_id,
    require_diplomacy_token,
)
from analysis.diplomacy_detection import DiplomaticRelationCandidate
from analysis.diplomacy_identity import DiplomacyAnalysis
from analysis.diplomacy_objective import DiplomacyObjectiveAnchorRow
from analysis.diplomacy_rows import (
    DiplomacyHarvestRows,
    treaty_version_status_label,
)

__all__ = [
    "DiplomacyAnalyticalRow",
    "DiplomacyLayerView",
    "DiplomacyObjectiveRow",
    "DiplomacySubjectiveRow",
    "assert_diplomacy_layer_separation",
    "project_diplomacy_layers",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.diplomacy_layers")


@dataclass(frozen=True, slots=True)
class DiplomacyObjectiveRow:
    tick: int
    region_token: str
    contact_event_count: int
    exchange_event_count: int
    attack_event_count: int


@dataclass(frozen=True, slots=True)
class DiplomacySubjectiveRow:
    owner_token: str
    party_token: str | None
    status_counts: tuple[tuple[str, int], ...]
    lane_counts: tuple[tuple[str, int], ...]
    treaty_status_counts: tuple[tuple[str, int], ...] = ()
    treaty_subject_counts: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class DiplomacyAnalyticalRow:
    candidate_id: str
    party_tokens: tuple[str, ...]
    organization_candidate_ids: tuple[str, ...]
    macro_society_candidate_ids: tuple[str, ...]
    lanes: tuple[str, ...]
    status: str
    treaty_count: int = 0
    version_count: int = 0
    lineage_edge_count: int = 0


@dataclass(frozen=True, slots=True)
class DiplomacyLayerView:
    objective: tuple[DiplomacyObjectiveRow, ...]
    subjective: tuple[DiplomacySubjectiveRow, ...]
    analytical: tuple[DiplomacyAnalyticalRow, ...]
    coverage: str


def _field_names(row: object) -> set[str]:
    return {field.name for field in fields(cast(Any, type(row)))}


def assert_diplomacy_layer_separation(layers: DiplomacyLayerView) -> None:
    """Reject any collapse of objective, subjective, or analytical authority."""

    for objective_row in layers.objective:
        names = _field_names(objective_row)
        if names & {
            "owner_token",
            "candidate_id",
            "party_token",
            "party_tokens",
            "treaty_id",
            "version_id",
            "organization_candidate_ids",
            "macro_society_candidate_ids",
        }:
            raise DiplomacyAnalysisError("diplomacy_layer_leak")
    for subjective_row in layers.subjective:
        names = _field_names(subjective_row)
        if "candidate_id" in names:
            raise DiplomacyAnalysisError("diplomacy_layer_leak")
        require_diplomacy_token(subjective_row.owner_token)
        if subjective_row.party_token is not None:
            require_diplomacy_token(subjective_row.party_token)
    for analytical_row in layers.analytical:
        require_diplomacy_candidate_id(analytical_row.candidate_id)
        for token in analytical_row.party_tokens:
            require_diplomacy_token(token)
    for mixed_row in cast(
        tuple[object, ...],
        (*layers.objective, *layers.subjective, *layers.analytical),
    ):
        if _field_names(mixed_row) & DIPLOMACY_FORBIDDEN_RESULT_FIELDS:
            raise DiplomacyAnalysisError("diplomacy_layer_leak")


def project_diplomacy_layers(
    rows: DiplomacyHarvestRows,
    candidates: tuple[DiplomaticRelationCandidate, ...],
    analysis: tuple[DiplomacyAnalysis, ...],
    *,
    objective_rows: tuple[DiplomacyObjectiveAnchorRow, ...] = (),
    coverage: str = "partial",
) -> DiplomacyLayerView:
    """Project objective counts, owner claims, and analytical candidates."""

    objective = tuple(
        sorted(
            (
                DiplomacyObjectiveRow(
                    tick=row.tick,
                    region_token=row.region_token,
                    contact_event_count=row.contact_event_count,
                    exchange_event_count=row.exchange_event_count,
                    attack_event_count=row.attack_event_count,
                )
                for row in objective_rows
            ),
            key=lambda row: (row.tick, row.region_token),
        )
    )
    statuses: dict[tuple[str, str | None], dict[str, int]] = {}
    lanes: dict[tuple[str, str | None], dict[str, int]] = {}
    treaty_subjects: dict[tuple[str, str | None], dict[str, int]] = {}
    treaty_statuses: dict[tuple[str, str | None], dict[str, int]] = {}
    versions_by_id = {row.version_id: row for row in rows.treaty_versions}
    for party in rows.parties:
        key = (party.owner_token, party.party_token)
        statuses.setdefault(key, {})
        lanes.setdefault(key, {})
    for treaty in rows.treaties:
        position = (treaty.owner_token, None)
        treaty_subjects.setdefault(position, {})[treaty.subject_token] = (
            treaty_subjects.setdefault(position, {}).get(treaty.subject_token, 0) + 1
        )
        version = versions_by_id.get(treaty.current_version_id)
        status_label = (
            treaty_version_status_label(version, rows.treaty_declarations)
            if version is not None
            else "proposed"
        )
        treaty_statuses.setdefault(position, {})[status_label] = (
            treaty_statuses.setdefault(position, {}).get(status_label, 0) + 1
        )
    for envoy in rows.envoys:
        statuses.setdefault((envoy.owner_token, envoy.party_token), {})[
            envoy.status
        ] = (
            statuses.setdefault((envoy.owner_token, envoy.party_token), {}).get(
                envoy.status, 0
            )
            + 1
        )
    for instrument in rows.instruments:
        position = (instrument.owner_token, None)
        lanes.setdefault(position, {})[instrument.instrument_kind] = (
            lanes.setdefault(position, {}).get(instrument.instrument_kind, 0) + 1
        )
    subjective = tuple(
        DiplomacySubjectiveRow(
            owner_token=owner,
            party_token=party,
            status_counts=tuple(sorted(statuses.get((owner, party), {}).items())),
            lane_counts=tuple(sorted(lanes.get((owner, party), {}).items())),
            treaty_status_counts=tuple(
                sorted(treaty_statuses.get((owner, party), {}).items())
            ),
            treaty_subject_counts=tuple(
                sorted(treaty_subjects.get((owner, party), {}).items())
            ),
        )
        for owner, party in sorted(
            set(statuses) | set(lanes) | set(treaty_subjects) | set(treaty_statuses),
            key=lambda item: (item[0], item[1] or ""),
        )
    )
    analytical = tuple(
        DiplomacyAnalyticalRow(
            candidate_id=row.candidate_id,
            party_tokens=row.party_tokens,
            organization_candidate_ids=row.organization_candidate_ids,
            macro_society_candidate_ids=row.macro_society_candidate_ids,
            lanes=row.lanes,
            status=row.status,
            treaty_count=getattr(row, "treaty_count", 0),
            version_count=getattr(row, "version_count", 0),
            lineage_edge_count=getattr(row, "lineage_edge_count", 0),
        )
        for row in sorted(analysis, key=lambda item: item.candidate_id)
    )
    view = DiplomacyLayerView(
        objective=objective,
        subjective=subjective,
        analytical=analytical,
        coverage=coverage,
    )
    assert_diplomacy_layer_separation(view)
    _LOG.debug(
        "diplomacy_layers objective=%s subjective=%s analytical=%s",
        len(objective),
        len(subjective),
        len(analytical),
    )
    return view
