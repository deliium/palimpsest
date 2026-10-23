"""Verified loader for cultural comparison documents over completed cells."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.cultural_metric_comparison import (
    CULTURAL_METRIC_COMPARISON_SCHEMA_VERSION,
    CulturalComparisonCell,
    CulturalComparisonError,
    CulturalComparisonRequest,
    CulturalMetricComparison,
    build_cultural_metric_comparison,
)
from analysis.numerical import library_versions
from experiments.cultural_metric_artifacts import (
    CulturalArtifactError,
    CulturalCaptureOptions,
    decode_cultural_cell_metrics,
    verify_cultural_pair,
)
from experiments.matrix_expand import expand_matrix
from experiments.matrix_manifest import MatrixManifestStore
from experiments.matrix_models import MatrixCell, MatrixCellState
from simulation.generational_seeds import build_generational_seed_manifest
from simulation.models import RunId
from simulation.runner_models import RecordingPolicy, SimulationRunnerConfig

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.cultural_metric_comparison"
)

__all__ = [
    "CULTURAL_METRIC_COMPARISON_SCHEMA_VERSION",
    "encode_cultural_metric_comparison",
    "load_cultural_metric_comparison",
]


def _provider_basis(policy: RecordingPolicy) -> str:
    if policy is RecordingPolicy.DETERMINISTIC_FAKE:
        return "deterministic_fake"
    if policy is RecordingPolicy.REPLAY:
        return "immutable_replay"
    return policy.value


def _channel_lineage(cell: MatrixCell, config: object) -> tuple[tuple[str, str], ...]:
    generational = getattr(config, "generational_run", None)
    if generational is None:
        return ()
    manifest = build_generational_seed_manifest(config, RunId(cell.cell_id))  # type: ignore[arg-type]
    lineage: list[tuple[str, str]] = []
    for channel in manifest.channels:
        if channel.draw_usage not in {"sampled", "deterministic_hash"}:
            continue
        if channel.identity_selector == "durable_run_id":
            selector = f"{channel.identity_selector}:{cell.cell_id}"
        else:
            selector = f"{channel.identity_selector}:{manifest.stochastic_identity}"
        lineage.append((channel.name, selector))
    return tuple(sorted(lineage))


def _decode_options(metrics: object) -> CulturalCaptureOptions:
    policy = getattr(metrics, "capture_policy", {})
    window = getattr(metrics, "analysis_window", None)
    if not isinstance(policy, Mapping) or window is None:
        raise CulturalArtifactError("capture_policy_mismatch")
    enabled = policy.get("enabled", True)
    max_frames = policy.get("max_frames")
    max_rows = policy.get("max_rows")
    if (
        type(enabled) is not bool
        or type(max_frames) is not int
        or type(max_rows) is not int
    ):
        raise CulturalArtifactError("capture_policy_mismatch")
    return CulturalCaptureOptions(
        enabled=enabled,
        max_frames=max_frames,
        max_rows=max_rows,
        analysis_window=window,
    )


def _expected_config_fingerprints(
    spec: object,
) -> tuple[dict[tuple[str, int, int], str], dict[str, SimulationRunnerConfig]]:
    from dataclasses import replace

    from simulation.runner_serialization import runner_config_fingerprint

    definition, expected_cells = expand_matrix(spec)  # type: ignore[arg-type]
    configs = {
        condition.condition_id: condition.runner_config
        for condition in definition.conditions
    }
    fingerprints = {
        (cell.condition_id, cell.seed_ordinal, cell.replicate_index): (
            runner_config_fingerprint(
                replace(configs[cell.condition_id], seed=cell.seed)
            )
        )
        for cell in expected_cells
    }
    return fingerprints, configs


def _load_cell(
    *,
    cell: MatrixCell,
    config: object,
    store: MatrixManifestStore,
    expected_config_fingerprint: str,
    source_revision: str | None,
    group_selector_basis: str | None,
) -> CulturalComparisonCell:
    pair = store.read_cultural_artifacts(cell.cell_id)
    if pair is None:
        raise CulturalArtifactError("cultural_capture_missing")
    decoded = decode_cultural_cell_metrics(pair[1])
    options = _decode_options(decoded)
    verified = verify_cultural_pair(
        pair[0],
        pair[1],
        cell_id=cell.cell_id,
        matrix_fingerprint=decoded.matrix_fingerprint,
        cell_fingerprint=cell.cell_fingerprint,
        config_fingerprint=expected_config_fingerprint,
        run_id=cell.cell_id,
        capture_options=options,
        source_revision=source_revision,
    )
    documents = verified.metrics.documents
    versions = documents[0].library_versions if documents else library_versions()
    provider = _provider_basis(config.provider.recording_policy)  # type: ignore[attr-defined]
    return CulturalComparisonCell(
        cell_id=cell.cell_id,
        condition_id=cell.condition_id,
        seed=cell.seed,
        seed_ordinal=cell.seed_ordinal,
        replicate_index=cell.replicate_index,
        stochastic_identity=config.stochastic_identity.value,  # type: ignore[attr-defined]
        channel_lineage=_channel_lineage(cell, config),
        provider_basis=provider,
        factor_levels=cell.factor_levels,
        config_fingerprint=expected_config_fingerprint,
        expected_config_fingerprint=expected_config_fingerprint,
        cell_fingerprint=cell.cell_fingerprint,
        code_revision=verified.evidence.inputs.source_revision,
        library_versions=dict(versions),
        documents=documents,
        evidence_digest=verified.metrics.evidence_digest,
        group_selector_basis=group_selector_basis,
    )


def load_cultural_metric_comparison(
    *,
    spec: object,
    cells: Sequence[MatrixCell],
    store: MatrixManifestStore,
    comparisons: Sequence[CulturalComparisonRequest] = (),
    confidence: float = 0.95,
    source_revision: str | None = None,
    group_selector_basis: str | None = None,
) -> CulturalMetricComparison:
    """Verify completed bound artifacts, then build the comparison document."""
    expected, configs = _expected_config_fingerprints(spec)
    from experiments.matrix_models import matrix_spec_fingerprint

    matrix_fingerprint = matrix_spec_fingerprint(spec)  # type: ignore[arg-type]
    inputs: list[CulturalComparisonCell] = []
    for cell in cells:
        if not store.has_valid_completion(cell, matrix_fingerprint=matrix_fingerprint):
            raise CulturalComparisonError("comparison_incompatible")
        record = store.get_cell(cell.cell_id)
        if record.state not in (
            MatrixCellState.COMPLETED,
            MatrixCellState.SKIPPED_VALID,
        ):
            raise CulturalComparisonError("comparison_incompatible")
        key = (cell.condition_id, cell.seed_ordinal, cell.replicate_index)
        config_fingerprint = expected.get(key)
        if config_fingerprint is None:
            raise CulturalComparisonError("comparison_factor_mismatch")
        base_config = configs.get(cell.condition_id)
        if base_config is None:
            raise CulturalComparisonError("comparison_factor_mismatch")
        from dataclasses import replace

        config = replace(base_config, seed=cell.seed)
        inputs.append(
            _load_cell(
                cell=cell,
                config=config,
                store=store,
                expected_config_fingerprint=config_fingerprint,
                source_revision=source_revision,
                group_selector_basis=group_selector_basis,
            )
        )
    _LOG.info(
        "cultural_metric_comparison_loaded cell_count=%s contrast_count=%s",
        len(inputs),
        len(comparisons),
    )
    return build_cultural_metric_comparison(
        tuple(inputs),
        matrix_fingerprint=matrix_fingerprint,
        comparisons=tuple(comparisons),
        confidence=confidence,
    )


def encode_cultural_metric_comparison(
    comparison: CulturalMetricComparison,
) -> bytes:
    """Canonical UTF-8 JSON sibling document."""
    if type(comparison) is not CulturalMetricComparison:
        raise TypeError("comparison must be CulturalMetricComparison")
    payload = comparison.to_payload()
    data = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return data
