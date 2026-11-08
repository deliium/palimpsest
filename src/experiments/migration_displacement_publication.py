"""Compose and publish ``migration-displacement-snapshot-v1``."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from experiments.migration_displacement_harvest import (
    MigrationDisplacementHarvest,
    build_completed_run_migration_displacement_harvest,
    compose_migration_displacement_snapshot,
)
from simulation.migration_displacement_codec import (
    encode_migration_displacement_snapshot,
)
from simulation.migration_displacement_models import MigrationDisplacementSnapshot
from simulation.migration_displacement_ports import MigrationDisplacementPublisherPort

__all__ = [
    "INCOMPLETE_MIGRATION_DISPLACEMENT_STOP_CODES",
    "MigrationDisplacementHarvestResult",
    "MigrationDisplacementReceipt",
    "build_migration_displacement_harvest_result",
    "migration_displacement_publication_document",
    "publish_migration_displacement_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.migration_displacement.publication"
)

INCOMPLETE_MIGRATION_DISPLACEMENT_STOP_CODES: Final[frozenset[str]] = frozenset(
    {
        "cancelled",
        "cognition_failure",
        "authority_failure",
        "finalization_recovery_required",
        "experiment_criterion_failure",
        "historical_artifact_failure",
    }
)

_RECEIPT_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "disabled",
        "unavailable",
        "failed",
        "size_limit",
        "publication_exists",
        "quota_exceeded",
        "published",
    }
)


@dataclass(frozen=True, slots=True)
class MigrationDisplacementReceipt:
    status: str
    reason: str | None = None
    publication_id: str | None = None
    digest: str | None = None
    row_count: int = 0
    byte_count: int = 0
    coverage: str = "missing"
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status not in _RECEIPT_STATUSES:
            raise ValueError("migration_displacement_receipt_status")


@dataclass(frozen=True, slots=True)
class MigrationDisplacementHarvestResult:
    receipt: MigrationDisplacementReceipt
    snapshot: MigrationDisplacementSnapshot | None = None


def _stop_reason(runner_result: object) -> str:
    value = getattr(runner_result, "stop_reason", None)
    return getattr(value, "value", str(value or ""))


def _row_count(snapshot: MigrationDisplacementSnapshot) -> int:
    return (
        len(snapshot.candidates)
        + len(snapshot.movements)
        + len(snapshot.causes)
        + len(snapshot.routes)
        + len(snapshot.clusters)
        + len(snapshot.waves)
        + len(snapshot.outcomes)
        + len(snapshot.lineage)
        + len(snapshot.alignment)
        + len(snapshot.metric_provenance)
    )


def _snapshot(
    harvest: MigrationDisplacementHarvest, run_id: str
) -> MigrationDisplacementSnapshot:
    if harvest.snapshot.summary.run_id == run_id:
        return harvest.snapshot
    return compose_migration_displacement_snapshot(harvest.rows, run_id)


def _receipt_from_snapshot(
    snapshot: MigrationDisplacementSnapshot,
    *,
    status: str,
    reason: str | None,
    notices: tuple[str, ...] = (),
) -> MigrationDisplacementReceipt:
    payload = encode_migration_displacement_snapshot(snapshot)
    return MigrationDisplacementReceipt(
        status=status,
        reason=reason,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        row_count=_row_count(snapshot),
        byte_count=len(payload),
        coverage=snapshot.summary.coverage,
        notices=notices,
    )


def build_migration_displacement_harvest_result(
    runner_result: object,
    *,
    committed_events: Sequence[object],
    run_id: str,
    input_revision: str = "rev-run",
    entity_to_agent: object | None = None,
    regions_spec: object | None = None,
    window_end: int | None = None,
    complete_through_boundary: int | None = None,
) -> MigrationDisplacementHarvestResult:
    stop = _stop_reason(runner_result)
    if stop in INCOMPLETE_MIGRATION_DISPLACEMENT_STOP_CODES:
        return MigrationDisplacementHarvestResult(
            receipt=MigrationDisplacementReceipt(
                status="unavailable", reason=stop, coverage="not_applicable"
            )
        )
    try:
        harvest = build_completed_run_migration_displacement_harvest(
            runner_result,
            committed_events=committed_events,
            run_id=run_id,
            input_revision=input_revision,
            entity_to_agent=entity_to_agent,  # type: ignore[arg-type]
            regions_spec=regions_spec,
            window_end=window_end,
            complete_through_boundary=complete_through_boundary,
        )
        snapshot = _snapshot(harvest, run_id)
    except ValueError as exc:
        code = str(exc)
        if code == "migration_displacement_size_limit" or "size_limit" in code:
            return MigrationDisplacementHarvestResult(
                receipt=MigrationDisplacementReceipt(
                    status="size_limit",
                    reason="migration_displacement_size_limit",
                )
            )
        _LOG.warning(
            "migration_displacement_publication status=%s rows=%s bytes=%s coverage=%s",
            "failed",
            0,
            0,
            "missing",
        )
        return MigrationDisplacementHarvestResult(
            receipt=MigrationDisplacementReceipt(
                status="failed",
                reason="migration_displacement_harvest_failed",
            )
        )
    except Exception:
        _LOG.warning(
            "migration_displacement_publication status=%s rows=%s bytes=%s coverage=%s",
            "failed",
            0,
            0,
            "missing",
        )
        return MigrationDisplacementHarvestResult(
            receipt=MigrationDisplacementReceipt(
                status="failed",
                reason="migration_displacement_harvest_failed",
            )
        )
    receipt = _receipt_from_snapshot(
        snapshot,
        status="published",
        reason="published",
        notices=harvest.notices,
    )
    _LOG.info(
        "migration_displacement_publication status=%s rows=%s bytes=%s coverage=%s",
        receipt.status,
        receipt.row_count,
        receipt.byte_count,
        receipt.coverage,
    )
    return MigrationDisplacementHarvestResult(receipt=receipt, snapshot=snapshot)


def publish_migration_displacement_snapshot(
    runner_result: object,
    publisher: MigrationDisplacementPublisherPort | None,
    *,
    committed_events: Sequence[object],
    run_id: str,
    input_revision: str = "rev-run",
    entity_to_agent: object | None = None,
    regions_spec: object | None = None,
    window_end: int | None = None,
    complete_through_boundary: int | None = None,
) -> MigrationDisplacementReceipt:
    """Publish when explicitly configured; never raise into the scientific path."""
    if publisher is None:
        return MigrationDisplacementReceipt(
            status="disabled", reason="root_unset", coverage="not_applicable"
        )
    result = build_migration_displacement_harvest_result(
        runner_result,
        committed_events=committed_events,
        run_id=run_id,
        input_revision=input_revision,
        entity_to_agent=entity_to_agent,
        regions_spec=regions_spec,
        window_end=window_end,
        complete_through_boundary=complete_through_boundary,
    )
    if result.snapshot is None:
        return result.receipt
    if result.receipt.status in {"unavailable", "failed", "size_limit"}:
        return result.receipt
    if not isinstance(publisher, MigrationDisplacementPublisherPort):
        return MigrationDisplacementReceipt(
            status="failed",
            reason="migration_displacement_harvest_failed",
            coverage=result.receipt.coverage,
            notices=result.receipt.notices,
        )
    try:
        publisher.publish(result.snapshot)
    except ValueError as exc:
        code = str(exc)
        if code == "migration_displacement_publication_exists":
            return MigrationDisplacementReceipt(
                status="publication_exists",
                reason="migration_displacement_publication_exists",
                publication_id=result.receipt.publication_id,
                digest=result.receipt.digest,
                row_count=result.receipt.row_count,
                byte_count=result.receipt.byte_count,
                coverage=result.receipt.coverage,
                notices=result.receipt.notices,
            )
        if code == "migration_displacement_quota_exceeded":
            return MigrationDisplacementReceipt(
                status="quota_exceeded",
                reason="migration_displacement_quota_exceeded",
                publication_id=result.receipt.publication_id,
                digest=result.receipt.digest,
                row_count=result.receipt.row_count,
                byte_count=result.receipt.byte_count,
                coverage=result.receipt.coverage,
                notices=result.receipt.notices,
            )
        if code == "migration_displacement_size_limit":
            return MigrationDisplacementReceipt(
                status="size_limit",
                reason="migration_displacement_size_limit",
                coverage=result.receipt.coverage,
                notices=result.receipt.notices,
            )
        _LOG.warning(
            "migration_displacement_publication status=%s rows=%s bytes=%s coverage=%s",
            "failed",
            result.receipt.row_count,
            result.receipt.byte_count,
            result.receipt.coverage,
        )
        return MigrationDisplacementReceipt(
            status="failed",
            reason="migration_displacement_harvest_failed",
            publication_id=result.receipt.publication_id,
            digest=result.receipt.digest,
            row_count=result.receipt.row_count,
            byte_count=result.receipt.byte_count,
            coverage=result.receipt.coverage,
            notices=result.receipt.notices,
        )
    except Exception:
        _LOG.warning(
            "migration_displacement_publication status=%s rows=%s bytes=%s coverage=%s",
            "failed",
            result.receipt.row_count,
            result.receipt.byte_count,
            result.receipt.coverage,
        )
        return MigrationDisplacementReceipt(
            status="failed",
            reason="migration_displacement_harvest_failed",
            publication_id=result.receipt.publication_id,
            digest=result.receipt.digest,
            row_count=result.receipt.row_count,
            byte_count=result.receipt.byte_count,
            coverage=result.receipt.coverage,
            notices=result.receipt.notices,
        )
    return result.receipt


def migration_displacement_publication_document(
    receipt: MigrationDisplacementReceipt,
) -> dict[str, object]:
    return {
        "status": receipt.status,
        "reason": receipt.reason,
        "publication_id": receipt.publication_id,
        "digest": receipt.digest,
        "row_count": receipt.row_count,
        "byte_count": receipt.byte_count,
        "coverage": receipt.coverage,
        "notices": list(receipt.notices),
    }
