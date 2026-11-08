# mypy: ignore-errors
"""Completed-run migration-displacement harvest and publication receipts."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from experiments.migration_displacement_harvest import (
    build_completed_run_migration_displacement_harvest,
)
from experiments.migration_displacement_publication import (
    build_migration_displacement_harvest_result,
    migration_displacement_publication_document,
    publish_migration_displacement_snapshot,
)
from simulation.migration_displacement_codec import (
    finalize_migration_displacement_snapshot,
)
from simulation.migration_displacement_models import (
    empty_migration_displacement_snapshot,
)
from tests.unit.migration_displacement_analysis_helpers import move
from tests.unit.migration_displacement_helpers import (
    OWNER,
    OWNER_ENTITY,
    PEER,
    PEER_ENTITY,
    cause,
    cluster,
    integration,
    ledger,
    route,
    wave,
)


def _runner(*, ledgers=(), stop: str = "max_ticks"):
    return SimpleNamespace(
        stop_reason=SimpleNamespace(value=stop),
        migration_displacement_ledgers=tuple(ledgers),
        status="completed",
    )


def _rich_ledger():
    c = cause()
    return ledger(
        causes=(c,),
        routes=(route(),),
        clusters=(cluster(),),
        integrations=(integration(),),
        waves=(wave(causes=(c,)),),
    )


def _events():
    return (
        move(1, OWNER_ENTITY.value, "loc-a", "loc-b"),
        move(2, PEER_ENTITY.value, "loc-a", "loc-b"),
    )


def test_completed_run_builds_all_four_layers() -> None:
    harvest = build_completed_run_migration_displacement_harvest(
        _runner(ledgers=(_rich_ledger(),)),
        committed_events=_events(),
        run_id="run-1",
        input_revision="rev-1",
        entity_to_agent={
            OWNER_ENTITY.value: OWNER.value,
            PEER_ENTITY.value: PEER.value,
        },
    )
    assert harvest.coverage in {"complete", "partial"}
    assert harvest.rows.movements
    assert harvest.rows.causes
    assert harvest.rows.routes
    assert harvest.rows.clusters or harvest.rows.waves or harvest.rows.outcomes
    assert harvest.snapshot.publication_id.startswith("md-pub-")
    assert {row.family for row in harvest.snapshot.metric_provenance} == {
        "migration_wave_structure",
        "migration_cause_evidence",
        "migration_cluster_cohesion",
        "migration_integration_outcome",
    }


def test_incomplete_run_is_unavailable() -> None:
    result = build_migration_displacement_harvest_result(
        _runner(ledgers=(_rich_ledger(),), stop="cancelled"),
        committed_events=_events(),
        run_id="run-1",
    )
    assert result.receipt.status == "unavailable"
    assert result.receipt.reason == "cancelled"
    assert result.snapshot is None


def test_missing_ledgers_is_missing_coverage() -> None:
    harvest = build_completed_run_migration_displacement_harvest(
        _runner(),
        committed_events=(),
        run_id="run-1",
    )
    assert harvest.coverage == "missing"
    assert harvest.rows.coverage == "missing"
    assert harvest.snapshot.summary.coverage == "missing"


def test_snapshot_carries_summary_and_candidates() -> None:
    harvest = build_completed_run_migration_displacement_harvest(
        _runner(ledgers=(_rich_ledger(),)),
        committed_events=_events(),
        run_id="run-1",
        input_revision="rev-1",
        entity_to_agent={
            OWNER_ENTITY.value: OWNER.value,
            PEER_ENTITY.value: PEER.value,
        },
    )
    summary = harvest.snapshot.summary
    assert summary.candidate_count == len(harvest.snapshot.candidates)
    assert summary.wave_count == len(harvest.snapshot.waves)
    assert summary.movement_count == len(harvest.snapshot.movements)
    assert summary.cause_count == len(harvest.snapshot.causes)
    assert summary.displacement_like_count + summary.mixed_count + (
        summary.not_displacement_like_count + summary.unknown_count
    ) == summary.wave_count
    assert summary.integration_settled_count + summary.integration_transient_count + (
        summary.integration_returned_count
        + summary.integration_onward_count
        + summary.integration_unknown_count
    ) == summary.outcome_count
    for candidate in harvest.snapshot.candidates:
        assert candidate.candidate_token.startswith("mig-")


def test_publication_receipt_statuses() -> None:
    disabled = publish_migration_displacement_snapshot(
        _runner(ledgers=(_rich_ledger(),)),
        None,
        committed_events=_events(),
        run_id="run-1",
    )
    assert disabled.status == "disabled"
    assert disabled.reason == "root_unset"

    ready = build_migration_displacement_harvest_result(
        _runner(ledgers=(_rich_ledger(),)),
        committed_events=_events(),
        run_id="run-1",
        input_revision="rev-1",
        entity_to_agent={
            OWNER_ENTITY.value: OWNER.value,
            PEER_ENTITY.value: PEER.value,
        },
    )
    assert ready.receipt.status == "published"
    assert ready.snapshot is not None
    document = migration_displacement_publication_document(ready.receipt)
    assert document["status"] == "published"
    assert document["publication_id"] == ready.receipt.publication_id
    assert set(document) <= {
        "status",
        "reason",
        "publication_id",
        "digest",
        "row_count",
        "byte_count",
        "coverage",
        "notices",
    }


def test_size_limit_and_duplicate_and_quota_receipts() -> None:
    class _Publisher:
        def __init__(self, code: str) -> None:
            self._code = code

        def publish(self, snapshot) -> None:
            raise ValueError(self._code)

        def read_summary(self, run_id: str):
            return None

        def read_snapshot(self, run_id: str):
            return None

    duplicate = publish_migration_displacement_snapshot(
        _runner(ledgers=(_rich_ledger(),)),
        _Publisher("migration_displacement_publication_exists"),
        committed_events=_events(),
        run_id="run-1",
        input_revision="rev-1",
        entity_to_agent={
            OWNER_ENTITY.value: OWNER.value,
            PEER_ENTITY.value: PEER.value,
        },
    )
    assert duplicate.status == "publication_exists"
    quota = publish_migration_displacement_snapshot(
        _runner(ledgers=(_rich_ledger(),)),
        _Publisher("migration_displacement_quota_exceeded"),
        committed_events=_events(),
        run_id="run-1",
        input_revision="rev-1",
        entity_to_agent={
            OWNER_ENTITY.value: OWNER.value,
            PEER_ENTITY.value: PEER.value,
        },
    )
    assert quota.status == "quota_exceeded"
    size = publish_migration_displacement_snapshot(
        _runner(ledgers=(_rich_ledger(),)),
        _Publisher("migration_displacement_size_limit"),
        committed_events=_events(),
        run_id="run-1",
        input_revision="rev-1",
        entity_to_agent={
            OWNER_ENTITY.value: OWNER.value,
            PEER_ENTITY.value: PEER.value,
        },
    )
    assert size.status == "size_limit"


def test_publication_failure_does_not_change_scientific_status() -> None:
    class _Boom:
        def publish(self, snapshot) -> None:
            raise RuntimeError("storage")

        def read_summary(self, run_id: str):
            return None

        def read_snapshot(self, run_id: str):
            return None

    runner = _runner(ledgers=(_rich_ledger(),))
    before = (
        runner.stop_reason.value,
        runner.migration_displacement_ledgers,
        runner.status,
    )
    receipt = publish_migration_displacement_snapshot(
        runner,
        _Boom(),
        committed_events=_events(),
        run_id="run-1",
        input_revision="rev-1",
        entity_to_agent={
            OWNER_ENTITY.value: OWNER.value,
            PEER_ENTITY.value: PEER.value,
        },
    )
    assert receipt.status == "failed"
    assert (
        runner.stop_reason.value,
        runner.migration_displacement_ledgers,
        runner.status,
    ) == before


def test_harvest_does_not_import_cognition_api_or_persistence() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "experiments"
    for name in (
        "migration_displacement_harvest.py",
        "migration_displacement_publication.py",
    ):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        forbidden = {
            "agents.cognition",
            "api",
            "persistence",
            "observer",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not any(
                        alias.name == item or alias.name.startswith(item + ".")
                        for item in forbidden
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not any(
                    node.module == item or node.module.startswith(item + ".")
                    for item in forbidden
                )


def test_empty_snapshot_helper_round_trips() -> None:
    snapshot = finalize_migration_displacement_snapshot(
        empty_migration_displacement_snapshot(
            "run-1", digest="", publication_id=""
        )
    )
    assert snapshot.publication_id.startswith("md-pub-")
    assert len(snapshot.digest) == 64
