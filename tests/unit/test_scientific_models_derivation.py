"""Admissible owner evidence derives typed, fallible model hypotheses."""

from __future__ import annotations

import pytest

from agents.cognition.experimentation import (
    ExperimentHypothesis,
    ExperimentLedger,
    HypothesisStatus,
)
from agents.cognition.scientific_model_derivation import (
    derive_model_hypotheses,
    quantity_milli,
)
from agents.cognition.scientific_models import (
    ModelLifecycle,
    ModelRevisionReason,
    ModelSourceKind,
    ModelTargetKind,
    ScientificModelLedger,
    empty_scientific_model_ledger,
)
from world.environment import Season
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import AgentId, EntityId, WorldId, WorldRevision
from world.observations import Observation, ObservedResource
from world.values import ResourceKind

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_OTHER = AgentId("agent-2")
_WORLD = WorldId("world-1")
_RESOURCE = EntityId("res-1")


def _experiment_ledger(
    *,
    owner_id: AgentId = _OWNER,
    hypotheses: tuple[ExperimentHypothesis, ...] = (),
) -> ExperimentLedger:
    return ExperimentLedger(
        owner_id=owner_id,
        max_hypotheses=8,
        max_trials_per_tick=1,
        repeat_threshold=1,
        learn_into_genealogy=False,
        hypotheses=hypotheses,
    )


def _observation(
    tick: int,
    *,
    season: Season | None = None,
    quantity: float | None = None,
    owner_id: AgentId = _OWNER,
    include_resource: bool = True,
) -> Observation:
    resources: tuple[ObservedResource, ...] = ()
    if include_resource and quantity is not None:
        resources = (
            ObservedResource(
                entity_id=_RESOURCE,
                name="grain",
                kind=ResourceKind.FOOD,
                quantity=quantity,
                unit="grain",
            ),
        )
    return Observation(
        world_id=_WORLD,
        observer_id=EntityId(owner_id.value),
        revision=WorldRevision(tick),
        tick=tick,
        season=season,
        resources=resources,
    )


def _production_hypothesis(
    *,
    predicted: str | None = "success",
    process: ExperimentProcessToken = ExperimentProcessToken.HARVEST,
    active: bool = True,
    owner_id: AgentId = _OWNER,
    hypothesis_id: str = "hyp:prod-1",
) -> ExperimentHypothesis:
    return ExperimentHypothesis(
        owner_id=owner_id,
        hypothesis_id=hypothesis_id,
        operator=ExperimentOperator.COMBINE,
        operand_a_id="wheat",
        process_token=process,
        predicted_outcome=predicted,
        active=active,
        created_tick=0,
    )


def _derive(
    ledger: ScientificModelLedger,
    observation: Observation,
    *,
    experiment_ledger: ExperimentLedger | None = None,
    causal_world_model: object | None = None,
) -> ScientificModelLedger:
    return derive_model_hypotheses(
        ledger,
        observation,
        experiment_ledger=experiment_ledger or _experiment_ledger(),
        causal_world_model=causal_world_model,
    )


def test_quantity_conversion_is_half_even_milli() -> None:
    assert quantity_milli(1.0) == 1000
    assert quantity_milli(0.0005) == 0
    assert quantity_milli(0.0015) == 2
    assert quantity_milli(2.5) == 2500


def test_season_lag_two_modal_hypothesis() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    rows = (
        (0, Season.SPRING),
        (1, Season.SPRING),
        (2, Season.SUMMER),
        (3, Season.SUMMER),
    )
    for tick, season in rows:
        ledger = _derive(ledger, _observation(tick, season=season))
    hypotheses = [
        row for row in ledger.hypotheses if row.target_kind is ModelTargetKind.SEASON
    ]
    assert len(hypotheses) == 1
    hypothesis = hypotheses[0]
    assert hypothesis.predicted_class == "summer"
    assert hypothesis.target_ref == "season:spring"
    assert hypothesis.unit_token == "season"
    assert hypothesis.horizon_ticks == 2
    assert hypothesis.source_kind is ModelSourceKind.OBSERVED_REGULARITY
    assert hypothesis.lifecycle is ModelLifecycle.ACTIVE
    assert any(
        row.reason is ModelRevisionReason.FORMULATED for row in hypothesis.revisions
    )


def test_season_requires_two_complete_pairs() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    for tick, season in ((0, Season.SPRING), (1, Season.SPRING), (2, Season.SUMMER)):
        ledger = _derive(ledger, _observation(tick, season=season))
    assert ledger.hypotheses == ()


def test_missing_season_never_creates_a_transition() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    ledger = _derive(ledger, _observation(0, season=Season.SPRING))
    ledger = _derive(ledger, _observation(1, season=Season.SPRING))
    ledger = _derive(ledger, _observation(2, season=None))
    ledger = _derive(ledger, _observation(3, season=Season.SUMMER))
    assert ledger.hypotheses == ()


def test_resource_net_change_hypothesis() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    for tick, quantity in ((0, 10.0), (1, 10.0), (2, 20.0), (3, 20.0)):
        ledger = _derive(ledger, _observation(tick, quantity=quantity))
    hypotheses = [
        row
        for row in ledger.hypotheses
        if row.target_kind is ModelTargetKind.RESOURCE_REGENERATION
    ]
    assert len(hypotheses) == 1
    hypothesis = hypotheses[0]
    assert hypothesis.predicted_class == "increase"
    assert hypothesis.unit_token == "grain"
    assert hypothesis.target_ref == f"{_RESOURCE}:unknown"


def test_resource_decrease_is_a_net_change_not_regeneration() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    for tick, quantity in ((0, 8.0), (1, 8.0), (2, 3.0), (3, 3.0)):
        ledger = _derive(ledger, _observation(tick, quantity=quantity))
    hypothesis = next(
        row
        for row in ledger.hypotheses
        if row.target_kind is ModelTargetKind.RESOURCE_REGENERATION
    )
    assert hypothesis.predicted_class == "decrease"
    assert hypothesis.unit_token == "grain"


def test_occluded_resource_suspends_and_restores_the_same_model() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    for tick, quantity in ((0, 10.0), (1, 10.0), (2, 20.0), (3, 20.0)):
        ledger = _derive(ledger, _observation(tick, quantity=quantity))
    hypothesis = next(
        row
        for row in ledger.hypotheses
        if row.target_kind is ModelTargetKind.RESOURCE_REGENERATION
    )
    hypothesis_id = hypothesis.hypothesis_id
    ledger = _derive(ledger, _observation(4, include_resource=False))
    suspended = next(
        row for row in ledger.hypotheses if row.hypothesis_id == hypothesis_id
    )
    assert suspended.lifecycle is ModelLifecycle.SUSPENDED
    ledger = _derive(ledger, _observation(5, quantity=20.0))
    resumed = next(
        row for row in ledger.hypotheses if row.hypothesis_id == hypothesis_id
    )
    assert resumed.lifecycle is ModelLifecycle.ACTIVE
    assert any(row.reason is ModelRevisionReason.RESUMED for row in resumed.revisions)


def test_production_hypothesis_freezes_the_experiment_claim() -> None:
    source = _production_hypothesis()
    ledger = empty_scientific_model_ledger(_OWNER)
    ledger = _derive(
        ledger,
        _observation(0),
        experiment_ledger=_experiment_ledger(hypotheses=(source,)),
    )
    rows = [
        row
        for row in ledger.hypotheses
        if row.target_kind is ModelTargetKind.PRODUCTION_OUTCOME
    ]
    assert len(rows) == 1
    assert rows[0].target_ref == source.hypothesis_id
    assert rows[0].predicted_class == ExperimentOutcomeClass.SUCCESS.value
    assert rows[0].horizon_ticks == 2
    assert rows[0].source_kind is ModelSourceKind.EXPERIMENT_HYPOTHESIS


def test_ineligible_production_sources_are_not_adopted() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    for source in (
        _production_hypothesis(
            hypothesis_id="hyp:a", process=ExperimentProcessToken.NONE
        ),
        _production_hypothesis(hypothesis_id="hyp:b", active=False),
        _production_hypothesis(hypothesis_id="hyp:c", predicted=None),
    ):
        updated = _derive(
            ledger,
            _observation(0),
            experiment_ledger=_experiment_ledger(hypotheses=(source,)),
        )
        assert updated.hypotheses == ()


def test_changed_source_claim_appends_a_revision_without_new_identity() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    first = _production_hypothesis(predicted="success")
    ledger = _derive(
        ledger,
        _observation(0),
        experiment_ledger=_experiment_ledger(hypotheses=(first,)),
    )
    hypothesis_id = ledger.hypotheses[0].hypothesis_id
    changed = _production_hypothesis(predicted="failure")
    ledger = _derive(
        ledger,
        _observation(1),
        experiment_ledger=_experiment_ledger(hypotheses=(changed,)),
    )
    assert [row.hypothesis_id for row in ledger.hypotheses] == [hypothesis_id]
    hypothesis = ledger.hypotheses[0]
    assert hypothesis.predicted_class == "failure"
    assert len(hypothesis.revisions) >= 2
    assert hypothesis.revisions[-1].reason is ModelRevisionReason.SOURCE_CHANGED


def test_retired_source_suspends_but_keeps_the_hypothesis() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    source = _production_hypothesis()
    ledger = _derive(
        ledger,
        _observation(0),
        experiment_ledger=_experiment_ledger(hypotheses=(source,)),
    )
    ledger = _derive(
        ledger,
        _observation(1),
        experiment_ledger=_experiment_ledger(
            hypotheses=(_production_hypothesis(active=False),)
        ),
    )
    hypothesis = ledger.hypotheses[0]
    assert hypothesis.lifecycle is ModelLifecycle.SUSPENDED


def test_repeated_observation_key_is_a_no_op() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    observation = _observation(2, season=Season.SPRING, quantity=4.0)
    first = _derive(ledger, observation)
    second = _derive(first, observation)
    assert second == first


def test_out_of_order_observation_fails_closed() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    ledger = _derive(ledger, _observation(5, season=Season.SPRING))
    with pytest.raises(ValueError, match="out_of_order"):
        _derive(ledger, _observation(4, season=Season.SPRING))


def test_foreign_owner_evidence_is_rejected() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    with pytest.raises(ValueError, match="owner_mismatch"):
        _derive(ledger, _observation(0, owner_id=_OTHER))
    with pytest.raises(ValueError, match="owner_mismatch"):
        _derive(
            ledger,
            _observation(0),
            experiment_ledger=_experiment_ledger(owner_id=_OTHER),
        )


def test_disease_risk_stays_unavailable_and_unmodelled() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    ledger = _derive(ledger, _observation(0))
    notices = [
        row
        for row in ledger.notices
        if row.reason_code == "disease_unavailable_no_observable"
    ]
    assert len(notices) == 1
    assert notices[0].target_kind is ModelTargetKind.DISEASE_RISK
    assert not any(
        row.target_kind is ModelTargetKind.DISEASE_RISK for row in ledger.hypotheses
    )


def test_local_status_is_not_treated_as_truth() -> None:
    source = _production_hypothesis()
    assert source.status is not HypothesisStatus.SUPPORTED
    ledger = _derive(
        empty_scientific_model_ledger(_OWNER),
        _observation(0),
        experiment_ledger=_experiment_ledger(hypotheses=(source,)),
    )
    assert ledger.hypotheses[0].source_kind is ModelSourceKind.EXPERIMENT_HYPOTHESIS
    assert "confidence" not in {
        revision.reason.value for revision in ledger.hypotheses[0].revisions
    }


def test_causal_world_model_is_provenance_only() -> None:
    class _ForbiddenModel:
        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"read {name}")

    ledger = _derive(
        empty_scientific_model_ledger(_OWNER),
        _observation(0, season=Season.SPRING),
        causal_world_model=_ForbiddenModel(),
    )
    assert ledger.last_observation_key == "tick:0"
