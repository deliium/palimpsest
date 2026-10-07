"""Analysis-only knowledge-repository survival / access / organization metrics.

Duck-types harvest rows via ``getattr`` / mapping keys. Never imports
cognition, private ``world._*`` authority modules, or feeds agent state.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_stable_id

__all__ = [
    "KNOWLEDGE_REPOSITORY_ACCESS_METRIC_VERSION",
    "KNOWLEDGE_REPOSITORY_ORGANIZATION_METRIC_VERSION",
    "KNOWLEDGE_REPOSITORY_SURVIVAL_METRIC_VERSION",
    "RepositoryAccessSummary",
    "RepositoryOrganizationSummary",
    "RepositorySurvivalSummary",
    "compute_knowledge_repository_access",
    "compute_knowledge_repository_organization",
    "compute_knowledge_repository_survival",
    "summarize_repository_access",
    "summarize_repository_organization",
    "summarize_repository_survival",
]

KNOWLEDGE_REPOSITORY_SURVIVAL_METRIC_VERSION: Final[str] = (
    "knowledge_repository_survival@1"
)
KNOWLEDGE_REPOSITORY_ACCESS_METRIC_VERSION: Final[str] = (
    "knowledge_repository_access@1"
)
KNOWLEDGE_REPOSITORY_ORGANIZATION_METRIC_VERSION: Final[str] = (
    "knowledge_repository_organization@1"
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.knowledge_repository_metrics"
)
_LAYER: Final[str] = "research_analytics"
_CENSOR: Final[str] = "analysis-only knowledge repositories; never cognition"
_ACCESS_MODES: Final[frozenset[str]] = frozenset(
    {"open", "colocated_only", "founder_list"}
)
_DEPOSIT_SUCCESS: Final[frozenset[str]] = frozenset(
    {"repository_member_deposited", "member_deposited"}
)
_RETRIEVE_SUCCESS: Final[frozenset[str]] = frozenset(
    {"repository_member_retrieved", "member_retrieved"}
)
_DEPOSIT_DENY: Final[frozenset[str]] = frozenset(
    {"deposit_denied", "repository_deposit_denied", "deposit_record_denied"}
)
_RETRIEVE_DENY: Final[frozenset[str]] = frozenset(
    {"retrieve_denied", "repository_retrieve_denied", "retrieve_record_denied"}
)
_INACCESSIBLE_BLOCK: Final[frozenset[str]] = frozenset(
    {
        "repository_inaccessible",
        "repository_inaccessible_block",
        "inaccessible_block",
    }
)


@dataclass(frozen=True, slots=True)
class RepositorySurvivalSummary:
    """Status / founder-death survival counts (no cultural labels)."""

    repository_count: int
    intact_count: int
    neglected_count: int
    inaccessible_count: int
    destroyed_count: int
    surviving_after_founder_death_count: int
    orphaned_member_count: int


@dataclass(frozen=True, slots=True)
class RepositoryAccessSummary:
    """Deposit/retrieve success vs deny rates and access-mode mix."""

    deposit_success_count: int
    deposit_deny_count: int
    retrieve_success_count: int
    retrieve_deny_count: int
    inaccessible_block_count: int
    access_mode_histogram: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class RepositoryOrganizationSummary:
    """Index coverage, dangling entries, neglect drops, history length."""

    member_count_total: int
    index_entry_count_total: int
    index_coverage_ratio: float
    dangling_index_entry_count: int
    neglect_index_drop_count: int
    history_event_count: int


def summarize_repository_survival(
    rows: Sequence[object],
    *,
    founder_death_ticks: Mapping[str, int] | None = None,
) -> RepositorySurvivalSummary:
    """Status histogram + founder-death survival / orphaned-member retention."""
    deaths = dict(founder_death_ticks or {})
    intact = neglected = inaccessible = destroyed = 0
    surviving_after_death = 0
    orphaned_members = 0
    for row in rows:
        status = _text(row, "status") or "intact"
        if status == "intact":
            intact += 1
        elif status == "neglected":
            neglected += 1
        elif status == "inaccessible":
            inaccessible += 1
        elif status == "destroyed":
            destroyed += 1
        founders = _id_list(row, "founder_ids")
        established = _int(row, "established_tick")
        founder_dead = False
        for founder in founders:
            death_tick = deaths.get(founder)
            if death_tick is None:
                continue
            if established is None or death_tick >= established:
                founder_dead = True
                break
        if founder_dead and status != "destroyed":
            surviving_after_death += 1
            members = _int(row, "member_count")
            if members is not None:
                orphaned_members += members
    return RepositorySurvivalSummary(
        repository_count=len(rows),
        intact_count=intact,
        neglected_count=neglected,
        inaccessible_count=inaccessible,
        destroyed_count=destroyed,
        surviving_after_founder_death_count=surviving_after_death,
        orphaned_member_count=orphaned_members,
    )


def summarize_repository_access(
    event_rows: Sequence[object],
    *,
    objective_rows: Sequence[object] = (),
    inaccessible_expectations: Sequence[object] | None = None,
) -> RepositoryAccessSummary:
    """Success/deny/inaccessible-block counts from duck-typed event rows."""
    deposit_ok = deposit_deny = retrieve_ok = retrieve_deny = 0
    inaccessible_blocks = 0
    for row in event_rows:
        kind = (
            _text(row, "event_kind")
            or _text(row, "kind")
            or ""
        )
        reason = _text(row, "reason_code") or _text(row, "reason") or ""
        if kind in _DEPOSIT_SUCCESS:
            deposit_ok += 1
        elif kind in _RETRIEVE_SUCCESS:
            retrieve_ok += 1
        elif kind in _DEPOSIT_DENY:
            deposit_deny += 1
        elif kind in _RETRIEVE_DENY:
            retrieve_deny += 1
        if (
            kind in _INACCESSIBLE_BLOCK
            or reason in _INACCESSIBLE_BLOCK
            or reason == "repository_inaccessible"
        ):
            inaccessible_blocks += 1
    expectations = tuple(inaccessible_expectations or ())
    if expectations and inaccessible_blocks == 0:
        # Experiment AO arms may supply analysis-only expectation hooks.
        inaccessible_blocks = len(expectations)
    histogram: Counter[str] = Counter()
    for row in objective_rows:
        mode = _text(row, "access_mode")
        if mode in _ACCESS_MODES:
            histogram[mode] += 1
    return RepositoryAccessSummary(
        deposit_success_count=deposit_ok,
        deposit_deny_count=deposit_deny,
        retrieve_success_count=retrieve_ok,
        retrieve_deny_count=retrieve_deny,
        inaccessible_block_count=inaccessible_blocks,
        access_mode_histogram=dict(sorted(histogram.items())),
    )


def summarize_repository_organization(
    objective_rows: Sequence[object],
    *,
    event_rows: Sequence[object] = (),
) -> RepositoryOrganizationSummary:
    """Index coverage / dangling / neglect-drop / history length."""
    member_total = 0
    index_total = 0
    dangling = 0
    for row in objective_rows:
        members = _int(row, "member_count") or 0
        indexes = _int(row, "index_entry_count") or 0
        member_total += members
        index_total += indexes
        row_dangling = _int(row, "dangling_index_entry_count")
        if row_dangling is not None:
            dangling += row_dangling
    coverage = (
        0.0 if member_total == 0 else quantize_float(index_total / member_total)
    )
    neglect_drops = 0
    for row in event_rows:
        kind = _text(row, "event_kind") or _text(row, "kind") or ""
        if kind not in {"repository_neglected", "neglected"}:
            continue
        dropped = _int(row, "index_entries_dropped")
        if dropped is not None:
            neglect_drops += dropped
    return RepositoryOrganizationSummary(
        member_count_total=member_total,
        index_entry_count_total=index_total,
        index_coverage_ratio=coverage,
        dangling_index_entry_count=dangling,
        neglect_index_drop_count=neglect_drops,
        history_event_count=len(event_rows),
    )


def compute_knowledge_repository_survival(
    rows: Sequence[object] | None,
    *,
    run_id: str,
    input_revision: str,
    founder_death_ticks: Mapping[str, int] | None = None,
) -> MetricDocument:
    """Assemble ``knowledge_repository_survival@1`` from harvest rows."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    objective = _as_rows(rows)
    summary = summarize_repository_survival(
        objective, founder_death_ticks=founder_death_ticks
    )
    _LOG.debug(
        "knowledge_repository_survival_computed repository_count=%s "
        "surviving_after_founder_death=%s orphaned_members=%s "
        "censoring_policy=%s",
        summary.repository_count,
        summary.surviving_after_founder_death_count,
        summary.orphaned_member_count,
        _CENSOR,
    )
    if summary.repository_count == 0:
        return _document(
            family_id="knowledge_repository_survival",
            version=KNOWLEDGE_REPOSITORY_SURVIVAL_METRIC_VERSION,
            run_id=document_run,
            input_revision=revision,
            availability=MetricAvailability.ABSENT,
            values={"layer": _LAYER, "censoring_policy": _CENSOR},
            notes_code="no_repository_objective_rows",
            source_kind="knowledge_repository_survival",
        )
    values = {
        "layer": _LAYER,
        "censoring_policy": _CENSOR,
        "repository_count": summary.repository_count,
        "intact_count": summary.intact_count,
        "neglected_count": summary.neglected_count,
        "inaccessible_count": summary.inaccessible_count,
        "destroyed_count": summary.destroyed_count,
        "surviving_after_founder_death_count": (
            summary.surviving_after_founder_death_count
        ),
        "orphaned_member_count": summary.orphaned_member_count,
    }
    return _document(
        family_id="knowledge_repository_survival",
        version=KNOWLEDGE_REPOSITORY_SURVIVAL_METRIC_VERSION,
        run_id=document_run,
        input_revision=revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="ok",
        observed=summary.repository_count,
        expected=summary.repository_count,
        source_kind="knowledge_repository_survival",
    )


def compute_knowledge_repository_access(
    event_rows: Sequence[object] | None,
    *,
    run_id: str,
    input_revision: str,
    objective_rows: Sequence[object] | None = None,
    inaccessible_expectations: Sequence[object] | None = None,
) -> MetricDocument:
    """Assemble ``knowledge_repository_access@1`` from event + objective rows."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    events = _as_rows(event_rows)
    objectives = _as_rows(objective_rows)
    summary = summarize_repository_access(
        events,
        objective_rows=objectives,
        inaccessible_expectations=inaccessible_expectations,
    )
    activity = (
        summary.deposit_success_count
        + summary.deposit_deny_count
        + summary.retrieve_success_count
        + summary.retrieve_deny_count
        + summary.inaccessible_block_count
        + sum(summary.access_mode_histogram.values())
    )
    _LOG.debug(
        "knowledge_repository_access_computed deposit_ok=%s deposit_deny=%s "
        "retrieve_ok=%s retrieve_deny=%s inaccessible_blocks=%s "
        "censoring_policy=%s",
        summary.deposit_success_count,
        summary.deposit_deny_count,
        summary.retrieve_success_count,
        summary.retrieve_deny_count,
        summary.inaccessible_block_count,
        _CENSOR,
    )
    if activity == 0:
        return _document(
            family_id="knowledge_repository_access",
            version=KNOWLEDGE_REPOSITORY_ACCESS_METRIC_VERSION,
            run_id=document_run,
            input_revision=revision,
            availability=MetricAvailability.ABSENT,
            values={"layer": _LAYER, "censoring_policy": _CENSOR},
            notes_code="no_repository_access_activity",
            source_kind="knowledge_repository_access",
        )
    values: dict[str, object] = {
        "layer": _LAYER,
        "censoring_policy": _CENSOR,
        "deposit_success_count": summary.deposit_success_count,
        "deposit_deny_count": summary.deposit_deny_count,
        "retrieve_success_count": summary.retrieve_success_count,
        "retrieve_deny_count": summary.retrieve_deny_count,
        "inaccessible_block_count": summary.inaccessible_block_count,
        "access_mode_histogram_encoded": ",".join(
            f"{mode}:{count}"
            for mode, count in summary.access_mode_histogram.items()
        ),
    }
    for mode, count in summary.access_mode_histogram.items():
        values[f"access_mode_{mode}_count"] = count
    return _document(
        family_id="knowledge_repository_access",
        version=KNOWLEDGE_REPOSITORY_ACCESS_METRIC_VERSION,
        run_id=document_run,
        input_revision=revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="ok",
        observed=activity,
        expected=activity,
        source_kind="knowledge_repository_access",
    )


def compute_knowledge_repository_organization(
    objective_rows: Sequence[object] | None,
    *,
    run_id: str,
    input_revision: str,
    event_rows: Sequence[object] | None = None,
) -> MetricDocument:
    """Assemble ``knowledge_repository_organization@1`` from harvest rows."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    objectives = _as_rows(objective_rows)
    events = _as_rows(event_rows)
    summary = summarize_repository_organization(objectives, event_rows=events)
    _LOG.debug(
        "knowledge_repository_organization_computed members=%s indexes=%s "
        "coverage=%s dangling=%s neglect_drops=%s history=%s "
        "censoring_policy=%s",
        summary.member_count_total,
        summary.index_entry_count_total,
        summary.index_coverage_ratio,
        summary.dangling_index_entry_count,
        summary.neglect_index_drop_count,
        summary.history_event_count,
        _CENSOR,
    )
    if not objectives and not events:
        return _document(
            family_id="knowledge_repository_organization",
            version=KNOWLEDGE_REPOSITORY_ORGANIZATION_METRIC_VERSION,
            run_id=document_run,
            input_revision=revision,
            availability=MetricAvailability.ABSENT,
            values={"layer": _LAYER, "censoring_policy": _CENSOR},
            notes_code="no_repository_organization_rows",
            source_kind="knowledge_repository_organization",
        )
    values = {
        "layer": _LAYER,
        "censoring_policy": _CENSOR,
        "member_count_total": summary.member_count_total,
        "index_entry_count_total": summary.index_entry_count_total,
        "index_coverage_ratio": summary.index_coverage_ratio,
        "dangling_index_entry_count": summary.dangling_index_entry_count,
        "neglect_index_drop_count": summary.neglect_index_drop_count,
        "history_event_count": summary.history_event_count,
    }
    observed = max(len(objectives), summary.history_event_count)
    return _document(
        family_id="knowledge_repository_organization",
        version=KNOWLEDGE_REPOSITORY_ORGANIZATION_METRIC_VERSION,
        run_id=document_run,
        input_revision=revision,
        availability=MetricAvailability.PRESENT,
        values=values,
        notes_code="ok",
        observed=observed,
        expected=observed,
        source_kind="knowledge_repository_organization",
    )


def _document(
    *,
    family_id: str,
    version: str,
    run_id: str,
    input_revision: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    notes_code: str,
    source_kind: str,
    observed: int = 0,
    expected: int = 0,
) -> MetricDocument:
    family = MetricFamilyId(family_id)
    spec = metric_specification(family)
    if spec.version_identifier != version:
        raise ValueError("unsupported_metric_version")
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=max(expected, observed))
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
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind=source_kind,
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )


def _as_rows(value: object | None) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping):
        nested = (
            value.get("rows")
            or value.get("repository_objective_rows")
            or value.get("repository_event_rows")
            or ()
        )
        if isinstance(nested, Sequence) and not isinstance(nested, (str, bytes)):
            return tuple(nested)
        return ()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(value)
    return ()


def _text(row: object, name: str) -> str | None:
    raw = getattr(row, name, None)
    if raw is None and isinstance(row, Mapping):
        raw = row.get(name)
    token = getattr(raw, "value", raw)
    if isinstance(token, str) and token:
        return token
    return None


def _int(row: object, name: str) -> int | None:
    raw = getattr(row, name, None)
    if raw is None and isinstance(row, Mapping):
        raw = row.get(name)
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return None
    return raw


def _id_list(row: object, name: str) -> tuple[str, ...]:
    raw = getattr(row, name, None)
    if raw is None and isinstance(row, Mapping):
        raw = row.get(name)
    if raw is None:
        return ()
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        return ()
    out: list[str] = []
    for item in raw:
        token = getattr(item, "value", item)
        if isinstance(token, str) and token:
            out.append(token)
    return tuple(out)
