"""Repeated-seed cultural comparison and paired seed-block inference tests."""

from __future__ import annotations

import json
import math

import pytest
from scipy import stats

from analysis.cultural_evolution_evidence import (
    CULTURAL_EVOLUTION_POLICY_VERSION,
    CulturalMeasurement,
)
from analysis.cultural_metric_comparison import (
    CulturalComparisonCell,
    CulturalComparisonError,
    CulturalComparisonRequest,
    build_cultural_metric_comparison,
)
from analysis.cultural_trait_dynamics import (
    CULTURAL_TRAIT_DYNAMICS_ALGORITHM_VERSION,
)
from analysis.evidence import EvidenceStage
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions
from analysis.specifications import MetricFamilyId


def _measurement(
    value: float | None,
    *,
    measurement_id: str = "richness",
    units: str = "count",
    denominator_code: str = "carrier_incidences",
    baseline_tick: int = 0,
    end_tick: int = 2,
    trait_id: str | None = None,
) -> CulturalMeasurement:
    return CulturalMeasurement(
        family=MetricFamilyId.CULTURAL_TRAIT_DYNAMICS.value,
        algorithm_version=CULTURAL_TRAIT_DYNAMICS_ALGORITHM_VERSION,
        policy_version=CULTURAL_EVOLUTION_POLICY_VERSION,
        measurement_id=measurement_id,
        dimension="vocabulary",
        representation="ledger_carriage",
        scope="global",
        partition_id=None,
        group_ids=(),
        population_basis=denominator_code,
        denominator_code=denominator_code,
        baseline_tick=baseline_tick,
        end_tick=end_tick,
        trait_id=trait_id,
        lineage_id=None,
        subject_id=None,
        units=units,
        value=value,
        numerator=None,
        denominator=None,
        availability=MetricAvailability.PRESENT,
        reason_code=None,
        coverage_observed=1,
        coverage_expected=1,
        left_censored=False,
        right_censored=False,
        evidence_ids=(),
    )


def _document(
    rows: tuple[CulturalMeasurement, ...],
    *,
    algorithm_version: str = "1",
    availability: MetricAvailability = MetricAvailability.PRESENT,
) -> MetricDocument:
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=MetricFamilyId.CULTURAL_TRAIT_DYNAMICS.value,
        algorithm_version=algorithm_version,
        library_versions=library_versions(),
        run_id="run-1",
        input_revision="rev-1",
        evidence_stages=frozenset({EvidenceStage.BELIEF_REVISION_TESTIMONY}),
        population="cultural_evolution_normalized_evidence",
        denominator="fixed_scientific_selector_denominator",
        coverage=None,
        availability=availability,
        values={
            "policy_version": CULTURAL_EVOLUTION_POLICY_VERSION,
            "window_start": 0,
            "window_end": 2,
            "measurement_count": len(rows),
            "rows_json": json.dumps(
                [row.to_payload() for row in rows],
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
            "evidence_manifest_digest": "d" * 64,
        },
        provenance=MetricProvenance(
            source_kind="cultural_evolution_evidence",
            source_ids=("d" * 64,),
            notes_code="normalized_evidence",
        ),
    )


def _cell(
    cell_id: str,
    condition: str,
    seed: int,
    value: float,
    *,
    seed_ordinal: int | None = None,
    replicate: int = 0,
    factor_levels: tuple[tuple[str, str], ...] = (("memory_type", "reference"),),
    expected_config_fingerprint: str = "f" * 64,
    config_fingerprint: str = "f" * 64,
    provider_basis: str = "deterministic_fake",
    channel_lineage: tuple[tuple[str, str], ...] = (),
    measurement_id: str = "richness",
    units: str = "count",
    denominator_code: str = "carrier_incidences",
    baseline_tick: int = 0,
    end_tick: int = 2,
    algorithm_version: str = "1",
    code_revision: str = "rev-1",
    rows: tuple[CulturalMeasurement, ...] | None = None,
) -> CulturalComparisonCell:
    row = _measurement(
        value,
        measurement_id=measurement_id,
        units=units,
        denominator_code=denominator_code,
        baseline_tick=baseline_tick,
        end_tick=end_tick,
    )
    document = _document(
        (row,) if rows is None else rows,
        algorithm_version=algorithm_version,
    )
    return CulturalComparisonCell(
        cell_id=cell_id,
        condition_id=condition,
        seed=seed,
        seed_ordinal=seed if seed_ordinal is None else seed_ordinal,
        replicate_index=replicate,
        stochastic_identity="stochastic-1",
        channel_lineage=channel_lineage,
        provider_basis=provider_basis,
        factor_levels=factor_levels,
        config_fingerprint=config_fingerprint,
        expected_config_fingerprint=expected_config_fingerprint,
        cell_fingerprint="c" * 64,
        code_revision=code_revision,
        library_versions=library_versions(),
        documents=(document,),
        evidence_digest="d" * 64,
    )


def _condition_cells(
    condition: str,
    values: tuple[float, ...],
    *,
    seed_offset: int = 0,
    factor_levels: tuple[tuple[str, str], ...] = (("memory_type", "reference"),),
    **kwargs: object,
) -> tuple[CulturalComparisonCell, ...]:
    return tuple(
        _cell(
            f"{condition}-s{seed_offset + index}",
            condition,
            seed_offset + index,
            value,
            factor_levels=factor_levels,
            **kwargs,  # type: ignore[arg-type]
        )
        for index, value in enumerate(values)
    )


def test_hand_computed_seed_block_mean_and_t_interval() -> None:
    result = build_cultural_metric_comparison(
        _condition_cells("control", (1.0, 2.0, 3.0)),
        matrix_fingerprint="m" * 64,
    )
    summary = result.conditions[0].measurements[0]
    assert summary.n == 3
    assert summary.raw_cell_count == 3
    assert summary.mean == pytest.approx(2.0)
    assert summary.std_sample == pytest.approx(1.0)
    margin = float(stats.t.ppf(0.975, 2)) * 1.0 / math.sqrt(3)
    assert summary.ci_low == pytest.approx(2.0 - margin)
    assert summary.ci_high == pytest.approx(2.0 + margin)
    assert summary.df == 2
    assert summary.inference_status == "present"
    assert [block.seed for block in summary.seed_blocks] == [0, 1, 2]


def test_one_seed_and_constant_values() -> None:
    one = (
        build_cultural_metric_comparison(
            _condition_cells("control", (4.0,)),
            matrix_fingerprint="m" * 64,
        )
        .conditions[0]
        .measurements[0]
    )
    assert one.n == 1
    assert one.mean == 4.0
    assert one.ci_low is None and one.ci_high is None
    assert one.inference_status == "insufficient_independent_seeds"

    constant = (
        build_cultural_metric_comparison(
            _condition_cells("control", (2.0, 2.0)),
            matrix_fingerprint="m" * 64,
        )
        .conditions[0]
        .measurements[0]
    )
    assert constant.std_sample == 0.0
    assert constant.ci_low == 2.0 and constant.ci_high == 2.0


def test_duplicate_seed_replicas_do_not_inflate_independent_n() -> None:
    cells = (
        _cell("c-1", "control", 7, 1.0, seed_ordinal=0, replicate=0),
        _cell("c-2", "control", 7, 3.0, seed_ordinal=0, replicate=1),
        _cell("c-3", "control", 8, 5.0, seed_ordinal=1, replicate=0),
    )
    summary = (
        build_cultural_metric_comparison(cells, matrix_fingerprint="m" * 64)
        .conditions[0]
        .measurements[0]
    )
    assert summary.n == 2
    assert summary.raw_cell_count == 3
    assert summary.duplicate_cell_count == 1
    assert summary.mean == pytest.approx(3.5)


def test_shuffled_cells_produce_identical_payload() -> None:
    cells = _condition_cells("control", (1.0, 2.0, 3.0))
    forward = build_cultural_metric_comparison(
        cells, matrix_fingerprint="m" * 64
    ).to_payload()
    reverse = build_cultural_metric_comparison(
        tuple(reversed(cells)), matrix_fingerprint="m" * 64
    ).to_payload()
    assert json.dumps(forward, sort_keys=True) == json.dumps(reverse, sort_keys=True)


def test_paired_contrast_excludes_missing_arm_and_uses_complete_pairs() -> None:
    control = _condition_cells("control", (1.0, 2.0, 100.0))
    treatment = _condition_cells(
        "treatment",
        (2.0, 2.0),
        factor_levels=(("memory_type", "reconstructive"),),
    )
    result = build_cultural_metric_comparison(
        (*control, *treatment),
        matrix_fingerprint="m" * 64,
        comparisons=(CulturalComparisonRequest("mem-pair", "control", "treatment"),),
    )
    contrast = result.contrasts[0]
    assert contrast.n == 2
    assert contrast.mean_difference == pytest.approx(0.5)
    assert contrast.pair_ids == ("control-s0+treatment-s0", "control-s1+treatment-s1")
    assert contrast.unmatched_cells == ("control-s2",)
    assert contrast.pairing_basis == "seed_ordinal_replicate"


def test_multiple_metrics_and_conditions_with_explicit_ids() -> None:
    control = _condition_cells("control", (1.0, 2.0, 3.0))
    treatment_a = _condition_cells(
        "treatment-a",
        (2.0, 3.0, 4.0),
        factor_levels=(("memory_type", "reconstructive"),),
    )
    treatment_b = _condition_cells(
        "treatment-b",
        (3.0, 4.0, 5.0),
        factor_levels=(("memory_type", "plain"),),
    )
    result = build_cultural_metric_comparison(
        (*control, *treatment_a, *treatment_b),
        matrix_fingerprint="m" * 64,
        comparisons=(
            CulturalComparisonRequest("a-vs-control", "control", "treatment-a"),
            CulturalComparisonRequest("b-vs-control", "control", "treatment-b"),
        ),
    )
    assert [item.contrast_id for item in result.contrasts] == [
        "a-vs-control",
        "b-vs-control",
    ]
    assert [item.mean_difference for item in result.contrasts] == [
        pytest.approx(1.0),
        pytest.approx(2.0),
    ]


def test_factor_rematerialization_and_multi_axis_rejection() -> None:
    control = _cell("c-1", "control", 1, 1.0)
    valid = _cell(
        "t-1",
        "treatment",
        1,
        2.0,
        factor_levels=(("memory_type", "reconstructive"),),
        config_fingerprint="a" * 64,
        expected_config_fingerprint="a" * 64,
    )
    result = build_cultural_metric_comparison(
        (control, valid),
        matrix_fingerprint="m" * 64,
        comparisons=(CulturalComparisonRequest("pair", "control", "treatment"),),
    )
    assert result.contrasts[0].mean_difference == pytest.approx(1.0)

    with pytest.raises(CulturalComparisonError, match="comparison_factor_mismatch"):
        build_cultural_metric_comparison(
            (
                control,
                _cell(
                    "t-1",
                    "treatment",
                    1,
                    2.0,
                    factor_levels=(("memory_type", "reconstructive"),),
                    config_fingerprint="b" * 64,
                    expected_config_fingerprint="a" * 64,
                ),
            ),
            matrix_fingerprint="m" * 64,
            comparisons=(CulturalComparisonRequest("pair", "control", "treatment"),),
        )

    with pytest.raises(CulturalComparisonError, match="comparison_factor_mismatch"):
        build_cultural_metric_comparison(
            (
                control,
                _cell(
                    "t-1",
                    "treatment",
                    1,
                    2.0,
                    factor_levels=(
                        ("memory_type", "reconstructive"),
                        ("tom", "on"),
                    ),
                    config_fingerprint="a" * 64,
                    expected_config_fingerprint="a" * 64,
                ),
            ),
            matrix_fingerprint="m" * 64,
            comparisons=(CulturalComparisonRequest("pair", "control", "treatment"),),
        )


def test_mismatched_selectors_are_incompatible() -> None:
    control = _cell("c-1", "control", 1, 1.0)
    for kwargs in (
        {"units": "proportion"},
        {"denominator_code": "fixed_baseline_traits"},
        {"end_tick": 3},
        {"algorithm_version": "2"},
        {"code_revision": "rev-2"},
    ):
        treatment = _cell(
            "t-1",
            "treatment",
            1,
            2.0,
            factor_levels=(("memory_type", "reconstructive"),),
            **kwargs,
        )
        with pytest.raises(CulturalComparisonError, match="comparison_incompatible"):
            build_cultural_metric_comparison(
                (control, treatment),
                matrix_fingerprint="m" * 64,
                comparisons=(
                    CulturalComparisonRequest("pair", "control", "treatment"),
                ),
            )


def test_duplicate_cell_and_confidence_validation() -> None:
    cell = _cell("c-1", "control", 1, 1.0)
    with pytest.raises(CulturalComparisonError, match="duplicate_comparison_cell"):
        build_cultural_metric_comparison((cell, cell), matrix_fingerprint="m" * 64)
    for confidence in (0.0, 1.0, -0.1, float("nan")):
        with pytest.raises(CulturalComparisonError, match="invalid_confidence"):
            build_cultural_metric_comparison(
                (cell,), matrix_fingerprint="m" * 64, confidence=confidence
            )


def test_uncontrolled_provider_and_stream_alignment() -> None:
    control = _condition_cells("control", (1.0, 2.0))
    live = tuple(
        _cell(
            f"live-s{cell.seed}",
            "live",
            cell.seed,
            float(cell.seed),
            factor_levels=(("memory_type", "reconstructive"),),
            provider_basis="live",
        )
        for cell in control
    )
    live_control = tuple(
        _cell(
            f"live-control-s{cell.seed}",
            "control",
            cell.seed,
            float(cell.seed),
            provider_basis="live",
        )
        for cell in control
    )
    live_result = build_cultural_metric_comparison(
        (*live_control, *live),
        matrix_fingerprint="m" * 64,
        comparisons=(CulturalComparisonRequest("live", "control", "live"),),
    )
    live_summary = live_result.conditions[1].measurements[0]
    assert live_summary.inference_status == "uncontrolled_provider_variation"
    assert live_summary.ci_low is None and live_summary.ci_high is None
    assert (
        live_result.contrasts[0].inference_status == "uncontrolled_provider_variation"
    )

    shared = tuple(
        _cell(
            f"treatment-s{cell.seed}",
            "treatment",
            cell.seed,
            float(cell.seed),
            factor_levels=(("memory_type", "reconstructive"),),
            channel_lineage=(("world", "stochastic:abc"),),
        )
        for cell in control
    )
    control_shared = tuple(
        _cell(
            cell.cell_id,
            "control",
            cell.seed,
            float(cell.seed),
            channel_lineage=(("world", "stochastic:abc"),),
        )
        for cell in control
    )
    result = build_cultural_metric_comparison(
        (*control_shared, *shared),
        matrix_fingerprint="m" * 64,
        comparisons=(CulturalComparisonRequest("s", "control", "treatment"),),
    )
    assert result.contrasts[0].shared_stream_status == "shared"

    mixed = tuple(
        _cell(
            f"mixed-s{cell.seed}",
            "treatment",
            cell.seed,
            float(cell.seed),
            factor_levels=(("memory_type", "reconstructive"),),
            channel_lineage=(
                ("world", "stochastic:abc"),
                ("demography", "run:other"),
            ),
        )
        for cell in control
    )
    mixed_control = tuple(
        _cell(
            cell.cell_id,
            "control",
            cell.seed,
            float(cell.seed),
            channel_lineage=(
                ("world", "stochastic:abc"),
                ("demography", "run:control"),
            ),
        )
        for cell in control
    )
    result = build_cultural_metric_comparison(
        (*mixed_control, *mixed),
        matrix_fingerprint="m" * 64,
        comparisons=(CulturalComparisonRequest("m", "control", "treatment"),),
    )
    assert result.contrasts[0].shared_stream_status == "mixed"

    unknown = tuple(
        _cell(
            f"unknown-s{cell.seed}",
            "treatment",
            cell.seed,
            float(cell.seed),
            factor_levels=(("memory_type", "reconstructive"),),
        )
        for cell in control
    )
    result = build_cultural_metric_comparison(
        (*control, *unknown),
        matrix_fingerprint="m" * 64,
        comparisons=(CulturalComparisonRequest("u", "control", "treatment"),),
    )
    assert result.contrasts[0].shared_stream_status == "unknown"


def _cell_with_raw_rows(
    cell_id: str,
    condition: str,
    seed: int,
    rows_json: str,
) -> CulturalComparisonCell:
    from dataclasses import replace

    cell = _cell(cell_id, condition, seed, 1.0)
    document = replace(
        cell.documents[0],
        values={**cell.documents[0].values, "rows_json": rows_json},
    )
    return replace(cell, documents=(document,))


def test_duplicate_keys_inside_rows_json_are_rejected() -> None:
    payload = _measurement(1.0).to_payload()
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    duplicated = encoded[:-1] + ',"value":2.0}'
    cell = _cell_with_raw_rows("c1", "control", 1, f"[{duplicated}]")
    with pytest.raises(CulturalComparisonError, match="comparison_incompatible"):
        build_cultural_metric_comparison((cell,), matrix_fingerprint="m" * 64)


def test_oversized_rows_json_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    import analysis.cultural_metric_comparison as module

    monkeypatch.setattr(module, "MAX_ROWS_JSON_BYTES", 8)
    cell = _cell_with_raw_rows(
        "c1", "control", 1, json.dumps([_measurement(1.0).to_payload()])
    )
    with pytest.raises(CulturalComparisonError, match="comparison_incompatible"):
        build_cultural_metric_comparison((cell,), matrix_fingerprint="m" * 64)


def test_partial_rows_are_excluded_from_inference() -> None:
    from dataclasses import replace

    row = replace(_measurement(1.0), availability=MetricAvailability.PARTIAL)
    common = _cell("c1", "control", 1, 1.0)
    partial_cell = replace(
        common,
        documents=(_document((row,)),),
    )
    result = build_cultural_metric_comparison(
        (partial_cell,), matrix_fingerprint="m" * 64
    )
    assert result.conditions[0].measurements == ()
