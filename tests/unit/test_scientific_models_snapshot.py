# mypy: ignore-errors

"""Canonical predictive snapshot bytes, closure, caps and paging."""

from __future__ import annotations

import pytest

from simulation.scientific_models_codec import (
    ScientificModelsError,
    decode_scientific_models_snapshot,
    encode_scientific_models_snapshot,
    scientific_models_snapshot_bytes,
    scientific_models_snapshot_digest,
)
from simulation.scientific_models_models import (
    ScientificCalibrationRow,
    ScientificComparisonRow,
    ScientificCoverageRow,
    ScientificModelRow,
    ScientificModelsSnapshot,
    ScientificOutcomeRow,
    ScientificPredictionRow,
    ScientificRevisionRow,
)
from simulation.scientific_models_paging import page_scientific_models_rows

pytestmark = pytest.mark.unit


def _snapshot(*, predictions: int = 2) -> ScientificModelsSnapshot:
    model = ScientificModelRow(
        owner_token="a" * 32,
        model_token="b" * 32,
        hypothesis_token="c" * 32,
        target_kind="season",
        unit_token="d" * 32,
        horizon_ticks=2,
        predictor_variant="hypothesis_baseline_v1",
        lifecycle="active",
        revision_tokens=("e" * 32,),
    )
    rows = []
    for index in range(predictions):
        rows.append(
            ScientificPredictionRow(
                owner_token="a" * 32,
                case_token=f"{index + 1:x}" * 32,
                prediction_token=f"{index + 2:x}" * 32,
                model_token="b" * 32,
                target_kind="season",
                target_token="f" * 32,
                unit_token="d" * 32,
                context_token="1" * 32,
                horizon_ticks=2,
                alphabet=("spring", "summer", "autumn", "winter"),
                probabilities_milli=(200, 400, 200, 200),
                predicted_class="summer",
                confidence_milli=400,
                issued_tick=index,
                committed_after_tick=index,
                target_observation_tick=index + 2,
                receipt_tick=index,
                window_index=0,
            )
        )
    empirical = ScientificModelRow(
        owner_token="a" * 32,
        model_token="7" * 32,
        hypothesis_token="c" * 32,
        target_kind="season",
        unit_token="d" * 32,
        horizon_ticks=2,
        predictor_variant="empirical_context_v1",
        lifecycle="active",
        revision_tokens=("8" * 32,),
    )
    outcomes = tuple(
        ScientificOutcomeRow(
            case_token=f"{index + 1:x}" * 32,
            owner_token="a" * 32,
            target_kind="season",
            target_token="f" * 32,
            unit_token="d" * 32,
            horizon_ticks=2,
            state="scored",
            settlement_reason="observed",
            observed_class="summer",
            observed_tick=index + 2,
            outcome_token="2" * 32,
        )
        for index in range(predictions)
    )
    return ScientificModelsSnapshot(
        schema_version="scientific-models-snapshot-v1",
        policy_version="scientific-models-publication.v1",
        run_token="3" * 32,
        publication_id="4" * 32,
        finalized_through_tick=9,
        coverage_status="complete",
        models=(model, empirical),
        predictions=tuple(rows),
        outcomes=outcomes,
        calibration=(
            ScientificCalibrationRow(
                group_token="5" * 32,
                target_kind="season",
                model_token="b" * 32,
                scored_count=predictions,
                brier_numerator_sum=960000,
                mean_brier_millionths=480000,
                calibration_gap_milli=600,
                insufficient=False,
            ),
        ),
        revisions=(
            ScientificRevisionRow(
                owner_token="a" * 32,
                model_token="b" * 32,
                revision_token="e" * 32,
                revision_index=0,
                tick=0,
                kind="model",
                reason="formulated",
            ),
        ),
        comparisons=(
            ScientificComparisonRow(
                group_token="6" * 32,
                target_kind="season",
                model_a_token="b" * 32,
                model_b_token="7" * 32,
                paired_count=predictions,
                mean_brier_millionths_a=480000,
                mean_brier_millionths_b=750000,
                a_minus_b_millionths=-270000,
                status="lower_loss_a",
            ),
        ),
        coverage=(
            ScientificCoverageRow(
                reason_code="retention_cap",
                target_kind="season",
                first_tick=0,
                last_tick=0,
                count=1,
            ),
        ),
    )


def test_canonical_twins_and_digest_are_stable() -> None:
    snapshot = _snapshot()
    payload = encode_scientific_models_snapshot(snapshot)
    decoded = decode_scientific_models_snapshot(payload)
    assert encode_scientific_models_snapshot(decoded) == payload
    assert decoded.publication_id == snapshot.publication_id
    assert scientific_models_snapshot_bytes(
        snapshot
    ) == scientific_models_snapshot_bytes(decode_scientific_models_snapshot(payload))
    assert scientific_models_snapshot_digest(snapshot) == (
        scientific_models_snapshot_digest(decode_scientific_models_snapshot(payload))
    )


def test_tampering_and_unknown_keys_fail_closed() -> None:
    payload = encode_scientific_models_snapshot(_snapshot())
    tampered = encode_scientific_models_snapshot(_snapshot(predictions=3))
    assert scientific_models_snapshot_digest(_snapshot()) != (
        scientific_models_snapshot_digest(_snapshot(predictions=3))
    )
    with pytest.raises(ScientificModelsError):
        decode_scientific_models_snapshot({**payload, "extra": 1})
    with pytest.raises(ScientificModelsError):
        decode_scientific_models_snapshot({**payload, "codec_version": "v2"})
    with pytest.raises(ScientificModelsError):
        decode_scientific_models_snapshot(tampered | {"codec_version": "x"})


def test_caps_and_reference_closure() -> None:
    with pytest.raises(ValueError, match="cap_exceeded"):
        ScientificModelsSnapshot(
            schema_version="scientific-models-snapshot-v1",
            policy_version="scientific-models-publication.v1",
            run_token="3" * 32,
            publication_id="4" * 32,
            finalized_through_tick=1,
            coverage_status="complete",
            notices=tuple("n" for _ in range(8193)),
        )
    model = _snapshot().models[0]
    prediction = _snapshot().predictions[0]
    with pytest.raises(ValueError, match="orphan_prediction"):
        ScientificModelsSnapshot(
            schema_version="scientific-models-snapshot-v1",
            policy_version="scientific-models-publication.v1",
            run_token="3" * 32,
            publication_id="4" * 32,
            finalized_through_tick=1,
            coverage_status="complete",
            models=(model,),
            predictions=(prediction,),
        )


def test_paging_is_stable_and_filters_by_tick_range() -> None:
    snapshot = _snapshot(predictions=5)
    first = page_scientific_models_rows(snapshot, section="predictions", page_size=2)
    assert len(first.rows) == 2
    assert first.next_offset == 2
    assert first.total == 5
    second = page_scientific_models_rows(
        snapshot, section="predictions", page_size=2, offset=first.next_offset
    )
    assert {row.prediction_token for row in first.rows}.isdisjoint(
        {row.prediction_token for row in second.rows}
    )
    filtered = page_scientific_models_rows(
        snapshot,
        section="predictions",
        page_size=10,
        issued_from_tick=2,
        issued_through_tick=3,
    )
    assert filtered.total == 2
    with pytest.raises(ValueError, match="invalid_tick_range"):
        page_scientific_models_rows(
            snapshot,
            section="predictions",
            page_size=10,
            issued_from_tick=4,
            issued_through_tick=1,
        )
    with pytest.raises(ValueError, match="invalid_page_size"):
        page_scientific_models_rows(snapshot, section="predictions", page_size=0)
