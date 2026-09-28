"""Asymmetric knowledge judgments from owner observations and beliefs."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.communication import DeterministicSocialMessagePolicy
from agents.cognition.epistemic import (
    EpistemicAttitude,
    EpistemicJudgment,
    EpistemicPolicy,
    default_epistemic_policy,
    epistemic_disclosure,
    update_epistemic_state,
)
from agents.cognition.models import DecisionMetadata, RetrievedMemoryContext
from agents.cognition.theory_of_mind import TheoryOfMind
from agents.models import AgentId
from memory import BeliefActivationState, BeliefId
from tests.unit.test_epistemic_model import _belief, _level1, _speech, _watch
from tests.unit.test_theory_of_mind import _occurrence
from world.actions import Ask, Talk, Tell
from world.communications import CommunicationSourceBasis
from world.identifiers import EntityId

_EPISTEMIC = "agents.cognition.epistemic"
_MESSAGE = "agents.cognition.communication"
_OWNER = AgentId("agent-alice")
_BOB = "body-bob"


def _memory(belief: object) -> RetrievedMemoryContext:
    return RetrievedMemoryContext(
        owner_id=_OWNER,
        memory_ids=(),
        belief_ids=(belief.belief_id,),  # type: ignore[attr-defined]
        confidence=1.0,
        semantic_beliefs=(belief,),  # type: ignore[arg-type]
        decision_metadata=DecisionMetadata(candidate_count=0),
    )


def _choose(mind: TheoryOfMind, belief: object, observation: object) -> object:
    return DeterministicSocialMessagePolicy().select(
        owner_id=_OWNER,
        speaker_id=EntityId("body-alice"),
        observation=observation,  # type: ignore[arg-type]
        memory=_memory(belief),
        selected_belief_ids=(BeliefId(belief.belief_id.value),),  # type: ignore[attr-defined]
        mind=mind,
    )


def _ledger(belief: object, observation: object, *, prior: TheoryOfMind | None = None):
    model = prior if prior is not None else TheoryOfMind(owner_id=_OWNER)
    return update_epistemic_state(
        model,
        observation,  # type: ignore[arg-type]
        (belief,),  # type: ignore[arg-type]
        default_epistemic_policy(),
    )


def test_new_already_known_and_secret_change_the_tell(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_MESSAGE)
    caplog.set_level(logging.DEBUG, logger=_EPISTEMIC)
    belief = _belief(confidence=0.8, support_mass=1.0, contradiction_mass=0.0)
    witnessed = _watch(
        tick=2,
        occurrences=(
            _occurrence(kind="eat", tick=2, actor="body-carol", event="evt-eat"),
        ),
        bodies=("body-carol",),
    )
    learned = _ledger(belief, witnessed)
    row = _level1(learned, "belief:belief-1")
    assert row.confidence == pytest.approx(0.8)
    assert row.witness_ids == ("body-carol",)
    visible = _watch(tick=3, bodies=("body-carol", _BOB))
    refreshed = _ledger(belief, visible, prior=learned)
    kept = _level1(refreshed, "belief:belief-1")
    assert _BOB not in kept.witness_ids
    disclosure = epistemic_disclosure(
        refreshed, _BOB, "belief:belief-1", default_epistemic_policy()
    )
    assert disclosure is not None
    assert disclosure.judgment is EpistemicJudgment.NEW
    told = _choose(refreshed, belief, visible)
    assert type(told.command) is Tell  # type: ignore[attr-defined]

    seen = _ledger(
        belief,
        _watch(
            tick=4,
            occurrences=(
                _occurrence(kind="eat", tick=4, actor=_BOB, event="evt-bob"),
            ),
            bodies=(_BOB,),
        ),
    )
    known_row = _level1(seen, "belief:belief-1")
    assert _BOB in known_row.witness_ids
    assert any(
        item.nesting_level == 2
        and item.modeled_agents == (_BOB,)
        and item.attitude is EpistemicAttitude.KNOWS
        for item in seen.attributions
    )
    already = epistemic_disclosure(
        seen, _BOB, "belief:belief-1", default_epistemic_policy()
    )
    assert already is not None
    assert already.judgment is EpistemicJudgment.ALREADY_KNOWN
    quiet = _choose(seen, belief, _watch(tick=4, bodies=(_BOB,)))
    assert type(quiet.command) is not Tell  # type: ignore[attr-defined]

    secret_model = _ledger(belief, _watch(tick=5, bodies=(_BOB,)))
    assert _level1(secret_model, "belief:belief-1").witness_ids == ()
    secret = epistemic_disclosure(
        secret_model, _BOB, "belief:belief-1", default_epistemic_policy()
    )
    assert secret is not None
    assert secret.judgment is EpistemicJudgment.SECRET
    withheld = _choose(secret_model, belief, _watch(tick=5, bodies=(_BOB,)))
    assert type(withheld.command) is not Tell  # type: ignore[attr-defined]
    text = caplog.text
    assert "judgment=new" in text
    assert "judgment=already_known" in text
    assert "judgment=secret" in text
    assert "hidden-speech" not in text


def test_uncertain_asks_only_for_allowlisted_tokens(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_MESSAGE)
    observation = _watch(tick=2, bodies=(_BOB,))
    unsure = _belief(
        confidence=0.5,
        support_mass=0.5,
        contradiction_mass=0.0,
        predicate="food",
    )
    model = _ledger(unsure, observation)
    row = _level1(model, "belief:belief-1")
    assert row.attitude is EpistemicAttitude.UNCERTAIN
    asked = _choose(model, unsure, observation)
    assert type(asked.command) is Ask  # type: ignore[attr-defined]
    assert asked.source_basis is CommunicationSourceBasis.UNREFERENCED  # type: ignore[attr-defined]
    other = _belief(
        belief_id="belief-other",
        confidence=0.5,
        support_mass=0.5,
        predicate="at",
        text_value="place-1",
    )
    plain = _ledger(other, observation)
    skipped = _choose(plain, other, observation)
    assert type(skipped.command) is Talk  # type: ignore[attr-defined]
    assert "judgment=uncertain" in caplog.text


def test_contradiction_and_competing_rows_block_the_tell() -> None:
    observation = _watch(tick=2, bodies=(_BOB,))
    conflicted = _belief(confidence=0.8, support_mass=0.8, contradiction_mass=0.5)
    model = _ledger(conflicted, observation)
    row = _level1(model, "belief:belief-1")
    assert row.attitude is EpistemicAttitude.UNCERTAIN
    assert row.contradiction_mass == pytest.approx(0.5)
    judgment = epistemic_disclosure(
        model, _BOB, "belief:belief-1", default_epistemic_policy()
    )
    assert judgment is not None
    assert judgment.judgment is EpistemicJudgment.CONTRADICTORY
    assert type(_choose(model, conflicted, observation).command) is Talk  # type: ignore[attr-defined]

    copied = _belief(confidence=0.8, support_mass=1.0, contradiction_mass=0.0)
    stored = _level1(_ledger(copied, observation), "belief:belief-1")
    assert stored.confidence == pytest.approx(0.8)

    fact_watch = _watch(
        tick=6,
        occurrences=(_occurrence(kind="eat", tick=6, actor=_BOB, event="evt-fact"),),
        bodies=("body-carol",),
        communications=(
            _speech(
                predicate="does_not_know",
                obj="fact:eat:none",
                subject="body-carol",
                event="evt-deny",
            ),
        ),
    )
    mixed = update_epistemic_state(
        TheoryOfMind(owner_id=_OWNER),
        fact_watch,
        (),
        default_epistemic_policy(),
    )
    fact_rows = [
        item
        for item in mixed.attributions
        if item.proposition_ref == "fact:eat:none"
        and item.modeled_agents == ("body-carol",)
    ]
    attitudes = {item.attitude for item in fact_rows}
    assert EpistemicAttitude.KNOWS in attitudes
    assert EpistemicAttitude.DOES_NOT_KNOW in attitudes
    fact_judgment = epistemic_disclosure(
        mixed, "body-carol", "fact:eat:none", default_epistemic_policy()
    )
    assert fact_judgment is not None
    assert fact_judgment.judgment is EpistemicJudgment.CONTRADICTORY
    lone = _choose(TheoryOfMind(owner_id=_OWNER), copied, observation)
    assert type(lone.command) is Tell  # type: ignore[attr-defined]


def test_inactive_heads_depth_cap_and_multi_hop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from tests.unit.test_epistemic_model import _row

    caplog.set_level(logging.WARNING, logger=_EPISTEMIC)
    observation = _watch(tick=2, bodies=(_BOB,))
    inactive = update_epistemic_state(
        TheoryOfMind(owner_id=_OWNER),
        observation,
        (
            _belief(state=BeliefActivationState.CANDIDATE),
            _belief(belief_id="belief-2", state=BeliefActivationState.RETIRED),
        ),
        default_epistemic_policy(),
    )
    assert inactive.attributions == ()
    assert "reason_code=belief_inactive" in caplog.text
    with pytest.raises(ValueError, match="epistemic_depth_rejected"):
        _row(nesting_level=4, modeled_agents=("a", "b", "c"))
    deep = _row(
        nesting_level=3,
        modeled_agents=("body-bob", "body-carol"),
        proposition_ref="fact:move:none",
    )
    capped = update_epistemic_state(
        TheoryOfMind(owner_id=_OWNER, attributions=(deep,)),
        observation,
        (),
        EpistemicPolicy(max_depth=2),
    )
    assert all(item.nesting_level <= 2 for item in capped.attributions)
    assert "reason_code=epistemic_depth_exceeded" in caplog.text
    held = TheoryOfMind(owner_id=_OWNER, attributions=(_row(),))
    frozen = update_epistemic_state(
        held, observation, (), EpistemicPolicy(max_depth=0)
    )
    assert frozen is held
    multi = update_epistemic_state(
        TheoryOfMind(owner_id=_OWNER),
        _watch(
            tick=3,
            communications=(
                _speech(predicate="knows", obj="food", hop=2, event="evt-hop"),
            ),
            bodies=(_BOB,),
        ),
        (),
        default_epistemic_policy(),
    )
    assert multi.attributions == ()
    assert "reason_code=multi_hop_deferred" in caplog.text
    assert "hidden-speech" not in caplog.text
