# mypy: ignore-errors
"""V4-28 receiver-owned replication compiles to one ordinary Experiment."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    ExperimentSelector,
    ReplicationAttemptState,
    ReplicationBindingMode,
    ReplicationCollaboration,
    ReplicationInvitationStatus,
    ReplicationLedger,
    ReplicationOwnerContext,
    ReplicationSelectorFamily,
    adopt_replication_design,
    build_experiment_design,
    compile_replication_test,
    empty_experiment_ledger,
    empty_replication_ledger,
    open_replication_collaboration,
    replication_local_hypothesis_id,
    replication_ref,
    request_replication,
)
from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    experiment_hypothesis_id,
    formulate_hypothesis,
)
from agents.models import AgentId
from world.actions import Experiment
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import EntityId
from world.values import ItemKind

pytestmark = pytest.mark.unit

A = "body-a"
B = "body-b"
OWNER_A = AgentId("owner-a")
OWNER_B = AgentId("owner-b")


def _binding(**overrides: object) -> ExperimentCognitionBinding:
    payload: dict[str, object] = {
        "max_hypotheses": 2,
        "max_trials_per_tick": 1,
        "repeat_threshold": 2,
        "learn_into_genealogy": False,
        "allow_provider": False,
    }
    payload.update(overrides)
    return ExperimentCognitionBinding(**payload)  # type: ignore[arg-type]


def _design(*, parent: str | None = None, trial: str = "source-trial") -> object:
    return build_experiment_design(
        origin_token=replication_ref("rorg", OWNER_A.value, trial),
        parent_design_token=parent,
        source_hypothesis_token=replication_ref("rhyp", OWNER_A.value, "hyp"),
        source_trial_token=replication_ref("rtrl", A, trial),
        created_tick=3,
        operator=ExperimentOperator.APPLY_TOOL,
        process_token=ExperimentProcessToken.CRAFT,
        operand_a_selector=ExperimentSelector(
            family=ReplicationSelectorFamily.ITEM,
            kind="tool",
            binding_mode=ReplicationBindingMode.SAME_KIND,
        ),
        operand_b_selector=None,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(),
    )


def _observation(*, item: str | None = "tool-b", tick: int = 5) -> SimpleNamespace:
    items = (
        ()
        if item is None
        else (
            SimpleNamespace(
                entity_id=EntityId(item),
                kind=ItemKind.TOOL,
                placement=SimpleNamespace(value="held_by_self"),
            ),
        )
    )
    return SimpleNamespace(
        observer_id=EntityId(B),
        self_body=SimpleNamespace(entity_id=EntityId(B)),
        tick=tick,
        items=items,
        resources=(),
        structures=(),
        artifacts=(),
        occurrences=(),
        communications=(),
    )


def _receiver(design: object) -> tuple[ReplicationLedger, object]:
    ledger = empty_replication_ledger(OWNER_B)
    ledger, reason = adopt_replication_design(
        OWNER_B,
        ledger,
        design,  # type: ignore[arg-type]
        delivery_event_id="design-delivery",
        received_tick=4,
        inviter_entity_id=A,
    )
    assert reason == "design_adopted"
    collaboration = ReplicationCollaboration(
        owner_id=OWNER_B,
        invitation_token=replication_ref("rinv", OWNER_B.value, "invite"),
        design_token=design.design_token,  # type: ignore[attr-defined]
        source_trial_token=design.source_trial_token,  # type: ignore[attr-defined]
        inviter_entity_id=A,
        created_tick=4,
        delivery_event_id="invite-delivery",
    )
    ledger, reason = open_replication_collaboration(ledger, collaboration)
    assert reason == "collaboration_opened"
    return ledger, collaboration


def test_receiver_repeats_with_its_own_tool_and_one_ordinary_command() -> None:
    design = _design()
    ledger, _collaboration = _receiver(design)
    experiment_ledger = empty_experiment_ledger(OWNER_B, _binding())
    compiled = compile_replication_test(
        OWNER_B,
        ledger,
        experiment_ledger,
        _observation(),
        source_context=ReplicationOwnerContext(),
    )
    assert compiled.reason is None
    assert type(compiled.command) is Experiment
    assert compiled.command.operand_a_id == EntityId("tool-b")
    assert compiled.command.operand_a_id != EntityId("item-a")
    assert compiled.attempt_token is not None
    attempt = compiled.replication_ledger.attempts[0]
    assert attempt.state is ReplicationAttemptState.PROPOSED
    assert attempt.hypothesis_id.startswith("rpl:")
    assert (
        compiled.replication_ledger.collaborations[0].status
        is ReplicationInvitationStatus.ACCEPTED
    )
    assert any(
        entry.message_kind == "participate"
        for entry in compiled.replication_ledger.outbox
    )
    hypothesis = compiled.experiment_ledger.hypotheses[0]
    assert hypothesis.hypothesis_id == attempt.hypothesis_id
    assert hypothesis.confidence_milli == 500
    assert hypothesis.support == 0


def test_one_attempt_per_invitation_and_shared_trial_cap() -> None:
    design = _design()
    ledger, _collaboration = _receiver(design)
    experiment_ledger = empty_experiment_ledger(OWNER_B, _binding())
    compiled = compile_replication_test(
        OWNER_B, ledger, experiment_ledger, _observation()
    )
    assert compiled.command is not None
    again = compile_replication_test(
        OWNER_B,
        compiled.replication_ledger,
        compiled.experiment_ledger,
        _observation(tick=6),
    )
    assert again.command is None
    assert again.reason == "no_replication_request"


def test_condition_mismatch_and_missing_operand_skip_without_failure() -> None:
    from agents.cognition.experimentation import (
        HypothesisCondition,
        HypothesisConditionSlot,
    )

    design = _design()
    design_with_condition = build_experiment_design(
        origin_token=design.origin_token,  # type: ignore[attr-defined]
        parent_design_token=None,
        source_hypothesis_token=design.source_hypothesis_token,  # type: ignore[attr-defined]
        source_trial_token=design.source_trial_token,  # type: ignore[attr-defined]
        created_tick=3,
        operator=design.operator,  # type: ignore[attr-defined]
        process_token=design.process_token,  # type: ignore[attr-defined]
        operand_a_selector=design.operand_a_selector,  # type: ignore[attr-defined]
        operand_b_selector=None,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(HypothesisCondition(HypothesisConditionSlot.WEATHER, "rain"),),
    )
    ledger, _ = _receiver(design_with_condition)
    compiled = compile_replication_test(
        OWNER_B,
        ledger,
        empty_experiment_ledger(OWNER_B, _binding()),
        _observation(),
    )
    assert compiled.command is None
    assert compiled.replication_ledger.attempts == ()

    ledger, _ = _receiver(_design(trial="missing-operand"))
    compiled = compile_replication_test(
        OWNER_B,
        ledger,
        empty_experiment_ledger(OWNER_B, _binding()),
        _observation(item=None),
    )
    assert compiled.command is None
    assert compiled.replication_ledger.attempts == ()


def test_contested_source_is_not_automatically_recruited() -> None:
    ledger, _collaboration = _receiver(_design())
    compiled = compile_replication_test(
        OWNER_B,
        ledger,
        empty_experiment_ledger(OWNER_B, _binding()),
        _observation(),
        source_context=ReplicationOwnerContext(
            trust_by_entity=((A, 0.0),)
        ),
    )
    assert compiled.command is None
    assert (
        compiled.replication_ledger.collaborations[0].status
        is ReplicationInvitationStatus.PENDING
    )


def test_explicit_request_allows_a_delivered_design_without_invitation() -> None:
    design = _design()
    ledger = empty_replication_ledger(OWNER_B)
    ledger, _ = adopt_replication_design(
        OWNER_B,
        ledger,
        design,  # type: ignore[arg-type]
        delivery_event_id="design-delivery",
        received_tick=4,
        inviter_entity_id=A,
    )
    ledger, reason = request_replication(
        ledger,
        design.design_token,  # type: ignore[attr-defined]
        actor_entity_id=B,
        tick=4,
    )
    assert reason == "request_recorded"
    compiled = compile_replication_test(
        OWNER_B,
        ledger,
        empty_experiment_ledger(OWNER_B, _binding()),
        _observation(),
    )
    assert compiled.command is not None


def test_capacity_rejection_leaves_no_orphan_attempt_or_hypothesis() -> None:
    design = _design()
    ledger, _ = _receiver(design)
    existing = formulate_hypothesis(
        owner_id=OWNER_B,
        hypothesis_id=experiment_hypothesis_id(
            OWNER_B,
            ExperimentOperator.COMBINE,
            "x",
            "y",
            ExperimentProcessToken.NONE,
        ),
        operator=ExperimentOperator.COMBINE,
        operand_a_id="x",
        operand_b_id="y",
        process_token=ExperimentProcessToken.NONE,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        created_tick=1,
    )
    from agents.cognition.experimentation import admit_hypothesis

    experiment_ledger = empty_experiment_ledger(OWNER_B, _binding(max_hypotheses=1))
    experiment_ledger = admit_hypothesis(experiment_ledger, existing)
    from dataclasses import replace

    from agents.cognition.replication import ReplicationAttempt, ReplicationAttemptState

    pending = ReplicationAttempt(
        owner_id=OWNER_B,
        attempt_token=replication_ref("ratt", OWNER_B.value, "pending"),
        design_token=design.design_token,  # type: ignore[attr-defined]
        source_trial_token=design.source_trial_token,  # type: ignore[attr-defined]
        actor_entity_id=B,
        hypothesis_id=existing.hypothesis_id,
        request_tick=4,
        state=ReplicationAttemptState.PROPOSED,
        resolution_event_id=None,
    )
    protected = replace(ledger, attempts=(pending,))
    compiled = compile_replication_test(
        OWNER_B,
        protected,
        experiment_ledger,
        _observation(),
    )
    assert compiled.command is None
    assert compiled.reason == "replication_hypothesis_capacity"
    assert compiled.replication_ledger.attempts == (pending,)
    assert compiled.experiment_ledger.hypotheses == (existing,)


def test_two_designs_do_not_conflate_local_hypothesis_identity() -> None:
    first = _design(trial="trial-1")
    second = _design(trial="trial-2")
    assert first.design_token != second.design_token
    first_id = replication_local_hypothesis_id(
        OWNER_B, first, "tool-b", None  # type: ignore[arg-type]
    )
    second_id = replication_local_hypothesis_id(
        OWNER_B, second, "tool-b", None  # type: ignore[arg-type]
    )
    assert first_id != second_id
    assert len(first_id) <= 64


def test_actor_visible_result_correlates_exactly_once_to_the_local_attempt() -> None:
    from agents.cognition.replication_actions import correlate_replication_occurrences

    design = _design()
    ledger, _collaboration = _receiver(design)
    experiment_ledger = empty_experiment_ledger(OWNER_B, _binding())
    compiled = compile_replication_test(
        OWNER_B, ledger, experiment_ledger, _observation()
    )
    assert compiled.command is not None
    occurrence = SimpleNamespace(
        kind="experiment_resolved",
        actor_id=EntityId(B),
        other_entity_id=EntityId("tool-b"),
        public_facts={
            "operator": ExperimentOperator.APPLY_TOOL.value,
            "outcome_class": ExperimentOutcomeClass.SUCCESS.value,
        },
        provenance=SimpleNamespace(
            source_tick=5, source_event_id=SimpleNamespace(value="event-result")
        ),
    )
    observation = _observation(tick=6)
    observation.occurrences = (occurrence,)
    replication_ledger, experiment_ledger = correlate_replication_occurrences(
        OWNER_B,
        compiled.replication_ledger,
        compiled.experiment_ledger,
        observation,
    )
    attempt = replication_ledger.attempts[0]
    assert attempt.state is ReplicationAttemptState.OBSERVED
    assert len(replication_ledger.reports) == 1
    assert replication_ledger.reports[0].measurement.outcome is (
        ExperimentOutcomeClass.SUCCESS
    )
    hypothesis = next(
        row
        for row in experiment_ledger.hypotheses
        if row.hypothesis_id == attempt.hypothesis_id
    )
    assert hypothesis.support == 1
    assert hypothesis.counter == 0
    assert any(
        trial.event_id == "event-result" for trial in experiment_ledger.trials
    )

    again = correlate_replication_occurrences(
        OWNER_B,
        replication_ledger,
        experiment_ledger,
        observation,
    )
    assert len(again[0].reports) == 1
    assert len(again[1].trials) == len(experiment_ledger.trials)


def test_original_test_draft_freezes_only_after_the_visible_result() -> None:
    from agents.cognition.replication_designs import (
        freeze_source_design_from_draft,
        source_draft_for_hypothesis,
    )

    operator = ExperimentOperator.APPLY_TOOL
    hypothesis = formulate_hypothesis(
        owner_id=OWNER_B,
        hypothesis_id=experiment_hypothesis_id(
            OWNER_B, operator, "tool-b", None, ExperimentProcessToken.CRAFT
        ),
        operator=operator,
        operand_a_id="tool-b",
        process_token=ExperimentProcessToken.CRAFT,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(),
        created_tick=5,
    )
    draft = source_draft_for_hypothesis(OWNER_B, hypothesis, _observation())
    assert draft is not None
    from agents.cognition.experimentation import ExperimentTrial

    trial = ExperimentTrial(
        tick=6,
        event_id="source-result",
        outcome_class=ExperimentOutcomeClass.SUCCESS.value,
        discovery_mode="deliberate",
    )
    frozen = freeze_source_design_from_draft(draft, trial)
    assert frozen.design is not None
    assert frozen.design.source_trial_token.startswith("rtrl-")
    assert frozen.design.operand_a_selector.kind == "tool"
