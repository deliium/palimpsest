"""Repeated experiment outcomes mint knowledge only through the learn gate."""

from __future__ import annotations

from dataclasses import fields

from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    ExperimentHypothesis,
    ExperimentTrial,
    admit_hypothesis,
    commit_experiment_learning,
    empty_experiment_ledger,
    experiment_hypothesis_id,
    record_trial,
)
from agents.cognition.practical_knowledge import (
    PracticalKnowledgeLedger,
    apply_practical_knowledge_from_independent_discovery,
    empty_practical_knowledge_ledger,
)
from agents.models import AgentId
from simulation.runner_models import KnowledgeGenealogyUptakeCompose
from world.experimentation import ExperimentOperator, ExperimentProcessToken

_OWNER = AgentId("owner-1")
_KINDS = ("crafting_process",)


def _experiment_ledger(
    *,
    threshold: int,
    learn: bool,
    outcomes: tuple[str, ...],
) -> tuple[object, str]:
    binding = ExperimentCognitionBinding(
        max_hypotheses=4,
        max_trials_per_tick=1,
        repeat_threshold=threshold,
        learn_into_genealogy=learn,
        allow_provider=False,
    )
    ledger = empty_experiment_ledger(_OWNER, binding)
    operator = ExperimentOperator.COMBINE
    token = ExperimentProcessToken.NONE
    hypothesis_id = experiment_hypothesis_id(
        _OWNER, operator, "item-a", "item-b", token
    )
    ledger = admit_hypothesis(
        ledger,
        ExperimentHypothesis(
            owner_id=_OWNER,
            hypothesis_id=hypothesis_id,
            operator=operator,
            operand_a_id="item-a",
            operand_b_id="item-b",
            process_token=token,
            predicted_outcome="success",
        ),
    )
    for index, outcome in enumerate(outcomes):
        ledger = record_trial(
            ledger,
            ExperimentTrial(
                tick=index,
                event_id=f"evt-{index}",
                outcome_class=outcome,
                discovery_mode="deliberate",
                hypothesis_id=hypothesis_id,
            ),
        )
    return ledger, hypothesis_id


def _learn(ledger: object, *, genealogy: bool = True):
    knowledge = empty_practical_knowledge_ledger(_OWNER)
    _kept, updated = commit_experiment_learning(
        ledger,  # type: ignore[arg-type]
        knowledge,
        genealogy_active=genealogy,
        enabled_kinds=_KINDS,
        tick=4,
    )
    assert isinstance(updated, PracticalKnowledgeLedger)
    return updated


def test_threshold_two_waits_for_the_second_success() -> None:
    once, _hypothesis_id = _experiment_ledger(
        threshold=2, learn=True, outcomes=("success",)
    )
    assert _learn(once).entries == ()
    twice, hypothesis_id = _experiment_ledger(
        threshold=2, learn=True, outcomes=("success", "success")
    )
    learned = _learn(twice)
    assert len(learned.entries) == 1
    refs = learned.entries[0].evidence_refs
    assert "evt:evt-1" in refs
    assert f"hypothesis:{hypothesis_id}" in refs
    assert "discovery_mode:deliberate" in refs
    assert learned.entries[0].origin.value == "independent_discovery"


def test_threshold_one_mints_on_the_first_success() -> None:
    ledger, _hypothesis_id = _experiment_ledger(
        threshold=1, learn=True, outcomes=("success",)
    )
    assert len(_learn(ledger).entries) == 1


def test_channel_off_skips() -> None:
    ledger, _hypothesis_id = _experiment_ledger(
        threshold=1, learn=False, outcomes=("success", "success")
    )
    assert _learn(ledger).entries == ()
    again, _hypothesis_id = _experiment_ledger(
        threshold=1, learn=True, outcomes=("success", "success")
    )
    assert _learn(again, genealogy=False).entries == ()


def test_harm_never_mints() -> None:
    ledger, _hypothesis_id = _experiment_ledger(
        threshold=1, learn=True, outcomes=("harm", "harm")
    )
    assert _learn(ledger).entries == ()


def test_uptake_compose_keyset_stays_v35() -> None:
    assert {item.name for item in fields(KnowledgeGenealogyUptakeCompose)} == {
        "teaching",
        "imitation",
        "written_record",
        "reconstruction",
        "developmental",
        "independent_discovery",
    }


def test_old_scanner_ignores_experiment_resolved() -> None:
    knowledge = empty_practical_knowledge_ledger(_OWNER)

    class _Occurrence:
        kind = "experiment_resolved"
        other_entity_id = None
        success = True

        class provenance:
            event_id = None

    class _Observation:
        occurrences = (_Occurrence(),)

    updated, audits = apply_practical_knowledge_from_independent_discovery(
        knowledge,
        enabled_kinds=_KINDS,
        observation=_Observation(),
        tick=1,
        independent_compose_on=True,
    )
    assert updated.entries == ()
    assert audits == ()
