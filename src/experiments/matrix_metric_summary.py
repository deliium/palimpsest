"""Thin filesystem I/O wrapper around analysis matrix metric summaries."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Final

from analysis.matrix_metric_summary import (
    MATRIX_METRIC_SUMMARY_SCHEMA_VERSION,
    MatrixMetricCellRef,
    MatrixMetricSummary,
    build_matrix_metric_summary,
)
from experiments.matrix_manifest import FilesystemMatrixManifestStore
from experiments.matrix_models import MatrixCell

_LOG: Final[logging.Logger] = logging.getLogger("experiments.matrix_metric_summary")

__all__ = [
    "encode_matrix_metric_summary",
    "load_matrix_metric_summary_from_store",
]


def encode_matrix_metric_summary(summary: MatrixMetricSummary) -> bytes:
    """Canonical JSON encoding of a matrix metric summary document."""
    payload = {
        "schema_version": summary.schema_version,
        "key_summaries": [asdict(item) for item in summary.key_summaries],
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def load_matrix_metric_summary_from_store(
    store: FilesystemMatrixManifestStore,
    cells: Sequence[MatrixCell],
    *,
    group_role_for_cell: object | None = None,
) -> MatrixMetricSummary:
    """Read metric sidecars and build ``matrix-metric-summary-v1``."""
    refs: list[MatrixMetricCellRef] = []
    for cell in cells:
        documents = store.read_metric_documents(cell.cell_id)
        if documents is None:
            continue
        if group_role_for_cell is not None:
            role = str(group_role_for_cell(cell))
        else:
            role = cell.group_role.value
        refs.append(
            MatrixMetricCellRef(
                cell_id=cell.cell_id,
                condition_id=cell.condition_id,
                group_role=role,
                seed=int(cell.seed),
                documents=tuple(documents),  # type: ignore[arg-type]
            )
        )
    summary = build_matrix_metric_summary(refs)
    _LOG.info(
        "matrix_metric_summary_loaded",
        extra={
            "experiment": {
                "schema_version": MATRIX_METRIC_SUMMARY_SCHEMA_VERSION,
                "cell_with_sidecars": len(refs),
                "key_summary_count": len(summary.key_summaries),
            }
        },
    )
    return summary


def write_matrix_metric_summary(
    root: Path | str,
    summary: MatrixMetricSummary,
    *,
    filename: str = "metric-summary.json",
) -> Path:
    """Write summary JSON beside the manifest root."""
    path = Path(root) / filename
    path.write_bytes(encode_matrix_metric_summary(summary))
    return path
