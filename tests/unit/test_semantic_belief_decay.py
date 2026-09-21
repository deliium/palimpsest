"""Unit tests for semantic belief confidence decay."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from memory.belief_formation import (
    BeliefFormationPolicy,
    apply_confidence_decay,
    revise_confidence,
)
from memory.beliefs import BeliefConfidenceState
from memory.scoring import apply_belief_confidence_decay


def test_decay_moves_toward_uncertainty_not_contradiction() -> None:
    policy = BeliefFormationPolicy(
        policy_id="decay",
        version="1",
        decay_half_life_ticks=10,
    )
    prior = BeliefConfidenceState(
        confidence=0.8, support_mass=0.8, contradiction_mass=0.1
    )
    decayed = apply_confidence_decay(prior, elapsed_ticks=10, policy=policy)
    assert decayed.confidence < prior.confidence
    assert decayed.support_mass < prior.support_mass
    assert decayed.contradiction_mass < prior.contradiction_mass
    assert decayed.confidence >= 0.0
    # Contradiction mass shrinks; decay does not invent contradiction.
    assert decayed.contradiction_mass <= prior.contradiction_mass


def test_scoring_wrapper_matches_formation_decay() -> None:
    state = BeliefConfidenceState(
        confidence=0.6, support_mass=0.6, contradiction_mass=0.2
    )
    via_score = apply_belief_confidence_decay(
        state, elapsed_ticks=20, half_life_ticks=20
    )
    via_formation = apply_confidence_decay(
        state,
        elapsed_ticks=20,
        policy=BeliefFormationPolicy(
            policy_id="score-decay",
            version="1",
            decay_half_life_ticks=20,
        ),
    )
    assert via_score == via_formation


def test_zero_elapsed_is_identity() -> None:
    policy = BeliefFormationPolicy(policy_id="decay", version="1")
    state = BeliefConfidenceState(
        confidence=0.4, support_mass=0.4, contradiction_mass=0.0
    )
    assert apply_confidence_decay(state, elapsed_ticks=0, policy=policy) == state


@given(
    support=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    contradict=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    elapsed=st.integers(min_value=0, max_value=500),
)
def test_decay_keeps_bounds(support: float, contradict: float, elapsed: int) -> None:
    state = revise_confidence(
        prior=None, support_delta=support, contradiction_delta=contradict
    )
    decayed = apply_confidence_decay(
        state,
        elapsed_ticks=elapsed,
        policy=BeliefFormationPolicy(
            policy_id="decay",
            version="1",
            decay_half_life_ticks=50,
        ),
    )
    assert 0.0 <= decayed.confidence <= 1.0
    assert 0.0 <= decayed.support_mass <= 1.0
    assert 0.0 <= decayed.contradiction_mass <= 1.0
