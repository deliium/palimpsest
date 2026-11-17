"""Trusted composition from detached analysis into replication snapshots."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Final, cast

from analysis.replication_contract import ReplicationAnalysis
from simulation.replication_codec import (
    finalize_replication_snapshot,
    replication_snapshot_row_token,
)
from simulation.replication_models import (
    REPLICATION_SNAPSHOT_POLICY_VERSION,
    REPLICATION_SNAPSHOT_VERSION,
    ScientificReplicationSnapshot,
)
from simulation.replication_ports import ReplicationPublicationError

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.replication_publication"
)

_HARVEST_STATUSES: Final[frozenset[str]] = frozenset(
    {"published", "disabled", "missing", "quota_exceeded", "corrupt"}
)


@dataclass(frozen=True, slots=True)
class ReplicationHarvestResult:
    """Safe publication receipt; scientific completion is tracked separately."""

    status: str
    publication_id: str | None
    stored: bool
    byte_size: int
    scientific_status: str
    reason: str = ""

    def __post_init__(self) -> None:
        if self.status not in _HARVEST_STATUSES:
            raise ValueError("replication_harvest_invalid_status")
        if self.publication_id is not None and (
            type(self.publication_id) is not str or not self.publication_id
        ):
            raise ValueError("replication_harvest_invalid_publication")
        if type(self.stored) is not bool:
            raise TypeError("stored must be bool")
        if isinstance(self.byte_size, bool) or type(self.byte_size) is not int:
            raise TypeError("byte_size must be int")
        if self.byte_size < 0:
            raise ValueError("byte_size must be non-negative")
        if type(self.scientific_status) is not str or not self.scientific_status:
            raise ValueError("replication_harvest_invalid_scientific_status")


def build_replication_harvest_result(
    *,
    snapshot: object | None,
    publisher: object | None,
    scientific_status: str = "complete",
) -> ReplicationHarvestResult:
    """Map one opt-in publication attempt onto a safe closed status."""
    if snapshot is None:
        return ReplicationHarvestResult(
            status="missing",
            publication_id=None,
            stored=False,
            byte_size=0,
            scientific_status=scientific_status,
            reason="missing",
        )
    if publisher is None:
        return ReplicationHarvestResult(
            status="disabled",
            publication_id=None,
            stored=False,
            byte_size=0,
            scientific_status=scientific_status,
            reason="disabled",
        )
    try:
        receipt = publisher.publish(snapshot)  # type: ignore[attr-defined]
    except ReplicationPublicationError as exc:
        code = str(exc.code)
        _LOG.warning(
            "replication_publication_failed status=corrupt reason=%s", code
        )
        return ReplicationHarvestResult(
            status="corrupt",
            publication_id=None,
            stored=False,
            byte_size=0,
            scientific_status=scientific_status,
            reason=code,
        )
    except Exception:
        _LOG.warning("replication_publication_failed status=corrupt reason=unknown")
        return ReplicationHarvestResult(
            status="corrupt",
            publication_id=None,
            stored=False,
            byte_size=0,
            scientific_status=scientific_status,
            reason="unknown",
        )
    reason = str(getattr(receipt, "reason", ""))
    stored = bool(getattr(receipt, "stored", False))
    if stored or reason == "published":
        status = "published"
    elif reason in {"disabled", "quota_exceeded"}:
        status = reason
    else:
        status = "corrupt"
    _LOG.info(
        "replication_publication_status status=%s bytes=%s",
        status,
        getattr(receipt, "byte_size", 0),
    )
    return ReplicationHarvestResult(
        status=status,
        publication_id=getattr(receipt, "publication_id", None),
        stored=stored,
        byte_size=int(getattr(receipt, "byte_size", 0)),
        scientific_status=scientific_status,
        reason=reason,
    )


def publish_replication_snapshot(
    snapshot: object | None,
    *,
    publisher: object | None,
    scientific_status: str = "complete",
) -> ReplicationHarvestResult:
    """Publish exactly one snapshot through an explicit opt-in port."""
    if snapshot is not None and type(snapshot) is not ScientificReplicationSnapshot:
        raise TypeError("snapshot must be ScientificReplicationSnapshot")
    return build_replication_harvest_result(
        snapshot=snapshot,
        publisher=publisher,
        scientific_status=scientific_status,
    )



def _row_dict(row: object, record_type: str) -> dict[str, object]:
    if is_dataclass(row):
        payload = asdict(cast(Any, row))
    elif isinstance(row, dict):
        payload = dict(row)
    else:
        raise TypeError("replication_publication_invalid_row")
    payload.pop("row_token", None)
    payload["record_type"] = record_type
    token = replication_snapshot_row_token(record_type, payload)
    payload["row_token"] = token
    return payload


def compose_replication_snapshot(
    analysis: object,
    *,
    run_id: str,
    generated_from_tick: int,
) -> ScientificReplicationSnapshot:
    if type(analysis) is not ReplicationAnalysis:
        raise TypeError("analysis must be ReplicationAnalysis")
    data = cast(Any, analysis)
    designs = [_row_dict(row, "design") for row in data.designs]
    attempts = [_row_dict(row, "attempt") for row in data.attempts]
    results = [
        _row_dict(row, "execution") for row in data.executions
    ] + [_row_dict(row, "report") for row in data.reports]
    comparisons = [_row_dict(row, "comparison") for row in data.comparisons]
    interpretations = [
        _row_dict(row, "interpretation") for row in data.interpretations
    ]
    collaborations = [
        _row_dict(row, "collaboration") for row in data.collaborations
    ]
    coverage_rows = data.coverage[-1] if data.coverage else None
    coverage = [_row_dict(row, "coverage") for row in data.coverage]
    windows = [
        row.window_index
        for row in (
            *analysis.designs,
            *data.executions,
            *data.reports,
        )
    ]
    participants = {
        row.fact.participant_token
        for row in (*data.attempts, *data.reports)
        if row.fact.participant_token is not None
    }
    summary = {
        "design_count": len(analysis.designs),
        "attempt_count": len(data.attempts),
        "execution_count": len(data.executions),
        "report_count": len(data.reports),
        "comparison_count": len(data.comparisons),
        "interpretation_count": len(data.interpretations),
        "collaboration_count": len(data.collaborations),
        "participant_count": len(participants),
        "first_tick": None if not windows else min(windows) * 32,
        "last_tick": None if not windows else max(windows) * 32 + 31,
        "coverage": "missing" if coverage_rows is None else coverage_rows.coverage,
        "availability": (
            "unavailable"
            if coverage_rows is None
            else coverage_rows.availability
        ),
        "reason_codes": () if coverage_rows is None else coverage_rows.reason_codes,
    }
    snapshot = ScientificReplicationSnapshot(
        snapshot_version=REPLICATION_SNAPSHOT_VERSION,
        policy_version=REPLICATION_SNAPSHOT_POLICY_VERSION,
        run_id=run_id,
        generated_from_tick=generated_from_tick,
        summary=summary,
        designs=tuple(designs),
        attempts=tuple(attempts),
        results=tuple(results),
        comparisons=tuple(comparisons),
        interpretations=tuple(interpretations),
        collaborations=tuple(collaborations),
        coverage=tuple(coverage),
    )
    _LOG.info(
        "replication_snapshot_composed designs=%s attempts=%s results=%s",
        len(designs),
        len(attempts),
        len(results),
    )
    return finalize_replication_snapshot(snapshot)


__all__ = [
    "ReplicationHarvestResult",
    "build_replication_harvest_result",
    "compose_replication_snapshot",
    "publish_replication_snapshot",
]
