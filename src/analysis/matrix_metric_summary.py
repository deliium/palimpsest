"""Pure multi-seed metric distribution summary builder.

``matrix-metric-summary-v1`` — sibling to ref-only ``matrix-aggregate-v1``.
Consumes already-quantized MetricDocument values; does not invent zeros from
missing sidecars.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.distribution_summary import summarize_distribution
from analysis.models import MetricAvailability, MetricDocument
from world.identifiers import require_stable_id

__all__ = [
    "MATRIX_METRIC_SUMMARY_SCHEMA_VERSION",
    "MatrixMetricCellRef",
    "MatrixMetricKeySummary",
    "MatrixMetricSummary",
    "build_matrix_metric_summary",
]

MATRIX_METRIC_SUMMARY_SCHEMA_VERSION: Final[str] = "matrix-metric-summary-v1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.matrix_metric_summary")


@dataclass(frozen=True, slots=True)
class MatrixMetricCellRef:
    """One completed cell contributing metric documents."""

    cell_id: str
    condition_id: str
    group_role: str
    seed: int
    documents: tuple[MetricDocument, ...]


@dataclass(frozen=True, slots=True)
class MatrixMetricKeySummary:
    """Distribution summary for one family/key under one condition/role."""

    condition_id: str
    group_role: str
    metric_family: str
    algorithm_version: str
    value_key: str
    n: int
    mean: float | None
    std_sample: float | None
    median: float | None
    p05: float | None
    p95: float | None
    interval_low: float | None
    interval_high: float | None
    interval_method: str
    dropped_non_finite: int
    cell_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MatrixMetricSummary:
    """Canonical multi-seed metric distribution document."""

    schema_version: str
    key_summaries: tuple[MatrixMetricKeySummary, ...]


def build_matrix_metric_summary(
    cells: Sequence[MatrixMetricCellRef],
) -> MatrixMetricSummary:
    """Group numeric values across seed×replicate cells and summarize."""
    buckets: dict[
        tuple[str, str, str, str, str],
        list[tuple[str, object]],
    ] = defaultdict(list)
    versions: dict[tuple[str, str, str, str], str] = {}
    for cell in cells:
        if type(cell) is not MatrixMetricCellRef:
            raise TypeError("cells: invalid_type")
        cell_id = require_stable_id("cell_id", cell.cell_id)
        condition_id = require_stable_id("condition_id", cell.condition_id)
        group_role = require_stable_id("group_role", cell.group_role)
        for doc in cell.documents:
            if type(doc) is not MetricDocument:
                raise TypeError("documents: invalid_type")
            if doc.availability not in (
                MetricAvailability.PRESENT,
                MetricAvailability.PARTIAL,
            ):
                continue
            version_key = (
                condition_id,
                group_role,
                doc.metric_family,
                doc.algorithm_version,
            )
            family_algo = (condition_id, group_role, doc.metric_family)
            previous = versions.get(family_algo)
            if previous is not None and previous != doc.algorithm_version:
                raise ValueError("mixed_algorithm_version")
            versions[family_algo] = doc.algorithm_version
            _ = version_key
            for key, value in sorted(doc.values.items()):
                if value is None:
                    continue
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                bucket_key = (
                    condition_id,
                    group_role,
                    doc.metric_family,
                    doc.algorithm_version,
                    key,
                )
                buckets[bucket_key].append((cell_id, value))

    summaries: list[MatrixMetricKeySummary] = []
    for (
        condition_id,
        group_role,
        metric_family,
        algorithm_version,
        value_key,
    ), samples in sorted(buckets.items()):
        samples.sort(key=lambda item: item[0])
        values = [value for _cell_id, value in samples]
        cell_ids = tuple(sorted({cell_id for cell_id, _value in samples}))
        dist = summarize_distribution(values, interval_method="percentile")
        summaries.append(
            MatrixMetricKeySummary(
                condition_id=condition_id,
                group_role=group_role,
                metric_family=metric_family,
                algorithm_version=algorithm_version,
                value_key=value_key,
                n=dist.n,
                mean=dist.mean,
                std_sample=dist.std_sample,
                median=dist.median,
                p05=dist.p05,
                p95=dist.p95,
                interval_low=dist.interval_low,
                interval_high=dist.interval_high,
                interval_method=dist.interval_method,
                dropped_non_finite=dist.dropped_non_finite,
                cell_ids=cell_ids,
            )
        )

    _LOG.info(
        "matrix_metric_summary_built",
        extra={
            "operation": "build_matrix_metric_summary",
            "cell_count": len(cells),
            "key_summary_count": len(summaries),
            "condition_count": len({item.condition_id for item in summaries}),
            "family_count": len({item.metric_family for item in summaries}),
        },
    )
    _LOG.debug(
        "matrix_metric_summary_methods",
        extra={
            "operation": "build_matrix_metric_summary",
            "interval_methods": sorted({item.interval_method for item in summaries}),
        },
    )
    return MatrixMetricSummary(
        schema_version=MATRIX_METRIC_SUMMARY_SCHEMA_VERSION,
        key_summaries=tuple(summaries),
    )
