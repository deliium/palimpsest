"""Detached detection of persistent science-like practice.

The detector only reads the bounded context windows produced by the trusted
composition bridge. It never reads cognition, world state, or owner snapshots,
and a stable label is evidence of repeat practice, not proof of scientific
quality, causal culture, or a particular institutional type.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from analysis.scientific_institutions_contract import (
    SCIENTIFIC_INSTITUTIONS_POLICY_VERSION,
    PracticeCarrierKind,
    PracticeCarrierSurvivalFact,
    PracticeCoverageStatus,
    PracticeLane,
    PracticeOrganizationFact,
    PracticeOrganizationLink,
    PracticeStatus,
    ScientificInstitutionContextEvidence,
    ScientificInstitutionContextWindow,
    ScientificInstitutionsError,
)

__all__ = [
    "PracticeWindowAssessment",
    "PracticeWindowState",
    "ScientificPracticeAssessment",
    "ScientificPracticeRow",
    "detect_scientific_practice",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.scientific_institutions_detection"
)


class PracticeWindowState(StrEnum):
    """Closed window states; complete-empty is never missing evidence."""

    COMPLETE_EMPTY = "complete_empty"
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ScientificPracticeRow:
    """One `(window, organization, activity key)` analytical observation."""

    window_index: int
    organization_id: str
    operator: str
    process_token: str
    status: PracticeStatus
    execution_tokens: tuple[str, ...]
    service_tokens: tuple[str, ...]
    contribution_tokens: tuple[str, ...]
    actor_tokens: tuple[str, ...]
    carrier_tokens: tuple[tuple[str, str], ...]
    surviving_carrier_tokens: tuple[tuple[str, str], ...]
    coverage: PracticeCoverageStatus

    def __post_init__(self) -> None:
        if self.status is PracticeStatus.STABLE and (
            self.coverage is not PracticeCoverageStatus.COMPLETE
        ):
            raise ScientificInstitutionsError(
                "scientific_institutions_stable_coverage"
            )

    @property
    def activity_key(self) -> tuple[str, str]:
        return (self.operator, self.process_token)


@dataclass(frozen=True, slots=True)
class PracticeWindowAssessment:
    """Coverage and counts for one absolute-tick window."""

    window_index: int
    start_tick: int
    end_tick_exclusive: int
    complete: bool
    state: PracticeWindowState
    execution_coverage: PracticeCoverageStatus
    carrier_coverage: PracticeCoverageStatus
    organization_coverage: PracticeCoverageStatus
    row_count: int
    unassigned: int
    ambiguous: int


@dataclass(frozen=True, slots=True)
class ScientificPracticeAssessment:
    """Detached rows and window denominators for one completed run."""

    run_id: str
    policy_version: str
    windows: tuple[PracticeWindowAssessment, ...]
    rows: tuple[ScientificPracticeRow, ...]
    unassigned: int
    ambiguous: int

    def __post_init__(self) -> None:
        indexes = tuple(item.window_index for item in self.windows)
        if indexes != tuple(range(len(indexes))):
            raise ScientificInstitutionsError(
                "scientific_institutions_invalid_window"
            )
        for row in self.rows:
            if row.window_index >= len(self.windows):
                raise ScientificInstitutionsError(
                    "scientific_institutions_invalid_window"
                )

    def stable_rows(self) -> tuple[ScientificPracticeRow, ...]:
        return tuple(
            row for row in self.rows if row.status is PracticeStatus.STABLE
        )


def _mandatory_status(
    window: ScientificInstitutionContextWindow,
) -> tuple[PracticeCoverageStatus, PracticeCoverageStatus, PracticeCoverageStatus]:
    execution = (
        window.window.lane_status(PracticeLane.EXECUTION)
        or PracticeCoverageStatus.UNAVAILABLE
    )
    carrier = (
        window.window.lane_status(PracticeLane.CARRIER)
        or PracticeCoverageStatus.UNAVAILABLE
    )
    organization = (
        window.window.lane_status(PracticeLane.ORGANIZATION)
        or PracticeCoverageStatus.UNAVAILABLE
    )
    return execution, carrier, organization


def _window_state(
    window: ScientificInstitutionContextWindow,
    *,
    row_count: int,
    execution: PracticeCoverageStatus,
    carrier: PracticeCoverageStatus,
    organization: PracticeCoverageStatus,
) -> PracticeWindowState:
    if (
        not window.window.complete
        or execution is PracticeCoverageStatus.UNAVAILABLE
        or carrier is PracticeCoverageStatus.UNAVAILABLE
        or organization is PracticeCoverageStatus.UNAVAILABLE
    ):
        return PracticeWindowState.UNAVAILABLE
    if (
        execution is PracticeCoverageStatus.PARTIAL
        or carrier is PracticeCoverageStatus.PARTIAL
        or organization is PracticeCoverageStatus.PARTIAL
    ):
        return PracticeWindowState.PARTIAL
    if row_count == 0:
        return PracticeWindowState.COMPLETE_EMPTY
    return PracticeWindowState.COMPLETE


def _surviving_keys(
    rows: Sequence[PracticeCarrierSurvivalFact],
) -> set[tuple[str, str, str | None]]:
    keys: set[tuple[str, str, str | None]] = set()
    for row in rows:
        keys.add((row.carrier_kind.value, row.carrier_token, None))
        if row.member_token is not None:
            keys.add(
                (
                    row.carrier_kind.value,
                    row.carrier_token,
                    row.member_token,
                )
            )
    return keys


def _service_survives(
    window: ScientificInstitutionContextWindow,
    service_token: str,
    surviving: set[tuple[str, str, str | None]],
) -> tuple[str, str] | None:
    service = next(
        (
            row
            for row in window.carriers
            if row.occurrence_token == service_token
        ),
        None,
    )
    if service is None:
        return None
    token: tuple[str, str] | None = None
    if service.carrier_kind is PracticeCarrierKind.REPOSITORY_MEMBER:
        member = service.member_token
        if member is None:
            return None
        if (
            service.carrier_kind.value,
            service.carrier_token,
            member,
        ) not in surviving:
            return None
        token = (service.carrier_kind.value, member)
    elif (
        service.carrier_kind.value,
        service.carrier_token,
        None,
    ) not in surviving:
        return None
    else:
        token = (service.carrier_kind.value, service.carrier_token)
    return token


def _row(
    window: ScientificInstitutionContextWindow,
    organization_id: str,
    key: tuple[str, str],
    *,
    status: PracticeStatus,
    execution_tokens: Sequence[str],
    service_tokens: Sequence[str],
    contribution_tokens: Sequence[str],
    actor_tokens: Sequence[str],
    carrier_tokens: Sequence[tuple[str, str]],
    surviving_tokens: Sequence[tuple[str, str]],
    coverage: PracticeCoverageStatus,
) -> ScientificPracticeRow:
    return ScientificPracticeRow(
        window_index=window.window.window_index,
        organization_id=organization_id,
        operator=key[0],
        process_token=key[1],
        status=status,
        execution_tokens=tuple(sorted(set(execution_tokens))),
        service_tokens=tuple(sorted(set(service_tokens))),
        contribution_tokens=tuple(sorted(set(contribution_tokens))),
        actor_tokens=tuple(sorted(set(actor_tokens))),
        carrier_tokens=tuple(sorted(set(carrier_tokens))),
        surviving_carrier_tokens=tuple(sorted(set(surviving_tokens))),
        coverage=coverage,
    )


def _row_for_fact(
    window: ScientificInstitutionContextWindow,
    fact: PracticeOrganizationFact,
    key: tuple[str, str],
    *,
    execution_links: Sequence[PracticeOrganizationLink],
    service_links: Sequence[PracticeOrganizationLink],
    keys: set[tuple[str, str, str | None]],
    coverage: PracticeCoverageStatus,
) -> ScientificPracticeRow:
    execution_tokens = [
        str(link.execution_token)
        for link in execution_links
        if link.execution_token is not None
    ]
    contributions = [
        str(link.contribution_token)
        for link in execution_links
        if link.contribution_token is not None
    ]
    actors = {
        link.actor_token
        for link in (*execution_links, *service_links)
        if getattr(link, "actor_token", None)
    }
    matched_services: list[str] = []
    carriers: set[tuple[str, str]] = set()
    surviving: set[tuple[str, str]] = {
        (kind, token)
        for kind, token in fact.anchor_tokens
        if (kind, token, None) in keys
    }
    for link in service_links:
        service_token = link.service_token
        if service_token is None:
            continue
        match = _service_survives(window, service_token, keys)
        if match is None:
            continue
        matched_services.append(service_token)
        carriers.add(match)
        surviving.add(match)
    status = PracticeStatus.SUPPORTED
    if not matched_services:
        status = PracticeStatus.OBSERVED_ONLY
    return _row(
        window,
        fact.organization_id,
        key,
        status=status,
        execution_tokens=execution_tokens,
        service_tokens=matched_services,
        contribution_tokens=contributions,
        actor_tokens=tuple(actors),
        carrier_tokens=tuple(carriers),
        surviving_tokens=tuple(surviving),
        coverage=coverage,
    )


def _is_stable(
    current: ScientificPracticeRow,
    previous: ScientificPracticeRow | None,
    *,
    window_index: int,
) -> bool:
    if previous is None:
        return False
    if previous.window_index != window_index - 1:
        return False
    if previous.status not in {PracticeStatus.SUPPORTED, PracticeStatus.STABLE}:
        return False
    if previous.operator != current.operator:
        return False
    if previous.process_token != current.process_token:
        return False
    if previous.organization_id != current.organization_id:
        return False
    if previous.coverage is not PracticeCoverageStatus.COMPLETE:
        return False
    if current.coverage is not PracticeCoverageStatus.COMPLETE:
        return False
    if current.status is not PracticeStatus.SUPPORTED:
        return False
    previous_carriers = set(previous.surviving_carrier_tokens)
    current_carriers = set(current.surviving_carrier_tokens)
    if not previous_carriers & current_carriers:
        return False
    actors = set(previous.actor_tokens) | set(current.actor_tokens)
    return len(actors) >= 2


def _merge_facts(
    facts: Sequence[PracticeOrganizationFact],
) -> tuple[PracticeOrganizationFact, ...]:
    """Group by unique organization id within one window."""

    by_org: dict[str, list[PracticeOrganizationFact]] = {}
    for fact in facts:
        by_org.setdefault(fact.organization_id, []).append(fact)
    merged: list[PracticeOrganizationFact] = []
    for organization_id in sorted(by_org):
        group = by_org[organization_id]
        if len(group) == 1:
            merged.append(group[0])
            continue
        first = group[0]
        participants = {token for row in group for token in row.participant_tokens}
        anchors = {pair for row in group for pair in row.anchor_tokens}
        procedures = {token for row in group for token in row.procedure_tokens}
        records = {token for row in group for token in row.record_tokens}
        claimants = {token for row in group for token in row.claimant_tokens}
        links = {link for row in group for link in row.links}
        coverage = PracticeCoverageStatus.COMPLETE
        for row in group:
            if row.coverage is PracticeCoverageStatus.UNAVAILABLE:
                coverage = PracticeCoverageStatus.UNAVAILABLE
                break
            if row.coverage is PracticeCoverageStatus.PARTIAL:
                coverage = PracticeCoverageStatus.PARTIAL
        merged.append(
            replace(
                first,
                participant_tokens=tuple(sorted(participants)),
                anchor_tokens=tuple(sorted(anchors)),
                procedure_tokens=tuple(sorted(procedures)),
                record_tokens=tuple(sorted(records)),
                claimant_tokens=tuple(sorted(claimants)),
                coverage=coverage,
                links=tuple(sorted(links, key=repr)),
            )
        )
    return tuple(merged)


def detect_scientific_practice(
    evidence: ScientificInstitutionContextEvidence,
) -> ScientificPracticeAssessment:
    """Classify window-local repeat practice without backdating stability."""

    if type(evidence) is not ScientificInstitutionContextEvidence:
        raise ScientificInstitutionsError("scientific_institutions_invalid_evidence")
    rows: list[ScientificPracticeRow] = []
    windows: list[PracticeWindowAssessment] = []
    known: dict[tuple[str, str, str], ScientificPracticeRow] = {}
    total_unassigned = 0
    total_ambiguous = 0
    for window in evidence.windows:
        execution, carrier, organization = _mandatory_status(window)
        mandatory_complete = (
            window.window.complete
            and execution is PracticeCoverageStatus.COMPLETE
            and carrier is PracticeCoverageStatus.COMPLETE
            and organization is PracticeCoverageStatus.COMPLETE
        )
        coverage = (
            PracticeCoverageStatus.COMPLETE
            if mandatory_complete
            else PracticeCoverageStatus.PARTIAL
        )
        if execution is PracticeCoverageStatus.UNAVAILABLE:
            coverage = PracticeCoverageStatus.UNAVAILABLE
        keys = _surviving_keys(window.surviving_carriers)
        window_rows: list[ScientificPracticeRow] = []
        merged_facts = _merge_facts(window.organizations)
        present_orgs = {fact.organization_id for fact in merged_facts}
        for fact in merged_facts:
            execution_links = [
                link
                for link in fact.links
                if link.execution_token is not None
            ]
            service_links = [
                link
                for link in fact.links
                if link.service_token is not None
            ]
            by_key: dict[tuple[str, str], list[PracticeOrganizationLink]] = {}
            tokens = {
                row.occurrence_token: row for row in window.executions
            }
            for link in execution_links:
                execution_fact = tokens.get(link.execution_token or "")
                if execution_fact is None:
                    continue
                by_key.setdefault(execution_fact.activity_key, []).append(link)
            for key, links in sorted(by_key.items()):
                row = _row_for_fact(
                    window,
                    fact,
                    key,
                    execution_links=links,
                    service_links=service_links,
                    keys=keys,
                    coverage=coverage,
                )
                previous = known.get(
                    (fact.organization_id, key[0], key[1])
                )
                if mandatory_complete and _is_stable(
                    row, previous, window_index=window.window.window_index
                ):
                    row = _row(
                        window,
                        fact.organization_id,
                        key,
                        status=PracticeStatus.STABLE,
                        execution_tokens=row.execution_tokens,
                        service_tokens=row.service_tokens,
                        contribution_tokens=row.contribution_tokens,
                        actor_tokens=row.actor_tokens,
                        carrier_tokens=row.carrier_tokens,
                        surviving_tokens=row.surviving_carrier_tokens,
                        coverage=coverage,
                    )
                window_rows.append(row)
                known[(fact.organization_id, key[0], key[1])] = row
        for (organization_id, operator, process_token), _ in sorted(
            known.items()
        ):
            key = (operator, process_token)
            if organization_id not in present_orgs and mandatory_complete:
                continue
            if any(
                row.organization_id == organization_id
                and row.activity_key == key
                for row in window_rows
            ):
                continue
            status = (
                PracticeStatus.NOT_OBSERVED
                if mandatory_complete
                else PracticeStatus.UNAVAILABLE
            )
            row = _row(
                window,
                organization_id,
                key,
                status=status,
                execution_tokens=(),
                service_tokens=(),
                contribution_tokens=(),
                actor_tokens=(),
                carrier_tokens=(),
                surviving_tokens=(),
                coverage=coverage,
            )
            window_rows.append(row)
        state = _window_state(
            window,
            row_count=len(window_rows),
            execution=execution,
            carrier=carrier,
            organization=organization,
        )
        total_unassigned += window.unassigned
        total_ambiguous += window.ambiguous
        rows.extend(window_rows)
        windows.append(
            PracticeWindowAssessment(
                window_index=window.window.window_index,
                start_tick=window.window.start_tick,
                end_tick_exclusive=window.window.end_exclusive,
                complete=window.window.complete,
                state=state,
                execution_coverage=execution,
                carrier_coverage=carrier,
                organization_coverage=organization,
                row_count=len(window_rows),
                unassigned=window.unassigned,
                ambiguous=window.ambiguous,
            )
        )
    _LOG.debug(
        "scientific_practice_detection run_id=%s windows=%s rows=%s stable=%s "
        "unassigned=%s ambiguous=%s",
        evidence.run_id,
        len(windows),
        len(rows),
        sum(1 for row in rows if row.status is PracticeStatus.STABLE),
        total_unassigned,
        total_ambiguous,
    )
    return ScientificPracticeAssessment(
        run_id=evidence.run_id,
        policy_version=SCIENTIFIC_INSTITUTIONS_POLICY_VERSION,
        windows=tuple(windows),
        rows=tuple(
            sorted(
                rows,
                key=lambda row: (
                    row.window_index,
                    row.organization_id,
                    row.operator,
                    row.process_token,
                ),
            )
        ),
        unassigned=total_unassigned,
        ambiguous=total_ambiguous,
    )
