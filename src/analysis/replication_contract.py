"""Closed detached replication analysis policy and row identity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Final

from analysis.replication_rows import (
    ReplicationAttemptRow,
    ReplicationCollaborationRow,
    ReplicationComparisonRow,
    ReplicationCoverageRow,
    ReplicationDesignRow,
    ReplicationInterpretationRow,
    ReplicationObjectiveRow,
    ReplicationOwnerReportRow,
)

REPLICATION_POLICY_VERSION: Final[str] = "scientific-replication.v1"
REPLICATION_WINDOW_TICKS: Final[int] = 32
REPLICATION_MAX_WINDOWS: Final[int] = 512
REPLICATION_MINIMUM_SAMPLES: Final[int] = 3
REPLICATION_MAX_PARTICIPANTS: Final[int] = 64
REPLICATION_MAX_ROWS: Final[int] = 8192
REPLICATION_MAX_DESIGN_ROWS: Final[int] = 4096
REPLICATION_MAX_COLLABORATION_ROWS: Final[int] = 2048

REPLICATION_NOTICE_CODES: Final[frozenset[str]] = frozenset(
    {
        "cap_designs",
        "cap_attempts",
        "cap_executions",
        "cap_reports",
        "cap_interpretations",
        "cap_comparisons",
        "cap_collaborations",
        "source_missing",
        "result_missing",
        "condition_unknown",
        "condition_different",
        "execution_ambiguous",
        "report_execution_mismatch",
        "retention_cap",
        "partial_owner_export",
        "duplicate_source",
    }
)

FORBIDDEN_REPLICATION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "truth",
        "proven",
        "verified",
        "consensus",
        "majority",
        "p_value",
        "confidence_interval",
        "scientific_score",
        "reliability_score",
    }
)


class ReplicationAnalysisError(ValueError):
    """Safe detached-analysis failure."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or not code:
            raise ValueError("replication_analysis_invalid_code")
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReplicationAnalysis:
    policy_version: str
    designs: tuple[ReplicationDesignRow, ...] = ()
    attempts: tuple[ReplicationAttemptRow, ...] = ()
    executions: tuple[ReplicationObjectiveRow, ...] = ()
    reports: tuple[ReplicationOwnerReportRow, ...] = ()
    comparisons: tuple[ReplicationComparisonRow, ...] = ()
    interpretations: tuple[ReplicationInterpretationRow, ...] = ()
    collaborations: tuple[ReplicationCollaborationRow, ...] = ()
    coverage: tuple[ReplicationCoverageRow, ...] = ()
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.policy_version != REPLICATION_POLICY_VERSION:
            raise ReplicationAnalysisError("replication_analysis_policy_mismatch")
        for name in (
            "designs",
            "attempts",
            "executions",
            "reports",
            "comparisons",
            "interpretations",
            "collaborations",
            "coverage",
            "notices",
        ):
            if not isinstance(getattr(self, name), tuple):
                raise ReplicationAnalysisError("replication_analysis_invalid_rows")
        for notice in self.notices:
            if notice not in REPLICATION_NOTICE_CODES:
                raise ReplicationAnalysisError("replication_analysis_invalid_notice")


def _default(value: object) -> object:
    import dataclasses

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    raise TypeError("replication_row_not_serializable")


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_default,
    )


def replication_row_token(record_type: str, payload: object) -> str:
    """Full-content row identity excluding ``row_token`` itself."""

    if record_type not in {
        "design",
        "attempt",
        "execution",
        "report",
        "comparison",
        "interpretation",
        "collaboration",
        "coverage",
    }:
        raise ReplicationAnalysisError("replication_analysis_invalid_record_type")
    material = _canonical(
        {
            "policy_version": REPLICATION_POLICY_VERSION,
            "record_type": record_type,
            "payload": payload,
        }
    ).encode("ascii")
    return "rprow-" + hashlib.sha256(material).hexdigest()[:32]


def window_index(tick: int) -> int:
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise ReplicationAnalysisError("replication_analysis_invalid_tick")
    return tick // REPLICATION_WINDOW_TICKS


__all__ = [
    "FORBIDDEN_REPLICATION_KEYS",
    "REPLICATION_MAX_COLLABORATION_ROWS",
    "REPLICATION_MAX_DESIGN_ROWS",
    "REPLICATION_MAX_PARTICIPANTS",
    "REPLICATION_MAX_ROWS",
    "REPLICATION_MAX_WINDOWS",
    "REPLICATION_MINIMUM_SAMPLES",
    "REPLICATION_NOTICE_CODES",
    "REPLICATION_POLICY_VERSION",
    "REPLICATION_WINDOW_TICKS",
    "ReplicationAnalysis",
    "ReplicationAnalysisError",
    "replication_row_token",
    "window_index",
]
