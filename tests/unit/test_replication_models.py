# mypy: ignore-errors
"""V4-28 replication policy, design identity, lineage, and owner ledgers."""

from __future__ import annotations

import dataclasses

import pytest

from agents.cognition import (
    ExperimentDesign,
    ExperimentSelector,
    ReplicationAttempt,
    ReplicationAttemptState,
    ReplicationBindingMode,
    ReplicationConditionComparison,
    ReplicationError,
    ReplicationLedger,
    ReplicationMeasurement,
    ReplicationMeasurementBasis,
    ReplicationMeasurementResolution,
    ReplicationNoticeCode,
    ReplicationPolicy,
    ReplicationSelectorFamily,
    ReplicationUncertaintyKind,
    append_replication_design,
    build_experiment_design,
    build_replication_result_report,
    default_replication_policy,
    design_token_for,
    empty_replication_ledger,
    ingest_replication_report,
    record_replication_attempt,
    record_replication_measurement,
    replication_attempt_token,
    replication_ref,
    require_owner_replication_ledger,
    transition_replication_attempt,
)
from agents.cognition.experimentation import (
    HypothesisCondition,
    HypothesisConditionSlot,
)
from agents.models import AgentId
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)

pytestmark = pytest.mark.unit

OWNER = AgentId("owner-1")
OTHER = AgentId("owner-2")


def _selector(entity_id: str) -> ExperimentSelector:
    return ExperimentSelector(
        family=ReplicationSelectorFamily.ITEM,
        kind="tool",
        binding_mode=ReplicationBindingMode.EXACT,
        exact_entity_id=entity_id,
    )


def _design(
    *,
    trial: str = "event-1",
    parent: str | None = None,
    conditions: tuple[HypothesisCondition, ...] = (),
    origin: str | None = None,
) -> ExperimentDesign:
    return build_experiment_design(
        origin_token=origin or replication_ref("rorg", OWNER.value, trial),
        parent_design_token=parent,
        source_hypothesis_token=replication_ref("rhyp", OWNER.value, "hyp-1"),
        source_trial_token=replication_ref("rtrl", "body-1", trial),
        created_tick=4,
        operator=ExperimentOperator.APPLY_TOOL,
        process_token=ExperimentProcessToken.CRAFT,
        operand_a_selector=_selector("item-a"),
        operand_b_selector=None,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=conditions,
    )


def test_policy_is_locked_and_rejects_altered_defaults() -> None:
    policy = default_replication_policy()
    assert policy.version == "scientific-replication.v1"
    assert policy.max_designs == 32
    assert policy.max_attempts == 128
    assert policy.max_outbox_entries == 128
    assert policy.max_send_attempts == 3
    assert policy.max_result_reports == 256
    assert policy.max_interpretations == 256
    assert policy.max_delivery_receipts == 256
    assert policy.max_collaborations == 32
    assert policy.max_participants == 8
    assert policy.max_interpretation_revisions == 32
    with pytest.raises(ReplicationError):
        ReplicationPolicy(max_designs=True)  # type: ignore[arg-type]
    with pytest.raises(ReplicationError):
        ReplicationPolicy(version="scientific-replication.v2")
    with pytest.raises(ReplicationError):
        ReplicationPolicy(trust_threshold_high=float("nan"))


def test_selector_modes_are_closed_and_exact_ids_are_explicit() -> None:
    with pytest.raises(ReplicationError):
        ExperimentSelector(
            family=ReplicationSelectorFamily.ITEM,
            kind="tool",
            binding_mode=ReplicationBindingMode.EXACT,
        )
    with pytest.raises(ReplicationError):
        ExperimentSelector(
            family=ReplicationSelectorFamily.ITEM,
            kind="tool",
            binding_mode=ReplicationBindingMode.SAME_KIND,
            exact_entity_id="item-a",
        )
    with pytest.raises(ReplicationError):
        ExperimentSelector(
            family=ReplicationSelectorFamily.ITEM,
            kind="Tool",
            binding_mode=ReplicationBindingMode.SAME_KIND,
        )


def test_design_identity_is_stable_and_content_addressed() -> None:
    first = _design()
    again = _design()
    assert first == again
    assert first.design_token.startswith("rdes-")
    assert len(first.design_token) == len("rdes-") + 32
    assert first.design_token == design_token_for(first)


def test_condition_order_is_normalized_and_content_changes_identity() -> None:
    left = HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1")
    right = HypothesisCondition(HypothesisConditionSlot.WEATHER, "rain")
    ordered = _design(conditions=(left, right))
    reversed_order = _design(conditions=(right, left))
    assert ordered.conditions == reversed_order.conditions
    assert ordered.design_token == reversed_order.design_token
    changed = _design(conditions=(left,))
    assert changed.design_token != ordered.design_token


def test_parent_and_origin_are_part_of_identity() -> None:
    parent = _design(trial="event-0")
    child = _design(trial="event-1", parent=parent.design_token)
    other_origin = _design(
        trial="event-1", origin=replication_ref("rorg", "elsewhere")
    )
    assert child.parent_design_token == parent.design_token
    assert child.design_token != other_origin.design_token
    assert child.origin_token != other_origin.origin_token


def test_design_is_immutable() -> None:
    design = _design()
    with pytest.raises(dataclasses.FrozenInstanceError):
        design.created_tick = 9  # type: ignore[misc]


def test_ledger_is_owner_scoped_and_empty_by_default() -> None:
    ledger = empty_replication_ledger(OWNER)
    assert ledger.owner_id == OWNER
    assert ledger.designs == ()
    assert ledger.notices == ()
    assert require_owner_replication_ledger(ledger, OWNER) is ledger
    with pytest.raises(ReplicationError):
        require_owner_replication_ledger(ledger, OTHER)
    with pytest.raises(ReplicationError):
        require_owner_replication_ledger(object(), OWNER)


def test_unknown_parent_is_retained_as_an_opaque_notice() -> None:
    unknown = "rdes-" + "a" * 32
    design = _design(parent=unknown)
    ledger, reason = append_replication_design(empty_replication_ledger(OWNER), design)
    assert reason == "design_adopted"
    assert ReplicationNoticeCode.UNKNOWN_PARENT in ledger.notices


def test_self_parent_and_local_cycles_are_rejected() -> None:
    self_parent_token = "rdes-" + "a" * 32
    self_parent = ExperimentDesign(
        design_token=self_parent_token,
        origin_token=replication_ref("rorg", "self"),
        parent_design_token=self_parent_token,
        source_hypothesis_token=replication_ref("rhyp", "self"),
        source_trial_token=replication_ref("rtrl", "self"),
        created_tick=1,
        operator=ExperimentOperator.APPLY_TOOL,
        process_token=ExperimentProcessToken.CRAFT,
        operand_a_selector=_selector("item-a"),
        operand_b_selector=None,
        predicted_outcome=None,
    )
    ledger, reason = append_replication_design(
        empty_replication_ledger(OWNER), self_parent
    )
    assert ledger.designs == ()
    assert reason == "self_parent"

    token_a = "rdes-" + "b" * 32
    token_b = "rdes-" + "c" * 32
    first = dataclasses.replace(
        _design(), design_token=token_a, parent_design_token=token_b
    )
    second = dataclasses.replace(
        _design(trial="event-2"), design_token=token_b, parent_design_token=token_a
    )
    ledger, _ = append_replication_design(empty_replication_ledger(OWNER), first)
    ledger, reason = append_replication_design(ledger, second)
    assert reason == "design_cycle"
    assert len(ledger.designs) == 1


def test_design_capacity_rejects_new_rows_without_eviction() -> None:
    ledger = empty_replication_ledger(OWNER)
    for index in range(32):
        design = _design(trial=f"event-{index}")
        ledger, reason = append_replication_design(ledger, design)
        assert reason in {"design_adopted", "duplicate_design"}
    kept = ledger.designs[0]
    overflow = _design(trial="event-overflow")
    ledger, reason = append_replication_design(ledger, overflow)
    assert reason == "design_capacity"
    assert len(ledger.designs) == 32
    assert ledger.designs[0] == kept
    assert ReplicationNoticeCode.DESIGN_CAPACITY in ledger.notices


def _attempt(
    design: ExperimentDesign,
    *,
    state: ReplicationAttemptState = ReplicationAttemptState.PLANNED,
    request_tick: int = 5,
    resolution_event_id: str | None = None,
) -> ReplicationAttempt:
    return ReplicationAttempt(
        owner_id=OWNER,
        attempt_token=replication_attempt_token(
            OWNER, design.design_token, design.source_trial_token, request_tick
        ),
        design_token=design.design_token,
        source_trial_token=design.source_trial_token,
        actor_entity_id="body-1",
        hypothesis_id="hyp-1",
        request_tick=request_tick,
        state=state,
        resolution_event_id=resolution_event_id,
    )


def _ledger_with_design() -> tuple[ReplicationLedger, ExperimentDesign]:
    design = _design()
    ledger, _ = append_replication_design(
        empty_replication_ledger(OWNER), design
    )
    return ledger, design


def _measurement(
    outcome: ExperimentOutcomeClass | None = ExperimentOutcomeClass.SUCCESS,
    *,
    kind: ReplicationUncertaintyKind = ReplicationUncertaintyKind.UNREPORTED,
    possible: tuple[ExperimentOutcomeClass, ...] = (),
    basis: ReplicationMeasurementBasis = ReplicationMeasurementBasis.OWN_OBSERVATION,
) -> ReplicationMeasurement:
    return ReplicationMeasurement(
        resolution=ReplicationMeasurementResolution.OUTCOME_CLASS,
        uncertainty_kind=kind,
        basis=basis,
        outcome=outcome,
        possible_outcomes=possible,
    )


def test_attempt_lifecycle_is_forward_only_and_requires_a_resolution() -> None:
    ledger, design = _ledger_with_design()
    ledger, reason = record_replication_attempt(ledger, _attempt(design))
    assert reason == "source_result_missing"
    token = ledger.attempts[0].attempt_token
    ledger, reason = transition_replication_attempt(
        ledger, token, ReplicationAttemptState.PROPOSED, submission_tick=6
    )
    assert reason == "attempt_transitioned"
    assert ledger.attempts[0].submission_tick == 6
    ledger, reason = transition_replication_attempt(
        ledger, token, ReplicationAttemptState.OBSERVED
    )
    assert reason == "resolution_missing"
    assert ledger.attempts[0].state is ReplicationAttemptState.PROPOSED
    ledger, reason = transition_replication_attempt(
        ledger, token, ReplicationAttemptState.PROPOSED
    )
    assert reason == "attempt_unchanged"
    ledger, reason = transition_replication_attempt(
        ledger,
        token,
        ReplicationAttemptState.OBSERVED,
        resolution_event_id="event-resolved",
        condition_comparison=ReplicationConditionComparison.MATCHED,
    )
    assert reason == "attempt_transitioned"
    assert ledger.attempts[0].state is ReplicationAttemptState.OBSERVED
    ledger, reason = transition_replication_attempt(
        ledger, token, ReplicationAttemptState.PROPOSED
    )
    assert reason == "attempt_transition_rejected"
    assert ledger.attempts[0].state is ReplicationAttemptState.OBSERVED


def test_unknown_design_attempt_is_rejected_and_capacity_is_bounded() -> None:
    ledger = empty_replication_ledger(OWNER)
    missing = _design()
    ledger, reason = record_replication_attempt(ledger, _attempt(missing))
    assert reason == "unknown_design"
    assert ledger.attempts == ()


def test_rejected_and_cancelled_attempts_are_not_failure_results() -> None:
    ledger, design = _ledger_with_design()
    ledger, _ = record_replication_attempt(ledger, _attempt(design, request_tick=5))
    ledger, _ = record_replication_attempt(ledger, _attempt(design, request_tick=6))
    first, second = ledger.attempts
    ledger, reason = transition_replication_attempt(
        ledger, first.attempt_token, ReplicationAttemptState.CANCELLED
    )
    assert reason == "attempt_transitioned"
    ledger, reason = transition_replication_attempt(
        ledger,
        second.attempt_token,
        ReplicationAttemptState.PROPOSED,
        submission_tick=7,
    )
    assert reason == "attempt_transitioned"
    ledger, reason = transition_replication_attempt(
        ledger, second.attempt_token, ReplicationAttemptState.REJECTED
    )
    assert reason == "attempt_transitioned"
    states = {row.attempt_token: row.state for row in ledger.attempts}
    assert states[first.attempt_token] is ReplicationAttemptState.CANCELLED
    assert states[second.attempt_token] is ReplicationAttemptState.REJECTED
    assert ledger.reports == ()



def test_measurement_uncertainty_is_explicit_and_never_zero_error() -> None:
    unreported = _measurement()
    assert unreported.possible_outcomes == ()
    declared = _measurement(
        kind=ReplicationUncertaintyKind.DECLARED_SET,
        possible=(
            ExperimentOutcomeClass.FAILURE,
            ExperimentOutcomeClass.SUCCESS,
        ),
    )
    assert declared.possible_outcomes == (
        ExperimentOutcomeClass.FAILURE,
        ExperimentOutcomeClass.SUCCESS,
    )
    with pytest.raises(ReplicationError):
        _measurement(
            kind=ReplicationUncertaintyKind.DECLARED_SET,
            possible=(ExperimentOutcomeClass.FAILURE,),
        )
    with pytest.raises(ReplicationError):
        _measurement(
            kind=ReplicationUncertaintyKind.UNREPORTED,
            possible=(ExperimentOutcomeClass.SUCCESS,),
        )
    with pytest.raises(ReplicationError):
        _measurement(
            kind=ReplicationUncertaintyKind.DECLARED_SET,
            possible=(
                ExperimentOutcomeClass.SUCCESS,
                ExperimentOutcomeClass.SUCCESS,
            ),
        )


def test_all_five_outcomes_are_accepted() -> None:
    for outcome in ExperimentOutcomeClass:
        assert _measurement(outcome).outcome is outcome


def test_missing_outcome_is_unresolved_not_a_failure_result() -> None:
    ledger, design = _ledger_with_design()
    ledger, _ = record_replication_attempt(ledger, _attempt(design))
    token = ledger.attempts[0].attempt_token
    ledger, _ = transition_replication_attempt(
        ledger, token, ReplicationAttemptState.PROPOSED, submission_tick=6
    )
    ledger, reason = record_replication_measurement(
        ledger,
        token,
        measurement=_measurement(None),
        condition_comparison=ReplicationConditionComparison.MATCHED,
        resolution_event_id="event-resolved",
        performer_claim_token=replication_ref("rpart", OWNER.value, "body-1"),
    )
    assert reason == "attempt_transitioned"
    assert ledger.attempts[0].state is ReplicationAttemptState.UNRESOLVED
    assert ledger.reports == ()


def test_own_observation_creates_one_report_and_observed_attempt() -> None:
    ledger, design = _ledger_with_design()
    ledger, _ = record_replication_attempt(ledger, _attempt(design))
    token = ledger.attempts[0].attempt_token
    ledger, _ = transition_replication_attempt(
        ledger, token, ReplicationAttemptState.PROPOSED, submission_tick=6
    )
    ledger, reason = record_replication_measurement(
        ledger,
        token,
        measurement=_measurement(),
        condition_comparison=ReplicationConditionComparison.MATCHED,
        resolution_event_id="event-resolved",
        performer_claim_token=replication_ref("rpart", OWNER.value, "body-1"),
    )
    assert reason == "attempt_transitioned"
    assert ledger.attempts[0].state is ReplicationAttemptState.OBSERVED
    assert len(ledger.reports) == 1
    report = ledger.reports[0]
    assert report.measurement.basis is ReplicationMeasurementBasis.OWN_OBSERVATION
    assert report.delivery_event_id is None
    duplicate, reason = ingest_replication_report(ledger, report)
    assert reason == "duplicate_report"
    assert duplicate == ledger


def test_communicated_reports_require_a_delivery_reference_and_keep_origin() -> None:
    origin = replication_ref("rrep", "source", "trial")
    common = {
        "design_token": _design().design_token,
        "attempt_token": replication_ref("ratt", OWNER.value, "attempt"),
        "source_trial_token": _design().source_trial_token,
        "source_root_token": origin,
        "measurement": _measurement(
            basis=ReplicationMeasurementBasis.COMMUNICATED
        ),
        "declared_measurement_basis": ReplicationMeasurementBasis.COMMUNICATED,
        "performer_claim_token": replication_ref("rpart", "source", "body"),
        "origin_report_token": origin,
    }
    with pytest.raises(ReplicationError):
        build_replication_result_report(OWNER, **common)  # type: ignore[arg-type]
    success = build_replication_result_report(
        OWNER, delivery_event_id="delivery-1", **common  # type: ignore[arg-type]
    )
    failure_common = dict(common)
    failure_common["measurement"] = _measurement(
        ExperimentOutcomeClass.FAILURE,
        basis=ReplicationMeasurementBasis.COMMUNICATED,
    )
    failure = build_replication_result_report(
        OWNER, delivery_event_id="delivery-1", **failure_common  # type: ignore[arg-type]
    )
    assert success.origin_report_token == failure.origin_report_token
    assert success.report_token != failure.report_token
    ledger, reason = ingest_replication_report(
        empty_replication_ledger(OWNER), success
    )
    assert reason == "report_ingested"
    ledger, reason = ingest_replication_report(ledger, failure)
    assert reason == "report_ingested"
    assert len(ledger.reports) == 2
    assert ledger.reports[0].measurement.outcome is ExperimentOutcomeClass.SUCCESS
    assert ledger.reports[1].measurement.outcome is ExperimentOutcomeClass.FAILURE

