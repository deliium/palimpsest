"""Canonical bounded scientific-replication snapshot contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

REPLICATION_SNAPSHOT_VERSION: Final[str] = "scientific-replication-snapshot-v1"
REPLICATION_SNAPSHOT_POLICY_VERSION: Final[str] = "scientific-replication.v1"
REPLICATION_PUBLICATION_PREFIX: Final[str] = "srep-"
REPLICATION_MAX_SNAPSHOT_BYTES: Final[int] = 8_388_608
REPLICATION_MAX_WINDOWS: Final[int] = 512
REPLICATION_MAX_DESIGNS: Final[int] = 4096
REPLICATION_MAX_ATTEMPTS: Final[int] = 4096
REPLICATION_MAX_EXECUTIONS: Final[int] = 4096
REPLICATION_MAX_REPORTS: Final[int] = 8192
REPLICATION_MAX_COMPARISONS: Final[int] = 8192
REPLICATION_MAX_INTERPRETATIONS: Final[int] = 8192
REPLICATION_MAX_COLLABORATIONS: Final[int] = 2048

_SNAPSHOT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "snapshot_version",
        "policy_version",
        "run_id",
        "generated_from_tick",
        "summary",
        "designs",
        "attempts",
        "results",
        "comparisons",
        "interpretations",
        "collaborations",
        "coverage",
        "internal_digest",
        "publication_id",
    }
)
_SUMMARY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "design_count",
        "attempt_count",
        "execution_count",
        "report_count",
        "comparison_count",
        "interpretation_count",
        "collaboration_count",
        "participant_count",
        "first_tick",
        "last_tick",
        "coverage",
        "availability",
        "reason_codes",
    }
)


class ReplicationSnapshotError(ValueError):
    """Safe snapshot codec failure with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or not code:
            raise ValueError("replication_snapshot_invalid_code")
        self.code = code
        super().__init__(code)


def _normalize(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _normalize(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_normalize(item) for item in value)
    return value


def _freeze_rows(
    rows: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    result: list[Mapping[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        result.append(
            _normalize(dict(row))  # type: ignore[arg-type]
        )
    return tuple(result)


@dataclass(frozen=True, slots=True)
class ScientificReplicationSnapshot:
    snapshot_version: str
    policy_version: str
    run_id: str
    generated_from_tick: int
    summary: Mapping[str, object]
    designs: tuple[Mapping[str, object], ...] = ()
    attempts: tuple[Mapping[str, object], ...] = ()
    results: tuple[Mapping[str, object], ...] = ()
    comparisons: tuple[Mapping[str, object], ...] = ()
    interpretations: tuple[Mapping[str, object], ...] = ()
    collaborations: tuple[Mapping[str, object], ...] = ()
    coverage: tuple[Mapping[str, object], ...] = ()
    internal_digest: str = ""
    publication_id: str = ""

    def __post_init__(self) -> None:
        if self.snapshot_version != REPLICATION_SNAPSHOT_VERSION:
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        if self.policy_version != REPLICATION_SNAPSHOT_POLICY_VERSION:
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        if type(self.run_id) is not str or not self.run_id:
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        if (
            isinstance(self.generated_from_tick, bool)
            or type(self.generated_from_tick) is not int
            or self.generated_from_tick < 0
        ):
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        if not isinstance(self.summary, Mapping) or set(self.summary) != _SUMMARY_KEYS:
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        object.__setattr__(self, "summary", _normalize(dict(self.summary)))
        for name, rows, cap in (
            ("designs", self.designs, REPLICATION_MAX_DESIGNS),
            ("attempts", self.attempts, REPLICATION_MAX_ATTEMPTS),
            ("results", self.results, REPLICATION_MAX_REPORTS),
            ("comparisons", self.comparisons, REPLICATION_MAX_COMPARISONS),
            ("interpretations", self.interpretations, REPLICATION_MAX_INTERPRETATIONS),
            ("collaborations", self.collaborations, REPLICATION_MAX_COLLABORATIONS),
            ("coverage", self.coverage, REPLICATION_MAX_WINDOWS),
        ):
            frozen = _freeze_rows(rows)
            if len(frozen) > cap:
                raise ReplicationSnapshotError("replication_snapshot_invalid")
            object.__setattr__(self, name, frozen)
        if self.internal_digest and (
            type(self.internal_digest) is not str or len(self.internal_digest) != 64
        ):
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        if self.publication_id and not self.publication_id.startswith(
            REPLICATION_PUBLICATION_PREFIX
        ):
            raise ReplicationSnapshotError("replication_snapshot_invalid")


SNAPSHOT_KEYS = _SNAPSHOT_KEYS
SUMMARY_KEYS = _SUMMARY_KEYS

__all__ = [
    "REPLICATION_MAX_SNAPSHOT_BYTES",
    "REPLICATION_PUBLICATION_PREFIX",
    "REPLICATION_SNAPSHOT_POLICY_VERSION",
    "REPLICATION_SNAPSHOT_VERSION",
    "SNAPSHOT_KEYS",
    "SUMMARY_KEYS",
    "ReplicationSnapshotError",
    "ScientificReplicationSnapshot",
]
