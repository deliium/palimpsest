# mypy: ignore-errors

"""Property tests: normalized distributions, exact loss bounds and idempotence."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.cognition.scientific_model_lifecycle import (
    advance_scientific_models,
)
from agents.cognition.scientific_model_prediction import (
    baseline_distribution,
    empirical_distribution,
    largest_remainder,
)
from agents.cognition.scientific_model_scoring import score_model_prediction
from agents.cognition.scientific_models import (
    SEASON_CLASSES,
    ModelPrediction,
    ModelPredictorVariant,
    scientific_model_content_count,
    scientific_prediction_id,
)
from tests.unit.test_scientific_models_lifecycle import (
    _experiment_ledger,
    _observation,
    _season_ledger,
)
from world.environment import Season

pytestmark = pytest.mark.unit


def _prediction(probabilities: tuple[int, ...], predicted: str) -> ModelPrediction:
    return ModelPrediction(
        prediction_id=scientific_prediction_id(
            "smc:prop", ModelPredictorVariant.HYPOTHESIS_BASELINE_V1
        ),
        model_id="smm:prop",
        hypothesis_id="smh:prop",
        predictor_variant=ModelPredictorVariant.HYPOTHESIS_BASELINE_V1,
        alphabet=SEASON_CLASSES,
        probabilities_milli=probabilities,
        predicted_class=predicted,
        confidence_milli=probabilities[SEASON_CLASSES.index(predicted)],
        model_revision_ref="smm:prop#0",
        source_revision_ref="smh:prop#0",
        parameter_digest="par:prop",
    )


@settings(max_examples=50, deadline=None)
@given(st.lists(st.integers(0, 10_000), min_size=1, max_size=5))
def test_largest_remainder_is_normalized_and_nonnegative(weights: list[int]) -> None:
    values = largest_remainder(tuple(weights))
    assert len(values) == len(weights)
    assert sum(values) == 1000
    assert all(value >= 0 for value in values)


def test_baseline_and_empirical_distributions_are_normalized() -> None:
    for predicted in SEASON_CLASSES:
        values = baseline_distribution(SEASON_CLASSES, predicted)
        assert sum(values) == 1000
        assert values[SEASON_CLASSES.index(predicted)] == 400
    uniform = empirical_distribution(SEASON_CLASSES, (0, 0, 0, 0))
    assert uniform == (250, 250, 250, 250)


@settings(max_examples=50, deadline=None)
@given(
    weights=st.lists(st.integers(0, 1000), min_size=4, max_size=4).filter(
        lambda rows: sum(rows) > 0
    )
)
def test_brier_stays_bounded_and_zero_for_perfect_forecasts(
    weights: list[int],
) -> None:
    total = sum(weights)
    scaled = [value * 1000 // total for value in weights]
    scaled[0] += 1000 - sum(scaled)
    best = max(range(4), key=lambda index: (scaled[index], -index))
    prediction = _prediction(tuple(scaled), SEASON_CLASSES[best])
    numerator = score_model_prediction(prediction, SEASON_CLASSES[best])
    assert 0 <= numerator <= 2_000_000
    perfect_index = best
    perfect = [0, 0, 0, 0]
    perfect[perfect_index] = 1000
    assert (
        score_model_prediction(
            _prediction(tuple(perfect), SEASON_CLASSES[perfect_index]),
            SEASON_CLASSES[perfect_index],
        )
        == 0
    )


def test_advance_is_idempotent_for_repeated_observations() -> None:
    ledger = _season_ledger()
    first = advance_scientific_models(
        ledger,
        _observation(
            12,
            season=Season.SUMMER,
        ),
        experiment_ledger=_experiment_ledger(),
    )
    second = advance_scientific_models(
        first,
        _observation(
            12,
            season=Season.SUMMER,
        ),
        experiment_ledger=_experiment_ledger(),
    )
    assert second == first
    assert scientific_model_content_count(second) >= 0
