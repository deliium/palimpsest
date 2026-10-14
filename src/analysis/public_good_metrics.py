"""Event-folded counts for public goods and their linked structures."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions
from analysis.objective_metrics import resource_inequality_gini
from analysis.specifications import MetricFamilyId, metric_specification
from world.collective_projects import PUBLIC_GOOD_KINDS
from world.events import (
    ProjectAbandoned,
    ProjectCompleted,
    ProjectContributed,
    ProjectCreated,
    PublicGoodBenefit,
    PublicGoodMaintained,
    PublicGoodOpposed,
    WorldEvent,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.public_good_metrics")
_LAYER: Final[str] = "research_inference"
_PUBLIC_KINDS: Final[tuple[str, ...]] = tuple(
    sorted(kind.value for kind in PUBLIC_GOOD_KINDS)
)


@dataclass(slots=True)
class _ProjectFold:
    kind: str
    status: str = "open"
    structure_id: str | None = None
    decay_millis: int = 0
    labor: Counter[str] = field(default_factory=Counter)
    actors: set[str] = field(default_factory=set)
    benefits: Counter[str] = field(default_factory=Counter)


@dataclass(slots=True)
class _Fold:
    projects: dict[str, _ProjectFold]
    maintain_attempts: int = 0
    maintain_accepted: int = 0
    oppose_count: int = 0
    maintain_actors: set[str] = field(default_factory=set)
    oppose_actors: set[str] = field(default_factory=set)
    accepted_ticks: set[int] = field(default_factory=set)
    integrity_by_structure: dict[str, int] = field(default_factory=dict)
    decay_tick_count: int = 0


def assemble_public_good_metrics(
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    input_revision: str,
    spec: object | None,
    as_of_tick: int,
) -> tuple[MetricDocument, ...]:
    """Assemble the five public-good families when the channel spec is present."""
    if spec is None:
        _LOG.info("public_good_metrics_empty reason=public_goods_absent")
        return ()
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    window_end = require_exact_nonneg_int("as_of_tick", as_of_tick)
    folded = _fold(events, as_of_tick=window_end)
    documents = (
        *_inequality_documents(folded, document_run, revision),
        *_benefit_documents(folded, document_run, revision),
        _document(
            MetricFamilyId.PUBLIC_GOOD_MAINTENANCE_BURDEN,
            {
                "layer": _LAYER,
                "maintain_attempt_count": folded.maintain_attempts,
                "maintain_accepted_count": folded.maintain_accepted,
                "oppose_count": folded.oppose_count,
                "decay_tick_count": folded.decay_tick_count,
                "integrity_millis_sum": sum(folded.integrity_by_structure.values()),
            },
            document_run,
            revision,
        ),
        _document(
            MetricFamilyId.PUBLIC_GOOD_FREE_RIDER_PATTERN,
            _pattern_values(folded),
            document_run,
            revision,
        ),
        _document(
            MetricFamilyId.PUBLIC_GOOD_COOPERATION_STABILITY,
            _stability_values(folded, window_end),
            document_run,
            revision,
        ),
    )
    benefits = sum(
        sum(project.benefits.values()) for project in folded.projects.values()
    )
    _LOG.debug(
        "public_good_metrics_assembled benefits=%s maintains=%s opposes=%s",
        benefits,
        folded.maintain_attempts,
        folded.oppose_count,
    )
    return documents


def _fold(events: Sequence[WorldEvent], *, as_of_tick: int) -> _Fold:
    ordered = tuple(
        sorted(
            (event for event in events if event.tick <= as_of_tick),
            key=lambda event: (event.tick, event.sequence, event.event_id.value),
        )
    )
    project_kinds: dict[str, str] = {}
    for event in ordered:
        details = event.details
        if type(details) is ProjectCreated:
            project_kinds[details.project_id.value] = details.project_kind
        elif type(details) is ProjectCompleted:
            project_kinds[details.project_id.value] = details.project_kind
    projects = {
        project_id: _ProjectFold(kind)
        for project_id, kind in project_kinds.items()
        if kind in _PUBLIC_KINDS
    }
    folded = _Fold(projects)
    events_by_tick: dict[int, list[WorldEvent]] = defaultdict(list)
    for event in ordered:
        events_by_tick[event.tick].append(event)
    for tick in range(as_of_tick + 1):
        presence_structures: set[str] = set()
        for event in events_by_tick.get(tick, ()):
            details = event.details
            project_id = getattr(getattr(details, "project_id", None), "value", "")
            project = projects.get(project_id)
            if project is None:
                continue
            if type(details) is ProjectContributed:
                actor_id = details.actor_id.value
                project.actors.add(actor_id)
                if details.accepted:
                    project.labor[actor_id] += 1
                    folded.accepted_ticks.add(tick)
            elif type(details) is ProjectCompleted:
                project.status = "completed"
                project.decay_millis = details.decay_millis or 0
                if details.structure_id is not None:
                    project.structure_id = details.structure_id.value
                    folded.integrity_by_structure[project.structure_id] = 1000
            elif type(details) is ProjectAbandoned:
                project.status = "abandoned"
            elif type(details) is PublicGoodBenefit:
                actor_id = details.actor_id.value
                project.actors.add(actor_id)
                project.benefits[actor_id] += 1
                _set_integrity(folded, project, details.integrity_millis)
                if details.source == "presence" and project.structure_id is not None:
                    presence_structures.add(project.structure_id)
            elif type(details) is PublicGoodMaintained:
                actor_id = details.actor_id.value
                project.actors.add(actor_id)
                folded.maintain_attempts += 1
                folded.maintain_actors.add(actor_id)
                if details.accepted:
                    folded.maintain_accepted += 1
                _set_integrity(folded, project, details.integrity_millis)
            elif type(details) is PublicGoodOpposed:
                actor_id = details.actor_id.value
                project.actors.add(actor_id)
                folded.oppose_count += 1
                folded.oppose_actors.add(actor_id)
                _set_integrity(folded, project, details.integrity_millis)
        decayed = False
        seen_structures: set[str] = set()
        for project in projects.values():
            structure_id = project.structure_id
            if (
                structure_id is None
                or structure_id in seen_structures
                or structure_id in presence_structures
                or project.decay_millis <= 0
            ):
                continue
            seen_structures.add(structure_id)
            integrity = folded.integrity_by_structure.get(structure_id)
            if integrity is None or integrity <= 0:
                continue
            folded.integrity_by_structure[structure_id] = max(
                0, integrity - project.decay_millis
            )
            decayed = True
        if decayed:
            folded.decay_tick_count += 1
    return folded


def _set_integrity(folded: _Fold, project: _ProjectFold, value: int) -> None:
    if project.structure_id is not None:
        folded.integrity_by_structure[project.structure_id] = value


def _inequality_documents(
    folded: _Fold, run_id: str, revision: str
) -> tuple[MetricDocument, ...]:
    documents: list[MetricDocument] = []
    for project_id in sorted(folded.projects):
        project = folded.projects[project_id]
        labor_values = [project.labor[actor_id] for actor_id in sorted(project.actors)]
        contributor_values = [value for value in labor_values if value >= 1]
        gini_millis = (
            0
            if len(labor_values) < 2
            else round(resource_inequality_gini(labor_values) * 1_000_000)
        )
        documents.append(
            _document(
                MetricFamilyId.PUBLIC_GOOD_CONTRIBUTION_INEQUALITY,
                {
                    "layer": _LAYER,
                    "project_id": project_id,
                    "project_kind": project.kind,
                    "contributor_count": len(contributor_values),
                    "recorded_actor_count": len(labor_values),
                    "labor_sum": sum(labor_values),
                    "max_labor": max(contributor_values, default=0),
                    "min_labor": min(contributor_values, default=0),
                    "gini_millis": gini_millis,
                },
                run_id,
                revision,
            )
        )
    return tuple(documents)


def _benefit_documents(
    folded: _Fold, run_id: str, revision: str
) -> tuple[MetricDocument, ...]:
    documents: list[MetricDocument] = []
    for kind in _PUBLIC_KINDS:
        matching = tuple(
            project for project in folded.projects.values() if project.kind == kind
        )
        beneficiaries = {
            actor_id
            for project in matching
            for actor_id, count in project.benefits.items()
            if count >= 1
        }
        contributors = {
            actor_id
            for project in matching
            for actor_id, count in project.labor.items()
            if count >= 1
        }
        documents.append(
            _document(
                MetricFamilyId.PUBLIC_GOOD_BENEFIT_DISTRIBUTION,
                {
                    "layer": _LAYER,
                    "project_kind": kind,
                    "benefit_event_count": sum(
                        sum(project.benefits.values()) for project in matching
                    ),
                    "distinct_beneficiary_count": len(beneficiaries),
                    "beneficiary_without_labor_count": len(
                        beneficiaries - contributors
                    ),
                    "contributor_without_benefit_count": len(
                        contributors - beneficiaries
                    ),
                },
                run_id,
                revision,
            )
        )
    return tuple(documents)


def _pattern_values(folded: _Fold) -> dict[str, object]:
    labor: Counter[str] = Counter()
    benefits: Counter[str] = Counter()
    actors: set[str] = set()
    for project in folded.projects.values():
        labor.update(project.labor)
        benefits.update(project.benefits)
        actors.update(project.actors)
    return {
        "layer": _LAYER,
        "contribute_and_use_count": sum(
            labor[actor_id] >= 1 and benefits[actor_id] >= 1 for actor_id in actors
        ),
        "contribute_low_use_count": sum(
            labor[actor_id] >= 1 and benefits[actor_id] <= 1 for actor_id in actors
        ),
        "use_without_contribution_count": sum(
            benefits[actor_id] >= 1 and labor[actor_id] == 0 for actor_id in actors
        ),
        "oppose_actor_count": len(folded.oppose_actors),
        "maintain_actor_count": len(folded.maintain_actors),
    }


def _stability_values(folded: _Fold, as_of_tick: int) -> dict[str, object]:
    ticks_observed = as_of_tick + 1
    longest_quiet_gap = 0
    current_gap = 0
    for tick in range(ticks_observed):
        if tick in folded.accepted_ticks:
            current_gap = 0
        else:
            current_gap += 1
            longest_quiet_gap = max(longest_quiet_gap, current_gap)
    statuses = Counter(project.status for project in folded.projects.values())
    return {
        "layer": _LAYER,
        "completed_public_count": statuses["completed"],
        "open_public_count": statuses["open"],
        "abandoned_public_count": statuses["abandoned"],
        "ticks_with_accepted_work": len(folded.accepted_ticks),
        "ticks_observed": ticks_observed,
        "longest_quiet_gap": longest_quiet_gap,
    }


def _document(
    family: MetricFamilyId,
    values: dict[str, object],
    run_id: str,
    revision: str,
) -> MetricDocument:
    spec = metric_specification(family)
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=MetricCoverage(observed=1, expected=1),
        availability=MetricAvailability.PRESENT,
        values=values,
        provenance=MetricProvenance(
            source_kind="public_goods",
            source_ids=(run_id,),
            notes_code="ok",
        ),
    )
