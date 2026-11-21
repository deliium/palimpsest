"""Compose owner organization context and optional practice signals.

The module joins committed receipts from the completed-run projection to
owner-scoped organization, office, institutional-memory, teaching, replication,
and measurement evidence. All joins are exact and contemporaneous; a claim or
co-occurrence never acts as an objective witness.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final

from analysis.organization_contract import OrganizationAnalysisError
from analysis.organization_detection import (
    OrganizationCandidate,
    detect_organization_candidates_with_contributors,
)
from analysis.organization_evidence import (
    ANCHOR_FAMILIES,
    OrganizationWindowEvidence,
)
from analysis.organization_identity import assign_organization_identities
from analysis.organizations import (
    OrganizationHarvestRows,
    harvest_organization_rows,
)
from analysis.scientific_institutions_contract import (
    OPTIONAL_PRACTICE_LANES,
    PracticeCarrierAction,
    PracticeCarrierKind,
    PracticeCoverage,
    PracticeCoverageStatus,
    PracticeLane,
    PracticeOrganizationFact,
    PracticeOrganizationLink,
    PracticeSignalKind,
    PracticeSupplementFact,
    PracticeWindow,
    ScientificInstitutionContextEvidence,
    ScientificInstitutionContextWindow,
    ScientificInstitutionsError,
    derive_practice_token,
)
from experiments.replication_completed_run import replication_facts
from experiments.scientific_institutions_completed_run import (
    PracticeCarrierSurvivalFact,
    ScientificInstitutionBoundaryInput,
    ScientificInstitutionEvidence,
    ScientificInstitutionWindowEvidence,
)
from simulation import SimulationRunnerConfig
from world.events import (
    ExperimentResolved,
    MeasurementTaken,
    ProjectContributed,
    WorldEvent,
)

__all__ = [
    "ScientificInstitutionContextEvidence",
    "ScientificInstitutionContextWindow",
    "build_scientific_institution_context",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.scientific_institutions_context"
)

_PARTICIPANT_STATUSES: Final[frozenset[str]] = frozenset({"perceived", "explicit"})
_CONFLICT_STATUSES: Final[frozenset[str]] = frozenset({"disputed", "former"})
_TEACHING_ADVICE: Final[str] = "advice"


@dataclass(frozen=True, slots=True)
class _Contribution:
    actor_token: str
    project_token: str
    tick: int
    occurrence_token: str


def _actor_token(run_id: str, agent_id: str) -> str:
    return derive_practice_token("actor", run_id, agent_id)


def _entity_actor_token(
    run_id: str, entity_id: str, mapping: Mapping[str, str]
) -> str | None:
    agent = mapping.get(entity_id)
    if agent is None:
        return None
    return _actor_token(run_id, agent)


def _carrier_token(run_id: str, entity_id: str) -> str:
    return derive_practice_token("carrier", run_id, entity_id)


def _occurrence_token(run_id: str, event_id: str) -> str:
    return derive_practice_token("occurrence", run_id, event_id)


def _owner_local_token(run_id: str, owner_token: str, value: str) -> str:
    return derive_practice_token("owner_local", run_id, owner_token, value)


def _identity_maps(
    boundaries: Sequence[ScientificInstitutionBoundaryInput],
) -> tuple[dict[str, str], dict[str, str]]:
    entity_to_agent: dict[str, str] = {}
    agent_to_entity: dict[str, str] = {}
    for item in boundaries:
        for owner in item.boundary.owners:
            entity = owner.entity_id.value
            agent = owner.owner_id.value
            existing = entity_to_agent.get(entity)
            if existing is not None and existing != agent:
                raise ScientificInstitutionsError(
                    "scientific_institutions_ambiguous_identity"
                )
            entity_to_agent[entity] = agent
            agent_to_entity[agent] = entity
    return entity_to_agent, agent_to_entity


def _org_ledgers(
    item: ScientificInstitutionBoundaryInput,
) -> tuple[tuple[OrganizationHarvestRows, ...], bool]:
    ledgers: list[object] = []
    missing = False
    for owner in item.boundary.owners:
        checkpoint = owner.runtime_checkpoint
        if checkpoint is None:
            missing = True
            continue
        ledger = checkpoint.organization_concepts
        if ledger is None:
            # The organizations flag is on: a missing sidecar is an enabled
            # empty ledger, not absent evidence.
            continue
        ledgers.append(ledger)
    if not ledgers:
        return (), missing
    try:
        return harvest_organization_rows(ledgers), missing
    except OrganizationAnalysisError as exc:
        raise ScientificInstitutionsError(
            "scientific_institutions_organization_invalid"
        ) from exc


def _filter_owner_rows(
    rows: Sequence[OrganizationHarvestRows],
    *,
    start_tick: int,
    end_tick: int,
) -> tuple[OrganizationHarvestRows, ...]:
    filtered: list[OrganizationHarvestRows] = []
    for owner in rows:
        concepts = tuple(
            concept
            for concept in owner.concepts
            if start_tick <= concept.last_tick <= end_tick
        )
        if not concepts:
            continue
        organization_ids = {concept.organization_id for concept in concepts}
        members = tuple(
            member
            for member in owner.members
            if member.organization_id in organization_ids
            and not (
                member.expires_tick is not None
                and member.expires_tick <= end_tick
            )
        )
        filtered.append(
            OrganizationHarvestRows(
                owner=owner.owner,
                concepts=concepts,
                members=members,
                roles=tuple(
                    row
                    for row in owner.roles
                    if row.organization_id in organization_ids
                ),
                goals=tuple(
                    row
                    for row in owner.goals
                    if row.organization_id in organization_ids
                ),
                resources=tuple(
                    row
                    for row in owner.resources
                    if row.organization_id in organization_ids
                ),
                procedures=tuple(
                    row
                    for row in owner.procedures
                    if row.organization_id in organization_ids
                ),
                records=tuple(
                    row
                    for row in owner.records
                    if row.organization_id in organization_ids
                ),
                commitments=tuple(
                    row
                    for row in owner.commitments
                    if row.organization_id in organization_ids
                ),
                identities=tuple(
                    row
                    for row in owner.identities
                    if row.organization_id in organization_ids
                ),
                windows=tuple(
                    row
                    for row in owner.windows
                    if row.organization_id in organization_ids
                ),
                lineage=owner.lineage,
            )
        )
    return tuple(filtered)


def _lane_presence(
    rows: Sequence[OrganizationHarvestRows],
) -> tuple[tuple[str, bool], ...]:
    presence = {family: False for family in ANCHOR_FAMILIES}
    for owner in rows:
        for family in ANCHOR_FAMILIES:
            if getattr(owner, family):
                presence[family] = True
    return tuple(sorted(presence.items()))


def _organization_window(
    window: ScientificInstitutionWindowEvidence,
    *,
    endpoint: ScientificInstitutionBoundaryInput | None,
) -> tuple[OrganizationWindowEvidence | None, bool, bool, bool]:
    if endpoint is None:
        return None, False, False, False
    rows, missing = _org_ledgers(endpoint)
    available = bool(endpoint.boundary.owners)
    filtered = _filter_owner_rows(
        rows,
        start_tick=window.window.start_tick,
        end_tick=window.window.end_exclusive - 1,
    )
    truncated = any(
        "history_truncated" in owner.owner.notices for owner in filtered
    )
    if not filtered:
        return None, missing, truncated, available
    evidence = OrganizationWindowEvidence(
        window_index=window.window.window_index,
        start_tick=window.window.start_tick,
        end_tick=window.window.end_exclusive - 1,
        owner_rows=filtered,
        known_person_ids=tuple(
            sorted({member.member_id for owner in filtered for member in owner.members})
        ),
        lane_presence=_lane_presence(filtered),
    )
    return evidence, missing, truncated, available


def _concept_rows(
    row: OrganizationHarvestRows, local_concept_id: str
) -> tuple[
    tuple[Any, ...],
    tuple[Any, ...],
    tuple[Any, ...],
    tuple[Any, ...],
    tuple[Any, ...],
]:
    return (
        tuple(
            item
            for item in row.roles
            if item.organization_id == local_concept_id
        ),
        tuple(
            item
            for item in row.goals
            if item.organization_id == local_concept_id
        ),
        tuple(
            item
            for item in row.records
            if item.organization_id == local_concept_id
        ),
        tuple(
            item
            for item in row.procedures
            if item.organization_id == local_concept_id
        ),
        tuple(
            item
            for item in row.resources
            if item.organization_id == local_concept_id
        ),
    )


def _participants(
    row: OrganizationHarvestRows,
    local_concept_id: str,
    *,
    run_id: str,
    entity_to_agent: Mapping[str, str],
) -> tuple[str, ...]:
    members = [
        member
        for member in row.members
        if member.organization_id == local_concept_id
    ]
    conflicted = {
        member.member_id
        for member in members
        if member.status in _CONFLICT_STATUSES
    }
    tokens: set[str] = set()
    for member in members:
        if member.member_id in conflicted:
            continue
        if member.status not in _PARTICIPANT_STATUSES:
            continue
        if member.temporal_scope == "temporary":
            continue
        token = _entity_actor_token(
            run_id, member.member_id, entity_to_agent
        )
        if token is None:
            continue
        tokens.add(token)
    return tuple(sorted(tokens))


@dataclass(frozen=True, slots=True)
class _CandidateView:
    candidate: OrganizationCandidate
    organization_id: str
    local_concept_ids: tuple[tuple[str, str], ...]


def _candidate_tokens(
    view: _CandidateView,
    *,
    run_id: str,
    entity_to_agent: Mapping[str, str],
    filtered_rows: Sequence[OrganizationHarvestRows],
) -> PracticeOrganizationFact:
    participants: set[str] = set()
    anchors: set[tuple[str, str]] = set()
    procedures: set[str] = set()
    records: set[str] = set()
    for owner_id, local_concept_id in view.local_concept_ids:
        owner_token = _actor_token(run_id, owner_id)
        owner_row = next(
            (
                row
                for row in filtered_rows
                if row.owner.owner_id == owner_id
            ),
            None,
        )
        if owner_row is None:
            continue
        participants.update(
            _participants(
                owner_row,
                local_concept_id,
                run_id=run_id,
                entity_to_agent=entity_to_agent,
            )
        )
        roles, concept_goals, concept_records, concept_procedures, resources = (
            _concept_rows(owner_row, local_concept_id)
        )
        for role in roles:
            token = _owner_local_token(run_id, owner_token, role.office_id)
            anchors.add(("office", token))
        for goal in concept_goals:
            token = _carrier_token(run_id, goal.anchor_id)
            anchors.add((goal.anchor_kind, token))
        for record in concept_records:
            token = _carrier_token(run_id, record.anchor_id)
            anchors.add(("record", token))
            records.add(token)
        for procedure in concept_procedures:
            token = _owner_local_token(run_id, owner_token, procedure.anchor_id)
            procedures.add(token)
        for resource in resources:
            token = _carrier_token(run_id, resource.anchor_id)
            anchors.add((resource.resource_kind, token))
    return PracticeOrganizationFact(
        run_id=run_id,
        window_index=view.candidate.window_index,
        organization_id=view.organization_id,
        candidate_key=view.candidate.candidate_key,
        participant_tokens=tuple(sorted(participants)),
        anchor_tokens=tuple(sorted(anchors)),
        procedure_tokens=tuple(sorted(procedures)),
        record_tokens=tuple(sorted(records)),
        claimant_tokens=tuple(
            sorted(
                {
                    _actor_token(run_id, owner_id)
                    for owner_id, _ in view.local_concept_ids
                }
            )
        ),
        coverage=PracticeCoverageStatus.COMPLETE,
        links=(),
    )


def _candidate_contributors(
    contributors: Sequence[tuple[int, str, str, str]],
) -> dict[str, tuple[tuple[str, str], ...]]:
    mapping: dict[str, set[tuple[str, str]]] = {}
    for _, candidate_key, owner_id, local_id in contributors:
        mapping.setdefault(candidate_key, set()).add((owner_id, local_id))
    return {
        key: tuple(sorted(values)) for key, values in mapping.items()
    }


def _window_events(
    endpoint: ScientificInstitutionBoundaryInput,
    window: PracticeWindow,
) -> tuple[WorldEvent, ...]:
    return tuple(
        event
        for event in endpoint.boundary.events
        if window.start_tick <= event.tick < window.end_exclusive
    )


def _contributions(
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    entity_to_agent: Mapping[str, str],
) -> tuple[_Contribution, ...]:
    rows: list[_Contribution] = []
    for event in events:
        details = event.details
        if not isinstance(details, ProjectContributed):
            continue
        if not details.accepted:
            continue
        if (
            details.labor_done <= 0
            and details.materials_done <= 0
            and details.item_id is None
        ):
            continue
        actor = _entity_actor_token(
            run_id,
            details.actor_id.value,
            entity_to_agent,
        )
        if actor is None:
            continue
        rows.append(
            _Contribution(
                actor_token=actor,
                project_token=_carrier_token(
                    run_id, details.project_id.value
                ),
                tick=event.tick,
                occurrence_token=_occurrence_token(
                    run_id, event.event_id.value
                ),
            )
        )
    return tuple(rows)


def _witness(
    contributions: Sequence[_Contribution],
    *,
    actor_token: str,
    goal_tokens: set[str],
    action_tick: int,
) -> _Contribution | None:
    eligible = [
        row
        for row in contributions
        if row.actor_token == actor_token
        and row.project_token in goal_tokens
        and row.tick <= action_tick
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda row: (row.tick, row.occurrence_token))


def _fact_carrier_anchor(
    fact: PracticeOrganizationFact,
) -> set[str]:
    return set(fact.record_tokens) | {
        token
        for kind, token in fact.anchor_tokens
        if kind in {"repository", "resource"}
    }


def _service_matches(
    carrier: PracticeCarrierKind,
    carrier_token: str,
    member_token: str | None,
    anchors: set[str],
) -> bool:
    if carrier is PracticeCarrierKind.REPOSITORY_MEMBER:
        return (
            (member_token is not None and member_token in anchors)
            or carrier_token in anchors
        )
    return carrier_token in anchors


def _surviving_tokens(
    rows: Sequence[PracticeCarrierSurvivalFact],
) -> set[str]:
    values: set[str] = set()
    for row in rows:
        values.add(row.carrier_token)
        if row.member_token is not None:
            values.add(row.member_token)
    return values


def _build_links(
    window: ScientificInstitutionWindowEvidence,
    facts: Sequence[PracticeOrganizationFact],
    *,
    run_id: str,
    contributions: Sequence[_Contribution],
    entity_to_agent: Mapping[str, str],
) -> tuple[list[PracticeOrganizationFact], int, int]:
    execution_by_token = {
        row.occurrence_token: row for row in window.executions
    }
    service_by_token = {
        row.occurrence_token: row
        for row in window.carriers
        if row.action
        in {
            PracticeCarrierAction.CREATE,
            PracticeCarrierAction.ANNOTATE,
            PracticeCarrierAction.DEPOSIT,
            PracticeCarrierAction.RETRIEVE,
        }
    }
    execution_targets: dict[str, set[str]] = {}
    service_targets: dict[str, set[str]] = {}
    for fact in facts:
        goals = {
            token
            for kind, token in fact.anchor_tokens
            if kind == "collective_project"
        }
        anchors = _fact_carrier_anchor(fact)
        for token, row in execution_by_token.items():
            if row.actor_token not in fact.participant_tokens:
                continue
            witness = _witness(
                contributions,
                actor_token=row.actor_token,
                goal_tokens=goals,
                action_tick=row.tick,
            )
            if witness is None:
                continue
            execution_targets.setdefault(token, set()).add(
                fact.organization_id
            )
        for token, service_row in service_by_token.items():
            if service_row.actor_token not in fact.participant_tokens:
                continue
            if not _service_matches(
                service_row.carrier_kind,
                service_row.carrier_token,
                service_row.member_token,
                anchors,
            ):
                continue
            witness = _witness(
                contributions,
                actor_token=service_row.actor_token,
                goal_tokens=goals,
                action_tick=service_row.tick,
            )
            if witness is None:
                continue
            service_targets.setdefault(token, set()).add(
                fact.organization_id
            )
    links: dict[str, set[PracticeOrganizationLink]] = {
        fact.organization_id: set() for fact in facts
    }
    ambiguous = 0
    for token, targets in execution_targets.items():
        if len(targets) > 1:
            ambiguous += 1
            continue
        for organization_id in targets:
            row = execution_by_token[token]
            fact = next(
                item for item in facts if item.organization_id == organization_id
            )
            goals = {
                value
                for kind, value in fact.anchor_tokens
                if kind == "collective_project"
            }
            witness = _witness(
                contributions,
                actor_token=row.actor_token,
                goal_tokens=goals,
                action_tick=row.tick,
            )
            assert witness is not None
            links[organization_id].add(
                PracticeOrganizationLink(
                    actor_token=row.actor_token,
                    execution_token=token,
                    contribution_token=witness.occurrence_token,
                    contribution_tick=witness.tick,
                )
            )
    for token, targets in service_targets.items():
        if len(targets) > 1:
            ambiguous += 1
            continue
        for organization_id in targets:
            service_row = service_by_token[token]
            fact = next(
                item for item in facts if item.organization_id == organization_id
            )
            goals = {
                value
                for kind, value in fact.anchor_tokens
                if kind == "collective_project"
            }
            witness = _witness(
                contributions,
                actor_token=service_row.actor_token,
                goal_tokens=goals,
                action_tick=service_row.tick,
            )
            assert witness is not None
            links[organization_id].add(
                PracticeOrganizationLink(
                    actor_token=service_row.actor_token,
                    service_token=token,
                    contribution_token=witness.occurrence_token,
                    contribution_tick=witness.tick,
                    carrier_kind=service_row.carrier_kind,
                    carrier_token=service_row.carrier_token,
                )
            )
    enriched: list[PracticeOrganizationFact] = []
    for fact in facts:
        enriched.append(replace(fact, links=tuple(links[fact.organization_id])))
    assigned = len(execution_targets) + len(service_targets)
    total = len(execution_by_token) + len(service_by_token)
    unassigned = max(0, total - assigned)
    return enriched, unassigned, ambiguous


def _supplements(
    window: ScientificInstitutionWindowEvidence,
    facts: Sequence[PracticeOrganizationFact],
    *,
    run_id: str,
    endpoint: ScientificInstitutionBoundaryInput,
    entity_to_agent: Mapping[str, str],
    teaching_audits: Sequence[object] | None,
    config: SimulationRunnerConfig,
) -> list[PracticeSupplementFact]:
    supplements: list[PracticeSupplementFact] = []
    tick_by_execution = {
        row.occurrence_token: row.tick for row in window.executions
    }
    tick_by_service = {
        row.occurrence_token: row for row in window.carriers
    }
    surviving = _surviving_tokens(window.surviving_carriers)
    for fact in facts:
        execution_links = [
            link for link in fact.links if link.execution_token is not None
        ]
        if execution_links:
            supplements.append(
                PracticeSupplementFact(
                    run_id=run_id,
                    window_index=window.window.window_index,
                    organization_id=fact.organization_id,
                    signal=PracticeSignalKind.EXPERIMENTER,
                    actor_tokens=tuple(
                        sorted({link.actor_token for link in execution_links})
                    ),
                    carrier_tokens=(),
                    tick=min(
                        tick_by_execution[link.execution_token or ""]
                        for link in execution_links
                    ),
                    count=len(execution_links),
                )
            )
        keeper_links = [
            link
            for link in fact.links
            if link.service_token is not None
            and link.carrier_kind
            in {
                PracticeCarrierKind.RECORD,
                PracticeCarrierKind.ARTIFACT,
                PracticeCarrierKind.REPOSITORY_MEMBER,
            }
        ]
        if keeper_links:
            supplements.append(
                PracticeSupplementFact(
                    run_id=run_id,
                    window_index=window.window.window_index,
                    organization_id=fact.organization_id,
                    signal=PracticeSignalKind.RECORD_KEEPER,
                    actor_tokens=tuple(
                        sorted({link.actor_token for link in keeper_links})
                    ),
                    carrier_tokens=tuple(
                        sorted(
                            {
                                (
                                    link.carrier_kind.value
                                    if link.carrier_kind is not None
                                    else "record",
                                    link.carrier_token or "",
                                )
                                for link in keeper_links
                            }
                        )
                    ),
                    tick=min(
                        tick_by_service[link.service_token or ""].tick
                        for link in keeper_links
                    ),
                    count=len(keeper_links),
                )
            )
        archive_links = [
            link
            for link in fact.links
            if link.service_token is not None
            and link.carrier_kind is PracticeCarrierKind.REPOSITORY_MEMBER
            and (link.carrier_token or "") in surviving
        ]
        if archive_links:
            supplements.append(
                PracticeSupplementFact(
                    run_id=run_id,
                    window_index=window.window.window_index,
                    organization_id=fact.organization_id,
                    signal=PracticeSignalKind.ARCHIVE,
                    actor_tokens=tuple(
                        sorted({link.actor_token for link in archive_links})
                    ),
                    carrier_tokens=tuple(
                        sorted(
                            {
                                ("repository_member", link.carrier_token or "")
                                for link in archive_links
                            }
                        )
                    ),
                    tick=min(
                        tick_by_service[link.service_token or ""].tick
                        for link in archive_links
                    ),
                    count=len(archive_links),
                )
            )
        if fact.procedure_tokens:
            supplements.append(
                PracticeSupplementFact(
                    run_id=run_id,
                    window_index=window.window.window_index,
                    organization_id=fact.organization_id,
                    signal=PracticeSignalKind.PROCEDURE,
                    actor_tokens=fact.claimant_tokens,
                    carrier_tokens=(),
                    tick=window.window.start_tick,
                    count=len(fact.procedure_tokens),
                )
            )
        office_ids = {
            token
            for kind, token in fact.anchor_tokens
            if kind == "office"
        }
        if office_ids:
            supplements.append(
                PracticeSupplementFact(
                    run_id=run_id,
                    window_index=window.window.window_index,
                    organization_id=fact.organization_id,
                    signal=PracticeSignalKind.OFFICE,
                    actor_tokens=fact.claimant_tokens,
                    carrier_tokens=tuple(
                        sorted(("office", token) for token in office_ids)
                    ),
                    tick=window.window.start_tick,
                    count=len(office_ids),
                )
            )
    supplements.extend(
        _teaching_supplements(
            window,
            facts,
            run_id=run_id,
            teaching_audits=teaching_audits,
        )
    )
    supplements.extend(
        _replication_supplements(
            window,
            facts,
            run_id=run_id,
            endpoint=endpoint,
            entity_to_agent=entity_to_agent,
        )
    )
    supplements.extend(
        _instrument_supplements(
            window,
            facts,
            run_id=run_id,
            endpoint=endpoint,
            entity_to_agent=entity_to_agent,
        )
    )
    return supplements


def _unique_candidate(
    facts: Sequence[PracticeOrganizationFact],
    tokens: set[str],
) -> PracticeOrganizationFact | None:
    matches = [
        fact
        for fact in facts
        if tokens and tokens.issubset(set(fact.participant_tokens))
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _teaching_supplements(
    window: ScientificInstitutionWindowEvidence,
    facts: Sequence[PracticeOrganizationFact],
    *,
    run_id: str,
    teaching_audits: Sequence[object] | None,
) -> list[PracticeSupplementFact]:
    if teaching_audits is None:
        return []
    rows: list[PracticeSupplementFact] = []
    for audit in teaching_audits:
        if getattr(getattr(audit, "store", None), "value", None) != _TEACHING_ADVICE:
            continue
        recipient = getattr(audit, "agent_id", None)
        source = getattr(audit, "source_agent_id", None)
        if recipient is None or source is None:
            continue
        tick = getattr(audit, "tick", None)
        if not isinstance(tick, int) or not (
            window.window.start_tick <= tick < window.window.end_exclusive
        ):
            continue
        tokens = {
            _actor_token(run_id, source.value),
            _actor_token(run_id, recipient.value),
        }
        fact = _unique_candidate(facts, tokens)
        if fact is None:
            continue
        rows.append(
            PracticeSupplementFact(
                run_id=run_id,
                window_index=window.window.window_index,
                organization_id=fact.organization_id,
                signal=PracticeSignalKind.TEACHER,
                actor_tokens=tuple(sorted(tokens)),
                carrier_tokens=(),
                tick=tick,
                count=1,
            )
        )
    return rows


def _replication_supplements(
    window: ScientificInstitutionWindowEvidence,
    facts: Sequence[PracticeOrganizationFact],
    *,
    run_id: str,
    endpoint: ScientificInstitutionBoundaryInput,
    entity_to_agent: Mapping[str, str],
) -> list[PracticeSupplementFact]:
    events_by_id = {
        event.event_id.value: event for event in endpoint.boundary.events
    }
    rows: list[PracticeSupplementFact] = []
    ledgers: list[object] = []
    owner_by_ledger: dict[int, str] = {}
    for owner in endpoint.boundary.owners:
        checkpoint = owner.runtime_checkpoint
        ledger = None if checkpoint is None else checkpoint.replication_ledger
        if ledger is None:
            continue
        owner_by_ledger[id(ledger)] = owner.owner_id.value
        ledgers.append(ledger)
        for collaboration in getattr(ledger, "collaborations", ()):
            status = getattr(
                getattr(collaboration, "status", None), "value", None
            )
            if status not in {"accepted", "completed"}:
                continue
            delivery_id = getattr(collaboration, "delivery_event_id", None)
            if delivery_id is None:
                continue
            event = events_by_id.get(delivery_id)
            ticks = [
                event.tick
                for event in (event,)
                if event is not None
                and window.window.start_tick
                <= event.tick
                < window.window.end_exclusive
            ]
            for participant in getattr(collaboration, "participants", ()):
                act = getattr(getattr(participant, "act", None), "value", None)
                if act != "participate":
                    continue
                tick = getattr(participant, "tick", None)
                if isinstance(tick, int) and (
                    window.window.start_tick <= tick < window.window.end_exclusive
                ):
                    ticks.append(tick)
            if not ticks:
                continue
            tokens = {_actor_token(run_id, owner.owner_id.value)}
            inviter = getattr(collaboration, "inviter_entity_id", None)
            if isinstance(inviter, str):
                token = _entity_actor_token(run_id, inviter, entity_to_agent)
                if token is not None:
                    tokens.add(token)
            fact = _unique_candidate(facts, tokens)
            if fact is None:
                continue
            rows.append(
                PracticeSupplementFact(
                    run_id=run_id,
                    window_index=window.window.window_index,
                    organization_id=fact.organization_id,
                    signal=PracticeSignalKind.REPLICATION_EXPECTATION,
                    actor_tokens=tuple(sorted(tokens)),
                    carrier_tokens=(),
                    tick=min(ticks),
                    count=1,
                )
            )
    if not ledgers:
        return rows
    # Linked child executions are counted separately from invitations via the
    # completed-run replication bridge plus exact ExperimentResolved witnesses.
    for ledger in ledgers:
        owner_id = owner_by_ledger.get(id(ledger))
        if owner_id is None:
            continue
        try:
            solo = replication_facts(
                run_id=run_id,
                replication_ledgers=(ledger,),
                events=tuple(endpoint.boundary.events),
            )
        except (TypeError, ValueError):
            continue
        designs = {
            design.design_token: design for design in solo.designs
        }
        practice_actor = _actor_token(run_id, owner_id)
        for attempt in solo.attempts:
            if attempt.collaboration_token is None:
                continue
            design = designs.get(attempt.design_token)
            if design is None:
                continue
            if not (
                window.window.start_tick
                <= attempt.observation_tick
                < window.window.end_exclusive
            ):
                continue
            for event in endpoint.boundary.events:
                if not isinstance(event.details, ExperimentResolved):
                    continue
                if not (
                    window.window.start_tick
                    <= event.tick
                    < window.window.end_exclusive
                ):
                    continue
                actor = (
                    None
                    if event.actor_id is None
                    else event.actor_id.value
                )
                if actor is None:
                    continue
                agent = entity_to_agent.get(actor)
                if agent is None or _actor_token(run_id, agent) != practice_actor:
                    continue
                if (
                    event.details.operator != design.operator
                    or event.details.process_token != design.process_token
                ):
                    continue
                # Confirm the bridge also projected this exact execution.
                if not any(
                    execution.operator == design.operator
                    and execution.process_token == design.process_token
                    and execution.execution_tick == event.tick
                    for execution in solo.executions
                ):
                    continue
                fact = _unique_candidate(facts, {practice_actor})
                if fact is None:
                    continue
                rows.append(
                    PracticeSupplementFact(
                        run_id=run_id,
                        window_index=window.window.window_index,
                        organization_id=fact.organization_id,
                        signal=PracticeSignalKind.REPLICATION_EXPECTATION,
                        actor_tokens=(practice_actor,),
                        carrier_tokens=(),
                        tick=event.tick,
                        count=1,
                    )
                )
    return rows


def _instrument_supplements(
    window: ScientificInstitutionWindowEvidence,
    facts: Sequence[PracticeOrganizationFact],
    *,
    run_id: str,
    endpoint: ScientificInstitutionBoundaryInput,
    entity_to_agent: Mapping[str, str],
) -> list[PracticeSupplementFact]:
    by_instrument: dict[str, list[tuple[str, int]]] = {}
    for event in _window_events(endpoint, window.window):
        details = event.details
        if not isinstance(details, MeasurementTaken):
            continue
        actor = event.actor_id
        if actor is None:
            continue
        token = _entity_actor_token(run_id, actor.value, entity_to_agent)
        if token is None:
            continue
        instrument = details.reading.instrument_id.value
        by_instrument.setdefault(instrument, []).append((token, event.tick))
    rows: list[PracticeSupplementFact] = []
    for instrument, uses in by_instrument.items():
        actors = {token for token, _ in uses}
        if len(actors) < 2:
            continue
        fact = _unique_candidate(facts, actors)
        if fact is None:
            continue
        rows.append(
            PracticeSupplementFact(
                run_id=run_id,
                window_index=window.window.window_index,
                organization_id=fact.organization_id,
                signal=PracticeSignalKind.SHARED_INSTRUMENT,
                actor_tokens=tuple(sorted(actors)),
                carrier_tokens=(
                    ("instrument", _carrier_token(run_id, instrument)),
                ),
                tick=min(tick for _, tick in uses),
                count=len(uses),
            )
        )
    return rows


def _optional_status(
    *,
    enabled: bool,
    base: PracticeCoverageStatus,
) -> PracticeCoverageStatus:
    if not enabled:
        return PracticeCoverageStatus.UNAVAILABLE
    if base is PracticeCoverageStatus.UNAVAILABLE:
        return PracticeCoverageStatus.UNAVAILABLE
    if base is PracticeCoverageStatus.PARTIAL:
        return PracticeCoverageStatus.PARTIAL
    return base


def _combined_window(
    window: ScientificInstitutionWindowEvidence,
    *,
    organization_status: PracticeCoverageStatus,
    config: SimulationRunnerConfig,
    teaching_audits: Sequence[object] | None,
    replication_enabled: bool,
    institutional_memory_enabled: bool,
    office_enabled: bool,
) -> PracticeWindow:
    base = window.window.lane_status(PracticeLane.EXECUTION)
    base = base or PracticeCoverageStatus.UNAVAILABLE
    coverage = list(window.window.coverage)
    coverage.append(
        PracticeCoverage(
            run_id=window.window.run_id,
            window_index=window.window.window_index,
            lane=PracticeLane.ORGANIZATION,
            status=organization_status,
        )
    )
    enabled_lanes = {
        PracticeLane.RECORD: config.durable_records is not None,
        PracticeLane.ARCHIVE: config.knowledge_repositories is not None,
        PracticeLane.TEACHING: teaching_audits is not None,
        PracticeLane.REPLICATION: replication_enabled,
        PracticeLane.INSTRUMENT: config.measurement_instruments is not None,
        PracticeLane.PROCEDURE: True,
        PracticeLane.INSTITUTIONAL_MEMORY: institutional_memory_enabled,
    }
    for lane in OPTIONAL_PRACTICE_LANES:
        practice_lane = PracticeLane(lane)
        coverage.append(
            PracticeCoverage(
                run_id=window.window.run_id,
                window_index=window.window.window_index,
                lane=practice_lane,
                status=_optional_status(
                    enabled=(
                        enabled_lanes.get(practice_lane, False)
                        if practice_lane is not PracticeLane.OFFICE
                        else office_enabled
                    ),
                    base=base,
                ),
            )
        )
    return PracticeWindow(
        run_id=window.window.run_id,
        window_index=window.window.window_index,
        start_tick=window.window.start_tick,
        end_tick_exclusive=window.window.end_exclusive,
        complete=window.window.complete,
        coverage=tuple(coverage),
    )


def build_scientific_institution_context(
    evidence: ScientificInstitutionEvidence,
    boundaries: Sequence[ScientificInstitutionBoundaryInput],
    config: SimulationRunnerConfig,
    *,
    teaching_audits: Sequence[object] | None = None,
) -> ScientificInstitutionContextEvidence:
    """Join objective receipts to exact owner organization context."""

    if type(evidence) is not ScientificInstitutionEvidence:
        raise ScientificInstitutionsError("scientific_institutions_invalid_evidence")
    if isinstance(boundaries, (str, bytes)) or not isinstance(boundaries, Sequence):
        raise ScientificInstitutionsError("scientific_institutions_invalid_boundary")
    if type(config) is not SimulationRunnerConfig:
        raise ScientificInstitutionsError("scientific_institutions_invalid_config")
    entity_to_agent, _ = _identity_maps(boundaries)
    by_tick = {
        item.boundary.boundary_tick.value: item for item in boundaries
    }
    organizations_enabled = bool(config.v4_capability_flags.organizations)
    organization_windows: list[OrganizationWindowEvidence] = []
    window_flags: dict[int, tuple[bool, bool, bool, bool]] = {}
    replication_enabled = False
    institutional_memory_enabled = False
    office_enabled = False
    for item in evidence.windows:
        endpoint = by_tick.get(item.window.end_exclusive)
        if endpoint is None:
            window_flags[item.window.window_index] = (
                False,
                False,
                False,
                False,
            )
            continue
        for owner in endpoint.boundary.owners:
            checkpoint = owner.runtime_checkpoint
            if checkpoint is None:
                continue
            if checkpoint.replication_ledger is not None:
                replication_enabled = True
            if checkpoint.institutional_memory is not None:
                institutional_memory_enabled = True
            if checkpoint.office_concepts is not None:
                office_enabled = True
        if not organizations_enabled:
            window_flags[item.window.window_index] = (
                False,
                False,
                False,
                False,
            )
            continue
        org_window, missing, truncated, available = _organization_window(
            item, endpoint=endpoint
        )
        if org_window is not None:
            organization_windows.append(org_window)
        window_flags[item.window.window_index] = (
            True,
            missing,
            truncated,
            not available,
        )
    detection = (
        detect_organization_candidates_with_contributors(organization_windows)
        if organization_windows
        else None
    )
    assignment = (
        assign_organization_identities(detection.result)
        if detection is not None
        else None
    )
    contributor_map = (
        _candidate_contributors(detection.contributors)
        if detection is not None
        else {}
    )
    by_org_id = {}
    if assignment is not None:
        by_org_id = dict(assignment.candidate_ids)
    candidates_by_window: dict[int, list[OrganizationCandidate]] = {}
    if detection is not None:
        for candidate in detection.result.candidates:
            candidates_by_window.setdefault(
                candidate.window_index, []
            ).append(candidate)
    filtered_by_window: dict[int, tuple[OrganizationHarvestRows, ...]] = {}
    for org_window in organization_windows:
        filtered_by_window[org_window.window_index] = org_window.owner_rows
    windows: list[ScientificInstitutionContextWindow] = []
    for item in evidence.windows:
        endpoint = by_tick.get(item.window.end_exclusive)
        enabled, missing, truncated, unavailable = window_flags.get(
            item.window.window_index, (False, False, False, True)
        )
        if (
            not enabled
            or endpoint is None
            or unavailable
        ):
            status = PracticeCoverageStatus.UNAVAILABLE
            facts: list[PracticeOrganizationFact] = []
            supplements: list[PracticeSupplementFact] = []
            unassigned = 0
            ambiguous = 0
        else:
            status = (
                PracticeCoverageStatus.COMPLETE
                if item.window.complete and not missing and not truncated
                else PracticeCoverageStatus.PARTIAL
            )
            filtered_rows = filtered_by_window.get(
                item.window.window_index, ()
            )
            candidates = candidates_by_window.get(
                item.window.window_index, []
            )
            facts = []
            for candidate in candidates:
                organization_id = by_org_id.get(candidate.candidate_key)
                if organization_id is None:
                    status = PracticeCoverageStatus.PARTIAL
                    continue
                owners = contributor_map.get(
                    candidate.candidate_key, ()
                )
                if not owners:
                    status = PracticeCoverageStatus.PARTIAL
                    continue
                fact = _candidate_tokens(
                    _CandidateView(
                        candidate=candidate,
                        organization_id=organization_id,
                        local_concept_ids=owners,
                    ),
                    run_id=evidence.run_id,
                    entity_to_agent=entity_to_agent,
                    filtered_rows=filtered_rows,
                )
                facts.append(replace(fact, coverage=status))
            events = _window_events(endpoint, item.window)
            contributions = _contributions(
                events,
                run_id=evidence.run_id,
                entity_to_agent=entity_to_agent,
            )
            facts, unassigned, ambiguous = _build_links(
                item,
                facts,
                run_id=evidence.run_id,
                contributions=contributions,
                entity_to_agent=entity_to_agent,
            )
            supplements = _supplements(
                item,
                facts,
                run_id=evidence.run_id,
                endpoint=endpoint,
                entity_to_agent=entity_to_agent,
                teaching_audits=teaching_audits,
                config=config,
            )
            if detection is not None and detection.duplicate_candidate_keys:
                if any(
                    key in detection.duplicate_candidate_keys
                    for key in by_org_id
                ):
                    status = PracticeCoverageStatus.PARTIAL
        combined = _combined_window(
            item,
            organization_status=status,
            config=config,
            teaching_audits=teaching_audits,
            replication_enabled=replication_enabled,
            institutional_memory_enabled=institutional_memory_enabled,
            office_enabled=office_enabled,
        )
        windows.append(
            ScientificInstitutionContextWindow(
                window=combined,
                executions=item.executions,
                carriers=item.carriers,
                surviving_carriers=item.surviving_carriers,
                organizations=tuple(facts),
                supplements=tuple(supplements),
                unassigned=unassigned,
                ambiguous=ambiguous,
            )
        )
    _LOG.debug(
        "scientific_institutions_context run_id=%s windows=%s organizations=%s "
        "supplements=%s unassigned=%s ambiguous=%s",
        evidence.run_id,
        len(windows),
        sum(len(item.organizations) for item in windows),
        sum(len(item.supplements) for item in windows),
        sum(item.unassigned for item in windows),
        sum(item.ambiguous for item in windows),
    )
    return ScientificInstitutionContextEvidence(
        run_id=evidence.run_id,
        windows=tuple(windows),
    )


