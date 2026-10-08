"""Owner experiment ledger stays subjective and law-free."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.configuration import build_cognitive_loop
from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    ExperimentHypothesis,
    ExperimentTrial,
    admit_hypothesis,
    cognition_binding_from_spec,
    empty_experiment_ledger,
    experiment_hypothesis_id,
    record_trial,
)
from agents.models import AgentId
from simulation.runner import _bounded_experimentation_loop_kwargs
from simulation.runner_models import example_bounded_experimentation_spec
from world.experimentation import (
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)

_OWNER = AgentId("owner-1")
_OTHER = AgentId("owner-2")


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


def _hypothesis(
    *,
    owner: AgentId = _OWNER,
    operand: str = "item-a",
    support: int = 0,
    created_tick: int = 0,
    predicted: str | None = ExperimentOutcomeClass.SUCCESS.value,
) -> ExperimentHypothesis:
    operator = ExperimentOperator.COMBINE
    token = ExperimentProcessToken.NONE
    return ExperimentHypothesis(
        owner_id=owner,
        hypothesis_id=experiment_hypothesis_id(
            owner, operator, operand, "item-b", token
        ),
        operator=operator,
        operand_a_id=operand,
        operand_b_id="item-b",
        process_token=token,
        predicted_outcome=predicted,
        support=support,
        created_tick=created_tick,
    )


def test_hypothesis_id_is_stable_and_owner_scoped() -> None:
    operator = ExperimentOperator.APPLY_TOOL
    token = ExperimentProcessToken.CRAFT
    first = experiment_hypothesis_id(_OWNER, operator, "tool-1", "res-1", token)
    again = experiment_hypothesis_id(_OWNER, operator, "tool-1", "res-1", token)
    other = experiment_hypothesis_id(_OTHER, operator, "tool-1", "res-1", token)
    assert first == again
    assert first.startswith("hyp:")
    assert first != other


def test_eviction_drops_lowest_support_then_oldest() -> None:
    ledger = empty_experiment_ledger(_OWNER, _binding(max_hypotheses=1))
    older = _hypothesis(operand="old", support=0, created_tick=1)
    newer = _hypothesis(operand="new", support=0, created_tick=4)
    kept = admit_hypothesis(admit_hypothesis(ledger, older), newer)
    assert [row.operand_a_id for row in kept.hypotheses] == ["new"]
    stronger = _hypothesis(operand="strong", support=3, created_tick=0)
    replaced = admit_hypothesis(kept, stronger)
    assert [row.operand_a_id for row in replaced.hypotheses] == ["strong"]


def test_repeat_admit_does_not_duplicate() -> None:
    ledger = empty_experiment_ledger(_OWNER, _binding())
    row = _hypothesis()
    once = admit_hypothesis(ledger, row)
    twice = admit_hypothesis(once, row)
    assert twice.hypotheses == once.hypotheses


def test_trial_cap_is_per_tick() -> None:
    ledger = empty_experiment_ledger(_OWNER, _binding(max_trials_per_tick=1))
    trial = ExperimentTrial(
        tick=3,
        event_id="evt-1",
        outcome_class="failure",
        discovery_mode="deliberate",
        hypothesis_id="hyp:1",
    )
    updated = record_trial(ledger, trial)
    with pytest.raises(ValueError, match="experiment_trial_cap"):
        record_trial(updated, trial)
    later = ExperimentTrial(
        tick=4,
        event_id="evt-2",
        outcome_class="unexpected",
        discovery_mode="accidental",
    )
    assert len(record_trial(updated, later).trials) == 2


def test_predicted_outcome_rejects_invented_class() -> None:
    with pytest.raises(ValueError, match="predicted_outcome"):
        _hypothesis(predicted="always_works")


def test_binding_copies_caps_without_laws() -> None:
    spec = example_bounded_experimentation_spec(allow_provider=True)
    binding = cognition_binding_from_spec(spec)
    assert binding.allow_provider is True
    assert not hasattr(binding, "laws")
    assert spec.laws


def test_absent_spec_omits_loop_kwargs() -> None:
    class _Off:
        bounded_experimentation = None

    assert _bounded_experimentation_loop_kwargs(_Off()) == {}


def test_present_spec_is_the_loop_kwarg() -> None:
    spec = example_bounded_experimentation_spec()

    class _On:
        bounded_experimentation = spec

    kwargs = _bounded_experimentation_loop_kwargs(_On())
    assert kwargs == {"bounded_experimentation_spec": spec}


def test_loop_keeps_caps_and_starts_an_empty_ledger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    spec = example_bounded_experimentation_spec(
        learn_into_genealogy=True, allow_provider=False
    )
    with caplog.at_level(logging.DEBUG):
        loop = build_cognitive_loop(bounded_experimentation_spec=spec)
        ledger = loop.experiment_ledger_for(_OWNER)
    caps = loop._bounded_experimentation_caps
    assert isinstance(caps, ExperimentCognitionBinding)
    assert not hasattr(caps, "laws")
    assert "bounded_experimentation_enabled" in caplog.text
    assert ledger is not None
    assert ledger.hypotheses == ()
    assert "experiment_ledger_constructed" in caplog.text
    with pytest.raises(ValueError, match="owner_id mismatch"):
        loop.experiment_ledger_for(_OTHER)


def test_loop_without_spec_does_not_write_a_ledger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.loop"):
        loop = build_cognitive_loop()
    assert loop._bounded_experimentation_caps is None
    assert loop.experiment_ledger_for(_OWNER) is None
    assert "bounded_experimentation_skipped" in caplog.text
    assert "experiment_ledger_constructed" not in caplog.text


@pytest.mark.asyncio
async def test_absent_object_shares_flags_off_trajectory_hash() -> None:
    from dataclasses import replace

    from experiments.catalog import (
        base_runner_config_from_scenario,
        v3_scaffolding_profile,
    )
    from simulation.models import RunId
    from simulation.runner import SimulationRunner
    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V4,
        AgentCognitionSpec,
        AgentRunnerSpec,
        MortalityMode,
        RunnerStopPolicy,
        V3CapabilityFlags,
        WorldScenarioSpec,
    )
    from simulation.runner_serialization import build_runner_result_document
    from tests.simulation_helpers import alive_body, make_location, make_weather
    from world.identifiers import WorldId, WorldRevision
    from world.models import non_lethal_physical_rules

    bodies = (alive_body("body-0"), alive_body("body-1"))
    specs = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(f"agent-{index}"),
            entity_id=body.entity_id,
            cognition=AgentCognitionSpec(agent_id=AgentId(f"agent-{index}")),
        )
        for index, body in enumerate(bodies)
    )
    base = base_runner_config_from_scenario(
        seed=52,
        stochastic_identity="cmp-v3-experiment-off",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v3-experiment-off"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(body_capacity=8),),
            bodies=bodies,
            weather=(make_weather(),),
        ),
        agents=specs,
        max_ticks=3,
    )
    flags_off = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=3),
        v3_capability_flags=V3CapabilityFlags(),
        bounded_experimentation=None,
    )
    v3_scaffolding_profile(flags_off)
    run_id = RunId("run-experiment-object-absent")
    async with await SimulationRunner.from_config(flags_off, run_id=run_id) as runner:
        first = await runner.run()
    async with await SimulationRunner.from_config(flags_off, run_id=run_id) as runner:
        second = await runner.run()
    doc_first = build_runner_result_document(result=first, config=flags_off)
    doc_second = build_runner_result_document(result=second, config=flags_off)
    assert doc_first.exact_trajectory_hash == doc_second.exact_trajectory_hash

