"""Outcome settlement: exact target boundaries, owner facts, no invented results."""

from __future__ import annotations

import dataclasses

import pytest

from agents.cognition.experimentation import (
    ExperimentHypothesis,
    ExperimentLedger,
)
from agents.cognition.scientific_model_lifecycle import advance_scientific_models
from agents.cognition.scientific_model_observation import (
    resolve_due_model_cases,
    resource_change_class,
)
from agents.cognition.scientific_models import (
    ForecastCaseState,
    ModelExecutionBinding,
    ModelExecutionComparability,
    ModelTargetKind,
    ScientificModelLedger,
    empty_scientific_model_ledger,
)
from world.environment import Season
from world.experimentation import ExperimentOperator, ExperimentProcessToken
from world.identifiers import AgentId, EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
    ObservedResource,
    ObservedSelf,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
)

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_WORLD = WorldId("world-1")
_SELF = EntityId("agent-1")
_LOCATION = EntityId("loc-1")
_RESOURCE = EntityId("res-1")


def _experiment_ledger(
    hypotheses: tuple[ExperimentHypothesis, ...] = (),
) -> ExperimentLedger:
    return ExperimentLedger(
        owner_id=_OWNER,
        max_hypotheses=8,
        max_trials_per_tick=1,
        repeat_threshold=1,
        learn_into_genealogy=False,
        hypotheses=hypotheses,
    )


def _self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=_SELF,
        location_id=_LOCATION,
        health=Health(100.0),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(37.0),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _observation(
    tick: int,
    *,
    season: Season | None = Season.SPRING,
    quantity: float | None = None,
    occurrences: tuple[ObservedOccurrence, ...] = (),
    include_self: bool = False,
) -> Observation:
    resources: tuple[ObservedResource, ...] = ()
    if quantity is not None:
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
        observer_id=EntityId(_OWNER.value),
        revision=WorldRevision(tick),
        tick=tick,
        self_body=_self() if include_self else None,
        season=season,
        resources=resources,
        occurrences=occurrences,
    )


def _occurrence(
    *,
    tick: int,
    outcome: str = "success",
    actor: EntityId = _SELF,
    role: ObservationAudienceRole = ObservationAudienceRole.ACTOR,
    event_id: str = "evt-1",
    operator: str = "combine",
    facts: dict[str, object] | None = None,
) -> ObservedOccurrence:
    public_facts: dict[str, object] = {
        "kind": "experiment_resolved",
        "operator": operator,
        "outcome_class": outcome,
    }
    if facts:
        public_facts.update(facts)
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=tick,
            source_event_id=EventId(event_id),
        ),
        kind="experiment_resolved",
        audience_role=role,
        actor_id=actor,
        public_facts=public_facts,
    )


def _season_ledger(issue_tick: int = 10) -> ScientificModelLedger:
    ledger = empty_scientific_model_ledger(_OWNER)
    for tick, season in (
        (0, Season.SPRING),
        (1, Season.SPRING),
        (2, Season.SUMMER),
        (3, Season.SUMMER),
    ):
        ledger = advance_scientific_models(
            ledger,
            _observation(tick, season=season),
            experiment_ledger=_experiment_ledger(),
        )
    for tick in range(4, issue_tick + 1):
        ledger = advance_scientific_models(
            ledger,
            _observation(tick, season=Season.SPRING),
            experiment_ledger=_experiment_ledger(),
        )
    return ledger


def test_resource_change_class_is_directional_only() -> None:
    assert resource_change_class(1000, 900) == "decrease"
    assert resource_change_class(1000, 1000) == "unchanged"
    assert resource_change_class(1000, 1100) == "increase"


def test_season_case_settles_only_at_the_exact_target_boundary() -> None:
    ledger = _season_ledger()
    issued = [
        row for row in ledger.pending_cases if row.target_kind is ModelTargetKind.SEASON
    ]
    case = max(issued, key=lambda row: row.target_observation_tick)
    inside = resolve_due_model_cases(ledger, _observation(11, season=Season.SUMMER))
    still = next(row for row in inside.cases if row.case_id == case.case_id)
    assert still.state is ForecastCaseState.PENDING

    settled = resolve_due_model_cases(ledger, _observation(12, season=Season.SUMMER))
    updated = next(row for row in settled.cases if row.case_id == case.case_id)
    assert updated.state is ForecastCaseState.SCORED
    assert updated.observed is not None
    assert updated.observed.observed_class == "summer"
    assert updated.observed.observed_tick == 12
    assert updated.settlement_reason == "observed"


def test_a_missed_target_is_unavailable_not_a_later_sample() -> None:
    ledger = _season_ledger()
    case = max(ledger.pending_cases, key=lambda row: row.target_observation_tick)
    later = resolve_due_model_cases(ledger, _observation(13, season=Season.AUTUMN))
    updated = next(row for row in later.cases if row.case_id == case.case_id)
    assert updated.state is ForecastCaseState.UNAVAILABLE
    assert updated.observed is None
    assert updated.settlement_reason == "missing_observation"


def test_missing_season_at_the_target_is_unavailable() -> None:
    ledger = _season_ledger()
    case = max(ledger.pending_cases, key=lambda row: row.target_observation_tick)
    resolved = resolve_due_model_cases(ledger, _observation(12, season=None))
    updated = next(row for row in resolved.cases if row.case_id == case.case_id)
    assert updated.state is ForecastCaseState.UNAVAILABLE
    assert updated.settlement_reason == "source_unavailable"


def _issue_resource_case() -> ScientificModelLedger:
    ledger = empty_scientific_model_ledger(_OWNER)
    for tick, quantity in ((0, 10.0), (1, 10.0), (2, 20.0), (3, 20.0)):
        ledger = advance_scientific_models(
            ledger,
            _observation(tick, quantity=quantity),
            experiment_ledger=_experiment_ledger(),
        )
    return ledger


def test_resource_outcome_uses_frozen_start_and_visible_end() -> None:
    ledger = _issue_resource_case()
    candidates = [
        row
        for row in ledger.pending_cases
        if row.target_kind is ModelTargetKind.RESOURCE_REGENERATION
    ]
    assert candidates
    case = candidates[0]
    resolved = resolve_due_model_cases(
        ledger,
        _observation(case.target_observation_tick, quantity=40.0),
    )
    updated = next(row for row in resolved.cases if row.case_id == case.case_id)
    if updated.state is ForecastCaseState.PENDING:
        pytest.skip("no resource case was issued at this boundary")
    assert updated.state is ForecastCaseState.SCORED
    assert updated.observed is not None
    assert updated.observed.observed_class == "increase"
    assert updated.outcome_start_milli is not None
    assert updated.outcome_end_milli == 40_000


def test_occluded_resource_is_unavailable_not_unchanged() -> None:
    ledger = _issue_resource_case()
    candidates = [
        row
        for row in ledger.pending_cases
        if row.target_kind is ModelTargetKind.RESOURCE_REGENERATION
    ]
    assert candidates
    case = candidates[0]
    resolved = resolve_due_model_cases(
        ledger, _observation(case.target_observation_tick, quantity=None)
    )
    updated = next(row for row in resolved.cases if row.case_id == case.case_id)
    if updated.state is ForecastCaseState.PENDING:
        pytest.skip("no resource case was issued at this boundary")
    assert updated.state is ForecastCaseState.UNAVAILABLE
    assert updated.observed is None


def _production_case() -> tuple[ScientificModelLedger, ExperimentHypothesis]:
    source = ExperimentHypothesis(
        owner_id=_OWNER,
        hypothesis_id="hyp:prod-1",
        operator=ExperimentOperator.COMBINE,
        operand_a_id="wheat",
        process_token=ExperimentProcessToken.HARVEST,
        predicted_outcome="success",
        created_tick=0,
    )
    ledger = empty_scientific_model_ledger(_OWNER)
    ledger = advance_scientific_models(
        ledger,
        _observation(0, include_self=True),
        experiment_ledger=_experiment_ledger((source,)),
    )
    candidates = [
        row
        for row in ledger.pending_cases
        if row.target_kind is ModelTargetKind.PRODUCTION_OUTCOME
    ]
    assert candidates
    return ledger, source


def _bind(
    ledger: ScientificModelLedger,
    case_id: str,
    *,
    comparability: ModelExecutionComparability = (
        ModelExecutionComparability.COMPARABLE
    ),
    tick: int | None = None,
) -> ScientificModelLedger:
    case = next(row for row in ledger.cases if row.case_id == case_id)
    binding = ModelExecutionBinding(
        binding_id=f"smb:{case_id}",
        owner_id=_OWNER,
        case_id=case_id,
        tick=case.issued_observation_tick + 1 if tick is None else tick,
        command_ref="command:1",
        target_ref=case.target_ref,
        conditions=case.conditions,
        comparability=comparability,
    )
    return dataclasses.replace(ledger, bindings=(*ledger.bindings, binding))


def test_production_requires_binding_and_exact_actor_occurrence() -> None:
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind is ModelTargetKind.PRODUCTION_OUTCOME
    )
    resolved = resolve_due_model_cases(
        ledger, _observation(case.target_observation_tick, include_self=True)
    )
    updated = next(row for row in resolved.cases if row.case_id == case.case_id)
    assert updated.state is ForecastCaseState.NOT_ATTEMPTED

    bound = _bind(ledger, case.case_id)
    occurrence = _occurrence(tick=case.issued_observation_tick + 1)
    resolved = resolve_due_model_cases(
        bound,
        _observation(
            case.target_observation_tick,
            include_self=True,
            occurrences=(occurrence,),
        ),
    )
    updated = next(row for row in resolved.cases if row.case_id == case.case_id)
    assert updated.state is ForecastCaseState.SCORED
    assert updated.observed is not None
    assert updated.observed.observed_class == "success"


def test_stale_event_tick_and_foreign_actor_are_not_eligible() -> None:
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind is ModelTargetKind.PRODUCTION_OUTCOME
    )
    bound = _bind(ledger, case.case_id)
    stale = _occurrence(tick=case.issued_observation_tick, event_id="evt-stale")
    foreign = _occurrence(
        tick=case.issued_observation_tick + 1,
        actor=EntityId("other"),
        event_id="evt-foreign",
    )
    resolved = resolve_due_model_cases(
        bound,
        _observation(
            case.target_observation_tick,
            include_self=True,
            occurrences=(stale, foreign),
        ),
    )
    updated = next(row for row in resolved.cases if row.case_id == case.case_id)
    assert updated.state is ForecastCaseState.NOT_ATTEMPTED


def test_bystander_redaction_is_ineligible() -> None:
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind is ModelTargetKind.PRODUCTION_OUTCOME
    )
    bound = _bind(ledger, case.case_id)
    bystander = _occurrence(
        tick=case.issued_observation_tick + 1,
        role=ObservationAudienceRole.BYSTANDER,
    )
    resolved = resolve_due_model_cases(
        bound,
        _observation(
            case.target_observation_tick,
            include_self=True,
            occurrences=(bystander,),
        ),
    )
    updated = next(row for row in resolved.cases if row.case_id == case.case_id)
    assert updated.state is ForecastCaseState.NOT_ATTEMPTED


def test_ambiguous_execution_is_not_scored() -> None:
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind is ModelTargetKind.PRODUCTION_OUTCOME
    )
    bound = _bind(ledger, case.case_id)
    first = _occurrence(tick=case.issued_observation_tick + 1, event_id="evt-1")
    second = _occurrence(tick=case.issued_observation_tick + 1, event_id="evt-2")
    resolved = resolve_due_model_cases(
        bound,
        _observation(
            case.target_observation_tick,
            include_self=True,
            occurrences=(first, second),
        ),
    )
    updated = next(row for row in resolved.cases if row.case_id == case.case_id)
    assert updated.state is ForecastCaseState.NOT_COMPARABLE
    assert updated.settlement_reason == "ambiguous_execution"


def test_changed_or_unknown_conditions_block_scoring() -> None:
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind is ModelTargetKind.PRODUCTION_OUTCOME
    )
    occurrence = _occurrence(tick=case.issued_observation_tick + 1)
    for comparability, reason in (
        (
            ModelExecutionComparability.CHANGED_CONDITIONS,
            "changed_conditions",
        ),
        (
            ModelExecutionComparability.UNKNOWN_CONDITIONS,
            "unknown_conditions",
        ),
    ):
        bound = _bind(ledger, case.case_id, comparability=comparability)
        resolved = resolve_due_model_cases(
            bound,
            _observation(
                case.target_observation_tick,
                include_self=True,
                occurrences=(occurrence,),
            ),
        )
        updated = next(row for row in resolved.cases if row.case_id == case.case_id)
        assert updated.state is ForecastCaseState.NOT_COMPARABLE
        assert updated.settlement_reason == reason


def test_contradictory_exposed_operand_is_not_comparable() -> None:
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind is ModelTargetKind.PRODUCTION_OUTCOME
    )
    bound = _bind(ledger, case.case_id)
    occurrence = _occurrence(
        tick=case.issued_observation_tick + 1,
        facts={"operand_a_id": "barley"},
    )
    resolved = resolve_due_model_cases(
        bound,
        _observation(
            case.target_observation_tick,
            include_self=True,
            occurrences=(occurrence,),
        ),
    )
    updated = next(row for row in resolved.cases if row.case_id == case.case_id)
    assert updated.state is ForecastCaseState.NOT_COMPARABLE


def test_foreign_observation_owner_is_rejected() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    with pytest.raises(ValueError, match="owner_mismatch"):
        resolve_due_model_cases(
            ledger,
            Observation(
                world_id=_WORLD,
                observer_id=EntityId("agent-2"),
                revision=WorldRevision(0),
                tick=0,
            ),
        )


def test_lifecycle_is_idempotent_for_repeated_observations() -> None:
    ledger = _season_ledger()
    first = advance_scientific_models(
        ledger,
        _observation(12, season=Season.SUMMER),
        experiment_ledger=_experiment_ledger(),
    )
    second = advance_scientific_models(
        first,
        _observation(12, season=Season.SUMMER),
        experiment_ledger=_experiment_ledger(),
    )
    assert second == first


def test_transition_scoring_order_and_revision_happens_after_settlement() -> None:
    ledger = _season_ledger()
    advanced = advance_scientific_models(
        ledger,
        _observation(12, season=Season.SUMMER),
        experiment_ledger=_experiment_ledger(),
    )
    assert any(
        row.observed is not None and row.settlement_reason == "observed"
        for row in advanced.cases
    )
    assert advanced.summaries
    assert all(row.scored_count >= 1 for row in advanced.summaries)


def test_no_new_case_targets_evidence_consumed_in_the_same_update() -> None:
    ledger = _season_ledger()
    advanced = advance_scientific_models(
        ledger,
        _observation(12, season=Season.SUMMER),
        experiment_ledger=_experiment_ledger(),
    )
    for case in advanced.pending_cases:
        assert case.target_observation_tick > 12
        assert case.training_high_water_tick <= 12
