"""Disclosure judgments and the speech-act hook."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.communication import DeterministicSocialMessagePolicy
from agents.cognition.epistemic import (
    EpistemicAttitude,
    EpistemicAttribution,
    EpistemicJudgment,
    EpistemicPolicy,
    EpistemicSource,
    default_epistemic_policy,
    epistemic_disclosure,
)
from agents.cognition.models import DecisionMetadata, RetrievedMemoryContext
from agents.cognition.theory_of_mind import TheoryOfMind
from agents.models import AgentId
from memory import BeliefId
from tests.unit.test_epistemic_model import _belief, _watch
from world.actions import Tell
from world.identifiers import EntityId

_LOG = "agents.cognition.epistemic"
_MESSAGE = "agents.cognition.communication"
_OWNER = AgentId("agent-alice")
_BOB = "body-bob"


def _attribution(
    *,
    nesting_level: int = 1,
    attitude: EpistemicAttitude = EpistemicAttitude.KNOWS,
    modeled_agents: tuple[str, ...] = (),
    proposition_ref: str = "belief:belief-1",
    confidence: float = 0.8,
    contradiction_mass: float = 0.0,
    witness_ids: tuple[str, ...] = (),
    source: EpistemicSource = EpistemicSource.SEMANTIC_BELIEF,
) -> EpistemicAttribution:
    return EpistemicAttribution(
        owner_id=_OWNER,
        proposition_ref=proposition_ref,
        attitude=attitude,
        support=confidence,
        counter=contradiction_mass,
        confidence=confidence,
        source=source,
        nesting_level=nesting_level,
        belief_id="belief-1" if proposition_ref.startswith("belief:") else None,
        modeled_agents=modeled_agents,
        contradiction_mass=contradiction_mass,
        witness_ids=witness_ids,
        updated_tick=1,
    )


def _model(*rows: EpistemicAttribution) -> TheoryOfMind:
    return TheoryOfMind(owner_id=_OWNER, attributions=rows)


def test_disclosure_precedence_and_skip_reasons(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOG)
    policy = default_epistemic_policy()
    proposition = "belief:belief-1"
    assert epistemic_disclosure(None, _BOB, proposition, policy) is None
    assert "reason=no_model" in caplog.text
    assert (
        epistemic_disclosure(
            TheoryOfMind(owner_id=_OWNER), _BOB, proposition, policy
        )
        is None
    )
    assert "reason=empty_ledger" in caplog.text
    assert (
        epistemic_disclosure(
            _model(_attribution()),
            _BOB,
            proposition,
            EpistemicPolicy(max_depth=0),
        )
        is None
    )
    assert "reason=depth_zero" in caplog.text
    assert (
        epistemic_disclosure(_model(_attribution()), _BOB, "belief:missing", policy)
        is None
    )
    assert "reason=unknown_proposition" in caplog.text

    contradictory = epistemic_disclosure(
        _model(
            _attribution(
                contradiction_mass=0.5,
                attitude=EpistemicAttitude.UNCERTAIN,
            )
        ),
        _BOB,
        proposition,
        policy,
    )
    assert contradictory is not None
    assert contradictory.judgment is EpistemicJudgment.CONTRADICTORY
    competing = epistemic_disclosure(
        _model(
            _attribution(witness_ids=("body-carol",)),
            _attribution(
                nesting_level=2,
                modeled_agents=(_BOB,),
                attitude=EpistemicAttitude.KNOWS,
                source=EpistemicSource.DERIVED,
                proposition_ref=proposition,
            ),
            _attribution(
                nesting_level=2,
                modeled_agents=(_BOB,),
                attitude=EpistemicAttitude.DOES_NOT_KNOW,
                source=EpistemicSource.DERIVED,
                proposition_ref="fact:eat:none",
            ),
        ),
        _BOB,
        proposition,
        policy,
    )
    # Competing pair must share the proposition. Rebuild without the fact mix.
    competing = epistemic_disclosure(
        _model(
            _attribution(witness_ids=("body-carol",)),
            _attribution(
                nesting_level=2,
                modeled_agents=(_BOB,),
                attitude=EpistemicAttitude.KNOWS,
                source=EpistemicSource.DERIVED,
            ),
            _attribution(
                nesting_level=2,
                modeled_agents=(_BOB,),
                attitude=EpistemicAttitude.DOES_NOT_KNOW,
                source=EpistemicSource.DERIVED,
            ),
        ),
        _BOB,
        proposition,
        policy,
    )
    assert competing is not None
    assert competing.judgment is EpistemicJudgment.CONTRADICTORY
    uncertain = epistemic_disclosure(
        _model(
            _attribution(
                attitude=EpistemicAttitude.UNCERTAIN,
                confidence=0.5,
            )
        ),
        _BOB,
        proposition,
        policy,
    )
    assert uncertain is not None
    assert uncertain.judgment is EpistemicJudgment.UNCERTAIN
    known = epistemic_disclosure(
        _model(
            _attribution(witness_ids=(_BOB,)),
            _attribution(
                nesting_level=2,
                modeled_agents=(_BOB,),
                attitude=EpistemicAttitude.KNOWS,
                source=EpistemicSource.DERIVED,
            ),
        ),
        _BOB,
        proposition,
        policy,
    )
    assert known is not None
    assert known.judgment is EpistemicJudgment.ALREADY_KNOWN
    secret = epistemic_disclosure(
        _model(_attribution(witness_ids=())),
        _BOB,
        proposition,
        policy,
    )
    assert secret is not None
    assert secret.judgment is EpistemicJudgment.SECRET
    new = epistemic_disclosure(
        _model(_attribution(witness_ids=("body-carol",))),
        _BOB,
        proposition,
        policy,
    )
    assert new is not None
    assert new.judgment is EpistemicJudgment.NEW
    text = caplog.text
    assert "epistemic_disclosure " in text
    assert "judgment=new" in text
    assert "hidden-speech" not in text
    assert "utterance" not in text


def _select(mind: TheoryOfMind | None, belief: object) -> object:
    memory = RetrievedMemoryContext(
        owner_id=_OWNER,
        memory_ids=(),
        belief_ids=(belief.belief_id,),  # type: ignore[attr-defined]
        confidence=1.0,
        semantic_beliefs=(belief,),  # type: ignore[arg-type]
        decision_metadata=DecisionMetadata(candidate_count=0),
    )
    return DeterministicSocialMessagePolicy().select(
        owner_id=_OWNER,
        speaker_id=EntityId("body-alice"),
        observation=_watch(tick=3, bodies=(_BOB,)),
        memory=memory,
        selected_belief_ids=(BeliefId(belief.belief_id.value),),  # type: ignore[attr-defined]
        mind=mind,
    )


def test_empty_ledger_keeps_the_belief_tell(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_MESSAGE)
    belief = _belief()
    decision = _select(TheoryOfMind(owner_id=_OWNER), belief)
    assert type(decision.command) is Tell  # type: ignore[attr-defined]
    assert "reason=empty_ledger" in caplog.text
    assert "hidden-speech" not in caplog.text
