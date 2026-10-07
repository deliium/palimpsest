"""Knowledge-repository harvest composition + collector opt-in wiring."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from experiments.composition import (
    knowledge_repository_harvest_from_run,
    repository_event_rows_from_events,
    repository_event_rows_from_resolutions,
    repository_objective_rows_from_repositories,
)
from experiments.metric_collection import inputs_with_opt_in_metric_rows
from simulation.runner_models import example_knowledge_repositories_spec
from world.events import RepositoryEstablished, RepositoryMemberDeposited, RepositoryNeglected
from world.identifiers import EntityId
from world.repositories import (
    KnowledgeRepository,
    RepositoryAccessMode,
    RepositoryIndexEntry,
    RepositoryStatus,
)

pytestmark = pytest.mark.unit


def test_objective_rows_include_dangling_index() -> None:
    repository = KnowledgeRepository(
        repository_id=EntityId("repo-1"),
        location_id=EntityId("loc-1"),
        founder_ids=(EntityId("body-1"),),
        established_tick=2,
        access_mode=RepositoryAccessMode.OPEN,
        status=RepositoryStatus.INTACT,
        member_artifact_ids=(EntityId("art-1"),),
        index_entries=(
            RepositoryIndexEntry(
                entry_id="e1",
                artifact_id=EntityId("art-1"),
                label_tokens=("a",),
                revision=0,
            ),
            RepositoryIndexEntry(
                entry_id="e2",
                artifact_id=EntityId("missing"),
                label_tokens=("b",),
                revision=1,
            ),
        ),
        last_maintained_tick=2,
        neglect_streak=0,
    )
    rows = repository_objective_rows_from_repositories((repository,))
    assert len(rows) == 1
    row = rows[0]
    assert row["repository_id"] == "repo-1"
    assert row["member_count"] == 1
    assert row["index_entry_count"] == 2
    assert row["dangling_index_entry_count"] == 1
    assert row["founder_ids"] == ("body-1",)
    assert "library" not in row
    assert "archive" not in row


def test_event_rows_from_repository_details() -> None:
    events = (
        SimpleNamespace(
            tick=1,
            details=RepositoryEstablished(
                repository_id=EntityId("repo-1"),
                location_id=EntityId("loc-1"),
                structure_id=None,
                founder_ids=(EntityId("body-1"),),
                access_mode="open",
                established_tick=1,
            ),
        ),
        SimpleNamespace(
            tick=2,
            details=RepositoryMemberDeposited(
                repository_id=EntityId("repo-1"),
                artifact_id=EntityId("art-1"),
                member_count=1,
                actor_id=EntityId("body-1"),
            ),
        ),
        SimpleNamespace(
            tick=3,
            details=RepositoryNeglected(
                repository_id=EntityId("repo-1"),
                neglect_streak=1,
                prior_status="intact",
                next_status="neglected",
                index_entries_dropped=1,
            ),
        ),
        SimpleNamespace(tick=4, details=SimpleNamespace(kind="wait")),
    )
    rows = repository_event_rows_from_events(events)
    assert len(rows) == 3
    assert rows[0]["event_kind"] == "repository_established"
    assert rows[1]["event_kind"] == "repository_member_deposited"
    assert rows[1]["artifact_id"] == "art-1"
    assert rows[2]["event_kind"] == "repository_neglected"
    assert rows[2]["index_entries_dropped"] == 1


def test_resolution_deny_rows() -> None:
    resolutions = (
        SimpleNamespace(
            command_kind="deposit_record",
            status="rejected",
            tick=4,
            agent_id="agent-1",
            reason_code="repository_inaccessible",
            command=SimpleNamespace(
                repository_id=EntityId("repo-1"),
                artifact_id=EntityId("art-1"),
            ),
        ),
        SimpleNamespace(
            command_kind="retrieve_record",
            status="applied",
            tick=5,
        ),
    )
    rows = repository_event_rows_from_resolutions(resolutions)
    assert len(rows) == 1
    assert rows[0]["event_kind"] == "deposit_denied"
    assert rows[0]["reason_code"] == "repository_inaccessible"


def test_harvest_skips_when_repository_absent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="experiments.composition"):
        payload = knowledge_repository_harvest_from_run(
            knowledge_repositories_spec=None
        )
    assert payload is None
    assert "repository_absent" in caplog.text


def test_harvest_attaches_rows_when_repository_enabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repository = KnowledgeRepository(
        repository_id=EntityId("repo-1"),
        location_id=EntityId("loc-1"),
        founder_ids=(EntityId("body-1"),),
        established_tick=0,
        access_mode=RepositoryAccessMode.OPEN,
        member_artifact_ids=(EntityId("art-1"),),
    )
    events = (
        SimpleNamespace(
            tick=1,
            details=RepositoryMemberDeposited(
                repository_id=EntityId("repo-1"),
                artifact_id=EntityId("art-1"),
                member_count=1,
                actor_id=EntityId("body-1"),
            ),
        ),
    )
    with caplog.at_level(logging.DEBUG, logger="experiments.composition"):
        payload = knowledge_repository_harvest_from_run(
            knowledge_repositories_spec=example_knowledge_repositories_spec(),
            repositories=(repository,),
            events=events,
        )
    assert payload is not None
    assert len(payload["repository_objective_rows"]) == 1
    assert len(payload["repository_event_rows"]) == 1
    assert "knowledge_repository_harvest_built" in caplog.text


def test_opt_in_and_assemble_attach_repository_families() -> None:
    base = MetricComputationInputs(
        run_id="run-1",
        input_revision="rev-1",
        window_end=1,
    )
    updated = inputs_with_opt_in_metric_rows(
        base,
        repository_objective_rows=(
            {
                "repository_id": "r1",
                "status": "intact",
                "access_mode": "open",
                "founder_ids": ("body-1",),
                "established_tick": 0,
                "member_count": 1,
                "index_entry_count": 0,
                "dangling_index_entry_count": 0,
            },
        ),
        repository_event_rows=(
            {"event_kind": "repository_member_deposited", "repository_id": "r1"},
        ),
        founder_death_ticks={"body-1": 3},
    )
    assert updated.repository_objective_rows is not None
    bundle = assemble_metric_documents(updated)
    families = {doc.metric_family for doc in bundle.documents}
    assert "knowledge_repository_survival" in families
    assert "knowledge_repository_access" in families
    assert "knowledge_repository_organization" in families
