"""Read-only matrix-aggregate-v1 documents (analysis-only)."""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from experiments.coordinator import ExperimentArmResult
from experiments.matrix_models import GroupRole, MatrixCell

_LOG: Final[logging.Logger] = logging.getLogger("experiments.matrix_aggregate")

MATRIX_AGGREGATE_SCHEMA_VERSION: Final[str] = "matrix-aggregate-v1"


@dataclass(frozen=True, slots=True)
class MatrixCellAggregateRef:
    """Per-cell reference only (run id + payload hash; no observations)."""

    cell_id: str
    condition_id: str
    group_role: GroupRole
    run_id: str
    config_fingerprint: str
    stop_reason: str
    metric_family_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MatrixAggregateDocument:
    """Canonical matrix aggregate grouped by factor levels and group_role."""

    schema_version: str
    matrix_id: str
    matrix_fingerprint: str
    cell_refs: tuple[MatrixCellAggregateRef, ...]
    group_role_counts: tuple[tuple[str, int], ...]
    condition_counts: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        if self.schema_version != MATRIX_AGGREGATE_SCHEMA_VERSION:
            raise ValueError("unsupported matrix aggregate schema_version")


def _canonical_dumps(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def build_matrix_aggregate(
    *,
    matrix_id: str,
    matrix_fingerprint: str,
    cells: Sequence[MatrixCell],
    arm_results: Sequence[ExperimentArmResult],
) -> MatrixAggregateDocument:
    """Build a deterministic aggregate for equal completed result sets."""
    cell_by_condition_seed = {
        (cell.condition_id, cell.seed_ordinal, cell.replicate_index): cell
        for cell in cells
    }
    refs: list[MatrixCellAggregateRef] = []
    for arm in arm_results:
        key = (
            arm.assignment.condition_id,
            arm.assignment.seed_ordinal,
            arm.assignment.replicate_index,
        )
        cell = cell_by_condition_seed.get(key)
        if cell is None:
            continue
        families = tuple(
            sorted(
                {
                    str(getattr(metric, "family", "unknown"))
                    for metric in arm.metrics
                }
            )
        )
        refs.append(
            MatrixCellAggregateRef(
                cell_id=cell.cell_id,
                condition_id=cell.condition_id,
                group_role=cell.group_role,
                run_id=arm.assignment.run_id.value,
                config_fingerprint=arm.config_fingerprint,
                stop_reason=arm.runner_result.stop_reason.value,
                metric_family_codes=families,
            )
        )
    refs.sort(key=lambda item: item.cell_id)
    role_counts = Counter(ref.group_role.value for ref in refs)
    condition_counts = Counter(ref.condition_id for ref in refs)
    document = MatrixAggregateDocument(
        schema_version=MATRIX_AGGREGATE_SCHEMA_VERSION,
        matrix_id=matrix_id,
        matrix_fingerprint=matrix_fingerprint,
        cell_refs=tuple(refs),
        group_role_counts=tuple(sorted(role_counts.items())),
        condition_counts=tuple(sorted(condition_counts.items())),
    )
    _LOG.info(
        "matrix_aggregate_built",
        extra={
            "experiment": {
                "matrix_id": matrix_id,
                "group_role_counts": dict(document.group_role_counts),
                "cell_ref_count": len(refs),
            }
        },
    )
    _LOG.debug(
        "matrix_aggregate_families",
        extra={
            "experiment": {
                "metric_family_lists": [
                    list(ref.metric_family_codes) for ref in refs[:8]
                ]
            }
        },
    )
    return document


def encode_matrix_aggregate(document: MatrixAggregateDocument) -> bytes:
    """Encode aggregate as strict canonical JSON (no metric payloads)."""
    payload = {
        "schema_version": document.schema_version,
        "matrix_id": document.matrix_id,
        "matrix_fingerprint": document.matrix_fingerprint,
        "group_role_counts": [
            {"group_role": role, "count": count}
            for role, count in document.group_role_counts
        ],
        "condition_counts": [
            {"condition_id": condition_id, "count": count}
            for condition_id, count in document.condition_counts
        ],
        "cell_refs": [
            {
                "cell_id": ref.cell_id,
                "condition_id": ref.condition_id,
                "group_role": ref.group_role.value,
                "run_id": ref.run_id,
                "config_fingerprint": ref.config_fingerprint,
                "stop_reason": ref.stop_reason,
                "metric_family_codes": list(ref.metric_family_codes),
            }
            for ref in document.cell_refs
        ],
    }
    return _canonical_dumps(payload)


def matrix_aggregate_fingerprint(document: MatrixAggregateDocument) -> str:
    return hashlib.sha256(encode_matrix_aggregate(document)).hexdigest()


__all__ = [
    "MATRIX_AGGREGATE_SCHEMA_VERSION",
    "MatrixAggregateDocument",
    "MatrixCellAggregateRef",
    "build_matrix_aggregate",
    "encode_matrix_aggregate",
    "matrix_aggregate_fingerprint",
]
