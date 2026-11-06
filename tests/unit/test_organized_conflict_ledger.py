# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from agents.cognition.organized_conflict import (
    ConflictBasis,
    ConflictContradiction,
    ConflictContradictionKind,
    ConflictInterpretation,
    ConflictInterpretationKind,
    ConflictLedger,
    ConflictObservation,
    ConflictObservationKind,
    ConflictOutcome,
    ConflictOutcomeKind,
    ConflictParticipation,
    ConflictParticipationStance,
    ConflictPlan,
    ConflictPlanStatus,
    ConflictProvenance,
    ConflictRole,
    ConflictTargetKind,
    ConflictTermination,
    ConflictTerminationKind,
    OrganizedConflictCapacityError,
    OrganizedConflictError,
    conflict_contradiction_id,
    conflict_episode_id,
    conflict_interpretation_id,
    conflict_observation_id,
    conflict_outcome_id,
    conflict_participation_id,
    conflict_plan_id,
    conflict_termination_id,
    default_organized_conflict_policy,
    empty_organized_conflict_ledger,
    enforce_organized_conflict_limits,
    export_organized_conflict_ledger,
    organized_conflict_ledger_digest,
)
from agents.cognition.organized_conflict import (
    ConflictOperation as ConflictOperationValue,
)
from agents.models import AgentId

OWNER = AgentId("agent-owner")
OTHER = AgentId("agent-other")
REF = "a" * 16
REF2 = "b" * 16


def _plan(
    tick: int = 1, *, status: ConflictPlanStatus = ConflictPlanStatus.ACTIVE
) -> ConflictPlan:
    return ConflictPlan(
        plan_id=conflict_plan_id(
            OWNER,
            ConflictOperationValue.COORDINATED_ATTACK,
            ConflictTargetKind.AGENT,
            REF,
            tick,
            (REF,),
        ),
        operation=ConflictOperationValue.COORDINATED_ATTACK,
        target_kind=ConflictTargetKind.AGENT,
        target_ref=REF,
        role=ConflictRole.ATTACKER,
        side_ref=REF,
        participant_refs=(REF,),
        start_tick=tick,
        status=status,
        provenance=ConflictProvenance.SELF_DECLARED,
        last_tick=tick,
    )


def _interpretation(plan_id: str, tick: int = 1) -> ConflictInterpretation:
    return ConflictInterpretation(
        interpretation_id=conflict_interpretation_id(
            OWNER,
            None,
            ConflictInterpretationKind.COORDINATED_CONFLICT,
            tick,
            ConflictBasis.OBSERVED,
        ),
        episode_ref=None,
        kind=ConflictInterpretationKind.COORDINATED_CONFLICT,
        basis=ConflictBasis.OBSERVED,
        confidence_band="mid",
        tick=tick,
    )


def test_rows_are_frozen_and_typed() -> None:
    plan = _plan()
    with pytest.raises(FrozenInstanceError):
        plan.status = ConflictPlanStatus.EXPIRED  # type: ignore[misc]
    with pytest.raises(TypeError):
        ConflictPlan(
            plan_id=plan.plan_id,
            operation="coordinated_attack",  # type: ignore[arg-type]
            target_kind=ConflictTargetKind.AGENT,
            target_ref=REF,
            role=ConflictRole.ATTACKER,
            side_ref=REF,
        )
    with pytest.raises(TypeError):
        ConflictObservation(
            observation_id=conflict_observation_id(
                OWNER, REF, ConflictObservationKind.ATTACK, 1
            ),
            event_class="attack",  # type: ignore[arg-type]
            actor_ref=REF,
            other_ref=None,
            tick=1,
            source_event_token=REF,
        )


def test_contradiction_requires_two_members() -> None:
    plan = _plan()
    with pytest.raises(ValueError):
        ConflictContradiction(
            contradiction_id=conflict_contradiction_id(
                OWNER, ConflictContradictionKind.DUPLICATE_PLAN, 1, (plan.plan_id,)
            ),
            member_ids=(plan.plan_id,),
            kind=ConflictContradictionKind.DUPLICATE_PLAN,
            tick=1,
        )
    row = ConflictContradiction(
        contradiction_id=conflict_contradiction_id(
            OWNER, ConflictContradictionKind.DUPLICATE_PLAN, 1, (plan.plan_id,)
        ),
        member_ids=(plan.plan_id, plan.plan_id),
        kind=ConflictContradictionKind.DUPLICATE_PLAN,
        tick=1,
    )
    assert row.status == "unresolved"


def test_forbidden_war_fields_are_rejected() -> None:
    from agents.cognition.organized_conflict import assert_conflict_no_forbidden_fields

    with pytest.raises(OrganizedConflictError):
        assert_conflict_no_forbidden_fields({"plan_id": "x", "war_score": 1})
    with pytest.raises(OrganizedConflictError):
        assert_conflict_no_forbidden_fields({"plan_id": "x", "winner": "a"})


def test_opaque_refs_are_bounded() -> None:
    with pytest.raises(TypeError):
        ConflictPlan(
            plan_id=_plan().plan_id,
            operation=ConflictOperationValue.COORDINATED_ATTACK,
            target_kind=ConflictTargetKind.AGENT,
            target_ref="free text with spaces",
            role=ConflictRole.ATTACKER,
            side_ref=REF,
        )
    with pytest.raises((TypeError, ValueError)):
        ConflictPlan(
            plan_id=_plan().plan_id,
            operation=ConflictOperationValue.COORDINATED_ATTACK,
            target_kind=ConflictTargetKind.AGENT,
            target_ref=REF,
            role=ConflictRole.ATTACKER,
            side_ref=REF,
            participant_refs=tuple([REF] * 17),
        )


def test_ids_are_stable_and_content_addressed() -> None:
    first = conflict_plan_id(
        OWNER,
        ConflictOperationValue.COORDINATED_ATTACK,
        ConflictTargetKind.AGENT,
        REF,
        1,
        (REF,),
    )
    second = conflict_plan_id(
        OWNER,
        ConflictOperationValue.COORDINATED_ATTACK,
        ConflictTargetKind.AGENT,
        REF,
        1,
        (REF,),
    )
    other = conflict_plan_id(
        OTHER,
        ConflictOperationValue.COORDINATED_ATTACK,
        ConflictTargetKind.AGENT,
        REF,
        1,
        (REF,),
    )
    assert first == second != other
    assert len(first) == len("ocp-") + 16
    assert conflict_observation_id(
        OWNER, REF, ConflictObservationKind.ATTACK, 1
    ) == conflict_observation_id(OWNER, REF, ConflictObservationKind.ATTACK, 1)
    assert len(conflict_episode_id(OWNER, 1, (REF,), ("attack",))) == len("oce-") + 16


def _ledger(tick: int = 5) -> ConflictLedger:
    plan = _plan(tick=1)
    interpretation = _interpretation(plan.plan_id)
    participation = ConflictParticipation(
        participation_id=conflict_participation_id(
            plan.plan_id, REF, ConflictParticipationStance.JOIN, 1
        ),
        plan_id=plan.plan_id,
        participant_ref=REF,
        role=ConflictRole.ATTACKER,
        stance=ConflictParticipationStance.JOIN,
        provenance=ConflictProvenance.SELF_DECLARED,
        tick=1,
    )
    outcome = ConflictOutcome(
        outcome_id=conflict_outcome_id(plan.plan_id, ConflictOutcomeKind.HIT, REF, 2),
        plan_id=plan.plan_id,
        kind=ConflictOutcomeKind.HIT,
        target_ref=REF,
        tick=2,
    )
    termination = ConflictTermination(
        termination_id=conflict_termination_id(
            plan.plan_id, ConflictTerminationKind.EXPIRED, 3
        ),
        plan_id=plan.plan_id,
        kind=ConflictTerminationKind.EXPIRED,
        tick=3,
    )
    return ConflictLedger(
        owner_id=OWNER,
        tick=tick,
        revision=1,
        plans=(plan,),
        participations=(participation,),
        interpretations=(interpretation,),
        outcomes=(outcome,),
        terminations=(termination,),
    )


def test_ledger_rejects_foreign_references() -> None:
    ledger = _ledger()
    bad_plan_id = "ocp-" + "f" * 16
    with pytest.raises(ValueError, match="conflict_foreign_reference"):
        replace(
            ledger,
            participations=(replace(ledger.participations[0], plan_id=bad_plan_id),),
        )


def test_ledger_requires_sorted_unique_rows() -> None:
    plan = _plan()
    with pytest.raises(ValueError, match="conflict_duplicate_id"):
        ConflictLedger(owner_id=OWNER, plans=(plan, plan))
    with pytest.raises(TypeError):
        ConflictLedger(owner_id="agent-owner")  # type: ignore[arg-type]


def test_digest_changes_with_any_row() -> None:
    ledger = _ledger()
    baseline = organized_conflict_ledger_digest(ledger)
    assert baseline == organized_conflict_ledger_digest(ledger)
    changed = replace(ledger, notices=("organized_conflict_truncated:observations",))
    assert organized_conflict_ledger_digest(changed) != baseline


def test_empty_ledger_is_owner_scoped() -> None:
    ledger = empty_organized_conflict_ledger(OWNER, tick=0)
    assert ledger.owner_id == OWNER
    assert ledger.plans == ()
    assert ledger.revision == 0


def test_caps_prune_observations_first() -> None:
    policy = default_organized_conflict_policy()
    observations = tuple(
        sorted(
            (
                ConflictObservation(
                    observation_id=conflict_observation_id(
                        OWNER, f"{index:016x}", ConflictObservationKind.ATTACK, index
                    ),
                    event_class=ConflictObservationKind.ATTACK,
                    actor_ref=REF,
                    other_ref=REF2,
                    tick=index,
                    source_event_token=f"{index:016x}",
                )
                for index in range(policy.max_observations + 5)
            ),
            key=lambda row: row.observation_id,
        )
    )
    ledger = ConflictLedger(
        owner_id=OWNER, tick=policy.plan_ttl_ticks, observations=observations
    )
    pruned = enforce_organized_conflict_limits(ledger, policy)
    assert len(pruned.observations) == policy.max_observations
    assert "organized_conflict_truncated:observations" in pruned.notices


def test_hard_cap_fails_closed() -> None:
    from agents.cognition.organized_conflict import ConflictEpisode

    policy = default_organized_conflict_policy()
    episodes = tuple(
        sorted(
            (
                ConflictEpisode(
                    episode_id=conflict_episode_id(OWNER, index, (REF,), ("attack",)),
                    start_tick=index,
                    end_tick=index,
                    participant_refs=(REF,),
                    event_classes=("attack",),
                    last_tick=index,
                )
                for index in range(policy.max_total_records + 1)
            ),
            key=lambda row: row.episode_id,
        )
    )
    ledger = ConflictLedger(owner_id=OWNER, tick=1, episodes=episodes)
    with pytest.raises(OrganizedConflictCapacityError):
        enforce_organized_conflict_limits(ledger, policy)


def test_export_is_detached_and_sorted() -> None:
    ledger = _ledger()
    exported = export_organized_conflict_ledger(ledger)
    assert exported == ledger
    assert exported is not ledger
    assert exported.plans == tuple(sorted(exported.plans, key=lambda row: row.plan_id))


def test_caps_retain_referenced_terminations_and_interpretations() -> None:
    from agents.cognition.organized_conflict import ConflictEpisode

    policy = default_organized_conflict_policy()
    plan = _plan(1, status=ConflictPlanStatus.EXPIRED)
    termination = ConflictTermination(
        termination_id=conflict_termination_id(
            plan.plan_id, ConflictTerminationKind.EXPIRED, 1
        ),
        plan_id=plan.plan_id,
        kind=ConflictTerminationKind.EXPIRED,
        tick=1,
    )
    interpretation = _interpretation("", tick=1)
    episode = ConflictEpisode(
        episode_id=conflict_episode_id(OWNER, 1, (REF,), ("attack",)),
        start_tick=1,
        end_tick=1,
        participant_refs=(REF,),
        event_classes=("attack",),
        interpretation_ids=(interpretation.interpretation_id,),
        last_tick=policy.plan_ttl_ticks + 100,
    )
    interpretation = replace(interpretation, episode_ref=episode.episode_id)
    ledger = ConflictLedger(
        owner_id=OWNER,
        tick=policy.plan_ttl_ticks + 100,
        plans=(plan,),
        interpretations=(interpretation,),
        terminations=(termination,),
        episodes=(episode,),
    )
    pruned = enforce_organized_conflict_limits(ledger, policy)
    assert pruned.plans == (plan,)
    assert pruned.terminations == (termination,)
    assert pruned.interpretations == (interpretation,)
    assert pruned.episodes == (episode,)
