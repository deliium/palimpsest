"""Transition rows are bounded, unique, and ordered by observation tick."""

from __future__ import annotations

from agents.cognition.cultural_narratives import (
    CULTURAL_NARRATIVE_POLICY_VERSION_V2,
    NarrativeTransitionKind,
    apply_narrative_update,
    default_generational_narrative_policy,
    empty_narrative_ledger,
)
from agents.models import AgentId
from tests.unit.test_cultural_narratives import _identity, _observation, _occurrence
from tests.unit.test_narrative_records import _cue, _ledger, _update

_OWNER = AgentId("alice")


def test_minted_transition_is_stable_across_updates() -> None:
    first = apply_narrative_update(
        observation=_observation(
            tick=2,
            occurrences=(_occurrence("agent_entered_world", 2, "evt-found"),),
        ),
        identity=_identity(),
        previous=empty_narrative_ledger(
            _OWNER, policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2
        ),
        policy=default_generational_narrative_policy(),
    )
    minted = [
        transition
        for transition in first.variants[0].transitions
        if transition.kind is NarrativeTransitionKind.MINTED
    ]
    assert len(minted) == 1
    second = apply_narrative_update(
        observation=_observation(tick=3),
        identity=_identity(),
        previous=first,
        policy=default_generational_narrative_policy(),
    )
    assert [
        transition.transition_id
        for transition in second.variants[0].transitions
        if transition.kind is NarrativeTransitionKind.MINTED
    ] == [minted[0].transition_id]


def test_transition_cap_holds() -> None:
    policy = default_generational_narrative_policy()
    ledger = _ledger()
    for revision in range(1, 40):
        ledger = _update(ledger, _cue(observed_revision=revision))
    assert len(ledger.variants[0].transitions) <= policy.max_transitions


def test_transition_ids_unique() -> None:
    ledger = _ledger()
    for revision in range(1, 10):
        ledger = _update(ledger, _cue(observed_revision=revision))
    ids = [transition.transition_id for transition in ledger.variants[0].transitions]
    assert len(ids) == len(set(ids))


def test_retired_transition_is_emitted_under_v2() -> None:
    from tests.unit.test_narrative_themes import _variant

    ledger = apply_narrative_update(
        observation=_observation(tick=2),
        identity=_identity(),
        previous=ledger_with(_variant(strength=0.21, repetition_count=1)),
        policy=default_generational_narrative_policy(),
    )
    variant = ledger.variants[0]
    assert variant.status.value == "retired"
    assert NarrativeTransitionKind.RETIRED in {
        transition.kind for transition in variant.transitions
    }


def ledger_with(*variants: object) -> object:
    from agents.cognition.cultural_narratives import NarrativeLedger

    return NarrativeLedger(
        owner_id=_OWNER,
        policy_version=CULTURAL_NARRATIVE_POLICY_VERSION_V2,
        variants=variants,  # type: ignore[arg-type]
    )
