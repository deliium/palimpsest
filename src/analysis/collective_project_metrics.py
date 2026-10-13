"""Counts for shared physical work. No crew label and no leader."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions
from analysis.specifications import MetricFamilyId, metric_specification
from world.collective_projects import CollectiveProjectKind
from world.events import (
    ProjectAbandoned,
    ProjectCompleted,
    ProjectContributed,
    ProjectCreated,
    ProjectShortage,
    WorldEvent,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("analysis.collective_project_metrics")
_LAYER: Final[str] = "research_inference"
_FORBIDDEN: Final[frozenset[str]] = frozenset(
    {
        "leader",
        "leader_id",
        "project_leader",
        "foreman",
        "chief",
        "manager",
        "coordinator_id",
        "crew_boss",
        "institution",
        "work_crew",
        "created_by",
        "archive",
    }
)


def assemble_collective_project_metrics(
    events: Sequence[WorldEvent],
    *,
    run_id: str,
    input_revision: str,
    spec: object | None,
    as_of_tick: int,
) -> tuple[MetricDocument, ...]:
    """Three families. An absent spec writes no rows."""
    if spec is None:
        _LOG.info(
            "collective_project_metrics_empty reason=collective_projects_absent"
        )
        return ()
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    require_exact_nonneg_int("as_of_tick", as_of_tick)
    folded = _fold(events)
    documents = (
        *_progress(folded, document_run, revision),
        _document(
            MetricFamilyId.COLLECTIVE_PROJECT_CONTRIBUTION,
            folded.contribution_values(),
            document_run,
            revision,
        ),
        _document(
            MetricFamilyId.COLLECTIVE_PROJECT_OUTCOME,
            folded.outcome_values(),
            document_run,
            revision,
        ),
    )
    _LOG.debug(
        "collective_project_metrics_assembled completed=%s abandoned=%s "
        "contributors=%s",
        folded.completed,
        folded.abandoned,
        folded.distinct_contributors,
    )
    return documents


class _Fold:
    def __init__(self) -> None:
        self.by_kind: dict[str, list[tuple[int, int, int, int]]] = {
            kind.value: [] for kind in CollectiveProjectKind
        }
        self.required: dict[str, tuple[str, int, int]] = {}
        self.done: dict[str, tuple[int, int]] = {}
        self.completed_ids: set[str] = set()
        self.abandoned_ids: set[str] = set()
        self.accepted_actors: set[str] = set()
        self.accepted = 0
        self.shortages = 0

    def contribution_values(self) -> dict[str, object]:
        return {
            "layer": _LAYER,
            "distinct_contributor_count": len(self.accepted_actors),
            "accepted_contribution_count": self.accepted,
            "shortage_count": self.shortages,
            "contribution_num": self.accepted,
            "contribution_den": self.accepted + self.shortages,
        }

    def outcome_values(self) -> dict[str, object]:
        open_count = len(self.required) - self.completed - self.abandoned
        return {
            "layer": _LAYER,
            "completed_count": self.completed,
            "abandoned_count": self.abandoned,
            "open_count": open_count,
            "outcome_num": self.completed,
            "outcome_den": self.completed + self.abandoned + open_count,
        }

    @property
    def completed(self) -> int:
        return len(self.completed_ids)

    @property
    def abandoned(self) -> int:
        return len(self.abandoned_ids)

    @property
    def distinct_contributors(self) -> int:
        return len(self.accepted_actors)


def _fold(events: Sequence[WorldEvent]) -> _Fold:
    folded = _Fold()
    for event in events:
        details = event.details
        if type(details) is ProjectCreated:
            folded.required[details.project_id.value] = (
                details.project_kind,
                details.labor_required,
                details.materials_required,
            )
            folded.done.setdefault(details.project_id.value, (0, 0))
        elif type(details) is ProjectContributed:
            folded.done[details.project_id.value] = (
                details.labor_done,
                details.materials_done,
            )
            if details.accepted:
                folded.accepted += 1
                folded.accepted_actors.add(details.actor_id.value)
        elif type(details) is ProjectShortage:
            folded.shortages += 1
        elif type(details) is ProjectAbandoned:
            folded.abandoned_ids.add(details.project_id.value)
        elif type(details) is ProjectCompleted:
            folded.completed_ids.add(details.project_id.value)
    for project_id, required in folded.required.items():
        kind, labor_required, materials_required = required
        labor_done, materials_done = folded.done.get(project_id, (0, 0))
        folded.by_kind.setdefault(kind, []).append(
            (labor_done, labor_required, materials_done, materials_required)
        )
    return folded


def _progress(folded: _Fold, run_id: str, revision: str) -> tuple[MetricDocument, ...]:
    documents: list[MetricDocument] = []
    for kind in sorted(folded.by_kind):
        rows = folded.by_kind[kind]
        labor_done = sum(row[0] for row in rows)
        labor_required = sum(row[1] for row in rows)
        materials_done = sum(row[2] for row in rows)
        materials_required = sum(row[3] for row in rows)
        documents.append(
            _document(
                MetricFamilyId.COLLECTIVE_PROJECT_PROGRESS,
                {
                    "layer": _LAYER,
                    "project_kind": kind,
                    "labor_done": labor_done,
                    "labor_required": labor_required,
                    "materials_done": materials_done,
                    "materials_required": materials_required,
                    "labor_num": labor_done,
                    "labor_den": labor_required,
                    "materials_num": materials_done,
                    "materials_den": materials_required,
                },
                run_id,
                revision,
            )
        )
    return tuple(documents)


def _document(
    family: MetricFamilyId,
    values: dict[str, object],
    run_id: str,
    revision: str,
) -> MetricDocument:
    blocked = set(values) & _FORBIDDEN
    if blocked:
        raise ValueError("collective_project_metrics forbidden key")
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
            source_kind="collective_projects",
            source_ids=(run_id,),
            notes_code="ok",
        ),
    )
