"""Knowledge-repository survival / access / organization metric computors."""

from __future__ import annotations

import logging

import pytest

from analysis.knowledge_repository_metrics import (
    KNOWLEDGE_REPOSITORY_ACCESS_METRIC_VERSION,
    KNOWLEDGE_REPOSITORY_ORGANIZATION_METRIC_VERSION,
    KNOWLEDGE_REPOSITORY_SURVIVAL_METRIC_VERSION,
    compute_knowledge_repository_access,
    compute_knowledge_repository_organization,
    compute_knowledge_repository_survival,
    summarize_repository_access,
    summarize_repository_organization,
    summarize_repository_survival,
)
from analysis.models import MetricAvailability

pytestmark = pytest.mark.unit


def test_survival_empty_is_absent() -> None:
    document = compute_knowledge_repository_survival(
        (),
        run_id="run-1",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.ABSENT
    assert document.metric_family == "knowledge_repository_survival"
    assert (
        f"{document.metric_family}@{document.algorithm_version}"
        == KNOWLEDGE_REPOSITORY_SURVIVAL_METRIC_VERSION
    )
    assert document.values["censoring_policy"].startswith("analysis-only")


def test_survival_founder_death_and_status_counts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    rows = (
        {
            "repository_id": "repo-1",
            "status": "intact",
            "access_mode": "open",
            "founder_ids": ("body-founder",),
            "established_tick": 1,
            "member_count": 2,
            "index_entry_count": 1,
        },
        {
            "repository_id": "repo-2",
            "status": "neglected",
            "access_mode": "founder_list",
            "founder_ids": ("body-alive",),
            "established_tick": 2,
            "member_count": 0,
            "index_entry_count": 0,
        },
        {
            "repository_id": "repo-3",
            "status": "destroyed",
            "access_mode": "open",
            "founder_ids": ("body-founder",),
            "established_tick": 0,
            "member_count": 0,
            "index_entry_count": 0,
        },
        {
            "repository_id": "repo-4",
            "status": "inaccessible",
            "access_mode": "colocated_only",
            "founder_ids": ("body-founder",),
            "established_tick": 1,
            "member_count": 3,
            "index_entry_count": 0,
        },
    )
    with caplog.at_level(
        logging.DEBUG, logger="analysis.knowledge_repository_metrics"
    ):
        document = compute_knowledge_repository_survival(
            rows,
            run_id="run-1",
            input_revision="rev-1",
            founder_death_ticks={"body-founder": 5},
        )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["repository_count"] == 4
    assert document.values["intact_count"] == 1
    assert document.values["neglected_count"] == 1
    assert document.values["inaccessible_count"] == 1
    assert document.values["destroyed_count"] == 1
    # intact + inaccessible survive founder death; destroyed does not.
    assert document.values["surviving_after_founder_death_count"] == 2
    assert document.values["orphaned_member_count"] == 5
    assert "knowledge_repository_survival_computed" in caplog.text
    summary = summarize_repository_survival(
        rows, founder_death_ticks={"body-founder": 5}
    )
    assert summary.orphaned_member_count == 5


def test_access_empty_is_absent() -> None:
    document = compute_knowledge_repository_access(
        (),
        run_id="run-1",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.ABSENT
    assert (
        f"{document.metric_family}@{document.algorithm_version}"
        == KNOWLEDGE_REPOSITORY_ACCESS_METRIC_VERSION
    )


def test_access_success_deny_and_inaccessible() -> None:
    events = (
        {"event_kind": "repository_member_deposited", "repository_id": "r1"},
        {"event_kind": "repository_member_retrieved", "repository_id": "r1"},
        {
            "event_kind": "deposit_denied",
            "reason_code": "repository_access_denied",
        },
        {
            "event_kind": "retrieve_denied",
            "reason_code": "repository_inaccessible",
        },
        {"event_kind": "repository_inaccessible_block", "repository_id": "r1"},
    )
    objectives = (
        {"repository_id": "r1", "access_mode": "open"},
        {"repository_id": "r2", "access_mode": "founder_list"},
        {"repository_id": "r3", "access_mode": "open"},
    )
    document = compute_knowledge_repository_access(
        events,
        run_id="run-1",
        input_revision="rev-1",
        objective_rows=objectives,
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["deposit_success_count"] == 1
    assert document.values["retrieve_success_count"] == 1
    assert document.values["deposit_deny_count"] == 1
    assert document.values["retrieve_deny_count"] == 1
    # retrieve_denied(reason inaccessible) + inaccessible_block kind
    assert document.values["inaccessible_block_count"] == 2
    assert document.values["access_mode_open_count"] == 2
    assert document.values["access_mode_founder_list_count"] == 1
    summary = summarize_repository_access(events, objective_rows=objectives)
    assert summary.deposit_success_count == 1


def test_organization_empty_is_absent() -> None:
    document = compute_knowledge_repository_organization(
        (),
        run_id="run-1",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.ABSENT
    assert (
        f"{document.metric_family}@{document.algorithm_version}"
        == KNOWLEDGE_REPOSITORY_ORGANIZATION_METRIC_VERSION
    )


def test_organization_coverage_dangling_and_neglect_drops() -> None:
    objectives = (
        {
            "repository_id": "r1",
            "member_count": 4,
            "index_entry_count": 2,
            "dangling_index_entry_count": 1,
        },
        {
            "repository_id": "r2",
            "member_count": 0,
            "index_entry_count": 0,
            "dangling_index_entry_count": 0,
        },
    )
    events = (
        {
            "event_kind": "repository_neglected",
            "index_entries_dropped": 2,
        },
        {"event_kind": "repository_indexed", "index_entry_count": 2},
    )
    document = compute_knowledge_repository_organization(
        objectives,
        run_id="run-1",
        input_revision="rev-1",
        event_rows=events,
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["member_count_total"] == 4
    assert document.values["index_entry_count_total"] == 2
    assert document.values["index_coverage_ratio"] == pytest.approx(0.5)
    assert document.values["dangling_index_entry_count"] == 1
    assert document.values["neglect_index_drop_count"] == 2
    assert document.values["history_event_count"] == 2
    summary = summarize_repository_organization(objectives, event_rows=events)
    assert summary.index_coverage_ratio == pytest.approx(0.5)
