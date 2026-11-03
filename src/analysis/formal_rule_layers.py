"""Three separated detached formal-rule layers with a hard leakage guard."""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Final, NoReturn

from analysis.formal_rule_contract import (
    FormalRuleAnalysisError,
    FormalRuleCandidateStatus,
    FormalRuleCoverage,
    require_formal_rule_candidate_id,
)
from analysis.formal_rule_lineage import FormalRuleAnalysis, FormalRuleSummary
from analysis.formal_rules import FormalRuleHarvestRows

__all__ = [
    "FormalRuleAnalyticalRow",
    "FormalRuleLayerView",
    "FormalRuleObjectiveRow",
    "FormalRuleSubjectiveRow",
    "assert_formal_rule_layer_separation",
    "formal_rule_layer_digest",
    "project_formal_rule_layers",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.formal_rule_layers")


@dataclass(frozen=True, slots=True)
class FormalRuleObjectiveRow:
    tick: int
    observed_artifact_count: int
    observed_repository_count: int
    observed_occurrence_count: int


@dataclass(frozen=True, slots=True)
class FormalRuleSubjectiveRow:
    owner_id: str
    system_ids: tuple[str, ...]
    rule_ids: tuple[str, ...]
    stage_counts: tuple[tuple[str, int], ...]
    status_counts: tuple[tuple[str, int], ...]
    response_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class FormalRuleAnalyticalRow:
    candidate_id: str
    status: FormalRuleCandidateStatus
    scope_kind: str
    action_token: str
    constraint_kinds: tuple[str, ...]
    stage: str
    rule_count: int
    version_count: int
    competing_candidate_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        require_formal_rule_candidate_id(self.candidate_id)
        object.__setattr__(
            self,
            "competing_candidate_ids",
            tuple(sorted(set(self.competing_candidate_ids))),
        )


@dataclass(frozen=True, slots=True)
class FormalRuleLayerView:
    objective: tuple[FormalRuleObjectiveRow, ...]
    subjective: tuple[FormalRuleSubjectiveRow, ...]
    analytical: tuple[FormalRuleAnalyticalRow, ...]
    summary: FormalRuleSummary
    coverage: FormalRuleCoverage


def project_formal_rule_layers(
    rows: FormalRuleHarvestRows,
    analysis: FormalRuleAnalysis,
    summary: FormalRuleSummary,
    *,
    windows: tuple[object, ...] = (),
) -> FormalRuleLayerView:
    """Project objective counts, owner claims, and candidates separately."""

    if type(rows) is not FormalRuleHarvestRows:
        raise TypeError("rows must be FormalRuleHarvestRows")
    if type(analysis) is not FormalRuleAnalysis:
        raise TypeError("analysis must be FormalRuleAnalysis")
    if type(summary) is not FormalRuleSummary:
        raise TypeError("summary must be FormalRuleSummary")
    objective_rows: list[FormalRuleObjectiveRow] = []
    source_windows = windows or analysis.windows
    for window in source_windows:
        end_tick = getattr(window, "end_tick", 0)
        artifacts = 0
        repositories = 0
        occurrences = 0
        for anchor in getattr(window, "objective_rows", ()):
            artifacts += anchor.observed_artifact_count
            repositories += anchor.observed_repository_count
            occurrences += anchor.observed_occurrence_count
        objective_rows.append(
            FormalRuleObjectiveRow(
                tick=end_tick,
                observed_artifact_count=artifacts,
                observed_repository_count=repositories,
                observed_occurrence_count=occurrences,
            )
        )
    subjective: list[FormalRuleSubjectiveRow] = []
    for owner in rows.owners:
        owner_rules = [
            row for row in rows.rules if row.owner_id == owner.owner_id
        ]
        owner_responses = [
            row for row in rows.responses if row.owner_id == owner.owner_id
        ]
        subjective.append(
            FormalRuleSubjectiveRow(
                owner_id=owner.owner_id,
                system_ids=tuple(
                    sorted(
                        {
                            row.system_id
                            for row in rows.systems
                            if row.owner_id == owner.owner_id
                        }
                    )
                ),
                rule_ids=tuple(sorted(row.rule_id for row in owner_rules)),
                stage_counts=tuple(
                    sorted(Counter(row.stage for row in owner_rules).items())
                ),
                status_counts=tuple(
                    sorted(Counter(row.status for row in owner_rules).items())
                ),
                response_counts=tuple(
                    sorted(Counter(row.kind for row in owner_responses).items())
                ),
            )
        )
    analytical: list[FormalRuleAnalyticalRow] = []
    for candidate in analysis.candidates:
        members = tuple(
            row
            for row in rows.rules
            if row.rule_id in set(candidate.rule_ids)
        )
        competitors = tuple(
            sorted(
                other.candidate_key
                for other in analysis.candidates
                if other.candidate_key != candidate.candidate_key
                and other.scope_digest == candidate.scope_digest
                and other.action_token == candidate.action_token
            )
        )
        analytical.append(
            FormalRuleAnalyticalRow(
                candidate_id=candidate.candidate_key,
                status=candidate.status,
                scope_kind=candidate.scope_kind,
                action_token=candidate.action_token,
                constraint_kinds=tuple(
                    sorted({row.constraint_kind for row in members})
                ),
                stage=(
                    max(
                        (row.stage for row in members),
                        key=lambda value: (
                            "habit",
                            "expectation",
                            "norm",
                            "documented",
                            "recognized_enforcement",
                        ).index(value),
                    )
                    if members
                    else "habit"
                ),
                rule_count=len(candidate.rule_ids),
                version_count=sum(
                    1 for row in rows.versions if row.rule_id in set(candidate.rule_ids)
                ),
                competing_candidate_ids=competitors,
            )
        )
    view = FormalRuleLayerView(
        objective=tuple(objective_rows),
        subjective=tuple(subjective),
        analytical=tuple(analytical),
        summary=summary,
        coverage=summary.coverage,
    )
    assert_formal_rule_layer_separation(view)
    _LOG.info(
        "formal_rule_layers objective=%s subjective=%s analytical=%s",
        len(view.objective),
        len(view.subjective),
        len(view.analytical),
    )
    return view


def _leak(field_name: str) -> NoReturn:
    _LOG.error(
        "formal_rule_layer_leakage field=%s reason_code=formal_rule_layer_leakage",
        field_name,
    )
    raise FormalRuleAnalysisError("formal_rule_layer_leakage")


def assert_formal_rule_layer_separation(view: FormalRuleLayerView) -> None:
    """Fail closed when ids, owner claims, or candidates cross layers."""

    if type(view) is not FormalRuleLayerView:
        raise TypeError("view must be FormalRuleLayerView")
    for objective_row in view.objective:
        if not all(
            type(value) is int
            for value in (
                objective_row.observed_artifact_count,
                objective_row.observed_repository_count,
                objective_row.observed_occurrence_count,
            )
        ):
            _leak("objective")
    for subjective_row in view.subjective:
        require_owner_token(subjective_row.owner_id)
        for rule_id in subjective_row.rule_ids:
            if rule_id.startswith("frule-"):
                _leak("subjective")
        for system_id in subjective_row.system_ids:
            if system_id.startswith("frule-"):
                _leak("subjective")
    for analytical_row in view.analytical:
        require_formal_rule_candidate_id(analytical_row.candidate_id)
        for other in analytical_row.competing_candidate_ids:
            require_formal_rule_candidate_id(other)
    for candidate_id in view.summary.candidates:
        if candidate_id.startswith(("org-", "msoc-")):
            _leak("analytical")


def require_owner_token(value: object) -> str:
    if not isinstance(value, str) or not value:
        _leak("subjective")
    if value.startswith(("frule-", "org-", "msoc-")):
        _leak("subjective")
    return value


def formal_rule_layer_digest(view: FormalRuleLayerView) -> str:
    """Return an order-independent digest of the layer view."""

    if type(view) is not FormalRuleLayerView:
        raise TypeError("view must be FormalRuleLayerView")
    material = [
        *(f"o:{row.tick}:{row.observed_artifact_count}" for row in view.objective),
        *(f"s:{row.owner_id}:{row.rule_ids}" for row in view.subjective),
        *(f"a:{row.candidate_id}:{row.status.value}" for row in view.analytical),
    ]
    return hashlib.sha256("\x1f".join(sorted(material)).encode("utf-8")).hexdigest()
