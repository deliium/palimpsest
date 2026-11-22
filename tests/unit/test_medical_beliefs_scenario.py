# mypy: ignore-errors

"""Paired medical-belief experiment preserves disease identity."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.catalog import OFF_GATE_MATRIX_EXPERIMENT_IDS
from experiments.medical_beliefs_scenario import (
    MEDICAL_BELIEFS_EXPERIMENT_ID,
    medical_beliefs_scenario,
)
from simulation.lifecycle import ActionResolutionStatus
from simulation.medical_beliefs_config import MEDICAL_BELIEFS_POLICY_ID
from simulation.models import RunId
from simulation.persistence import checkpoint_schema_for_production
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    RESULT_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V58,
    RUNNER_SCHEMA_VERSION_V59,
)
from simulation.runner_serialization import (
    cognition_fingerprint,
    runner_config_fingerprint,
    scenario_fingerprint,
)
from tests.unit.test_disease_config import _infra_base
from world.actions import Wait
from world.events import EVENT_SCHEMA_REPLAY_V24
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _conditions():
    definition = medical_beliefs_scenario(_infra_base(), max_ticks=8)
    return definition, {
        condition.condition_id: condition.runner_config
        for condition in definition.conditions
    }


def test_medical_beliefs_is_registered_off_gate() -> None:
    assert MEDICAL_BELIEFS_EXPERIMENT_ID == "medical_beliefs@1"
    assert "medical_beliefs@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS


def test_paired_configs_differ_only_by_schema_and_spec() -> None:
    definition, configs = _conditions()
    off = configs["beliefs-off"]
    on = configs["beliefs-on"]
    assert off.schema_version == RUNNER_SCHEMA_VERSION_V58
    assert on.schema_version == RUNNER_SCHEMA_VERSION_V59
    assert off.medical_beliefs is None
    assert on.medical_beliefs is not None
    assert on.medical_beliefs.policy_id == MEDICAL_BELIEFS_POLICY_ID
    assert off.seed == on.seed
    assert off.stochastic_identity == on.stochastic_identity
    assert off.scenario == on.scenario
    assert off.stop_policy == on.stop_policy
    assert off.disease_mechanics == on.disease_mechanics
    assert scenario_fingerprint(off) == scenario_fingerprint(on)
    assert runner_config_fingerprint(off) != runner_config_fingerprint(on)
    assert cognition_fingerprint(off) != cognition_fingerprint(on)
    assert definition.paired_world_group.endswith("-world")


def test_both_arms_keep_disease_replay_pair_and_defaults() -> None:
    _definition, configs = _conditions()
    for config in configs.values():
        assert checkpoint_schema_for_production(
            production_active=False, disease_active=True
        ) == (EVENT_SCHEMA_REPLAY_V24, "v22")
        assert config.v4_capability_flags.epidemics is True
        assert config.v4_capability_flags.infrastructure_networks is True
    assert RESULT_SCHEMA_VERSION == "runner-result-v2"


@pytest.mark.asyncio
async def test_beliefs_on_twins_are_deterministic() -> None:
    _definition, configs = _conditions()
    config = replace(
        configs["beliefs-on"],
        stop_policy=replace(configs["beliefs-on"].stop_policy, max_ticks=2),
    )
    results = []
    for ordinal in (1, 2):
        runner = await SimulationRunner.from_config(
            config,
            run_id=RunId(
                {
                    1: "run-medical-twin-a",
                    2: "run-medical-twin-b",
                }[ordinal]
            ),
            factories=RunnerDependencyFactories(),
        )
        async with runner:
            result = await runner.run()
        results.append(result)
    from simulation.runner_serialization import replica_normalized_trajectory_hash

    first = replica_normalized_trajectory_hash(
        tick_receipts=results[0].finalized_tick_receipts
    )
    second = replica_normalized_trajectory_hash(
        tick_receipts=results[1].finalized_tick_receipts
    )
    assert first == second


class _ScriptedPlanner:
    """Test-only planner wrapper; delegates then replaces one scripted command."""

    __slots__ = ("_base", "_root", "_state")

    def __init__(self, base: object, root: str) -> None:
        self._base = base
        self._root = root
        self._state: dict[str, int] = {}

    async def plan(self, loop_input: object, *args: object, **kwargs: object):
        plan = await self._base.plan(loop_input, *args, **kwargs)
        observation = loop_input.observation
        owner = observation.observer_id.value
        command = plan.command
        if owner == "body-a" and observation.tick == 0:
            command = _talk(
                "body-b",
                "body-a",
                self._root,
                "uncertain",
                observation.tick,
                include_relation=True,
            )
        elif owner == "body-b":
            body = observation.self_body
            cue = body is not None and body.symptom_cue == "unwell"
            if cue:
                self._state["b_cue"] = self._state.get("b_cue", 0) + 1
            if cue and self._state["b_cue"] == 1:
                command = Wait()
            elif cue and self._state["b_cue"] == 2:
                command = _talk(
                    "body-c",
                    "body-b",
                    self._root,
                    "not_obviously_helped",
                    observation.tick,
                    include_relation=False,
                )
        return replace(plan, command=command)


def _talk(
    recipient: str,
    speaker: str,
    root: str,
    outlook: str,
    tick: int,
    *,
    include_relation: bool,
):
    from world.actions import Talk
    from world.communications import CommunicationRelation, origin_utterance

    relations = ()
    if include_relation:
        relations = (
            CommunicationRelation(
                subject="medical_beliefs",
                predicate="mb_v1",
                object=f"cultural|ritual_pause|{outlook}|{root}|0",
            ),
        )
    return Talk(
        recipient_id=EntityId(recipient),
        utterance=origin_utterance(
            text="medical-beliefs",
            speaker_id=EntityId(speaker),
            communication_id=f"comm-mb-script-{tick}-{speaker}",
            relations=relations,
        ),
    )


@pytest.mark.asyncio
async def test_controlled_practice_persists_after_negative_feedback() -> None:
    from dataclasses import replace

    from experiments.medical_beliefs_capture import run_with_medical_beliefs_capture
    from experiments.medical_beliefs_scenario import medical_beliefs_scenario
    from simulation.runner import RunnerDependencyFactories, SimulationRunner
    from simulation.runner_models import RunnerStopPolicy
    from world.artifacts import ArtifactContent, ArtifactKind, InformationArtifact

    definition = medical_beliefs_scenario(_infra_base(), max_ticks=16)
    config = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "beliefs-on"
    )
    settled = EntityId("loc-settled")
    bodies = tuple(
        replace(body, location_id=settled)
        if body.entity_id == EntityId("body-c")
        else body
        for body in config.scenario.bodies
    )
    artifact = InformationArtifact(
        artifact_id=EntityId("artifact-1"),
        kind=ArtifactKind.MARK,
        author_id=EntityId("body-b"),
        created_tick=0,
        content=ArtifactContent(marks=("mark",)),
        location_id=settled,
    )
    disease = replace(
        config.disease_mechanics,
        initial_latent_entity_ids=(
            EntityId("body-a"),
            EntityId("body-b"),
        ),
    )
    config = replace(
        config,
        scenario=replace(config.scenario, bodies=bodies, artifacts=(artifact,)),
        stop_policy=RunnerStopPolicy(max_ticks=16),
        disease_mechanics=disease,
    )
    runner = await SimulationRunner.from_config(
        config,
        run_id=RunId("run-medical-controlled"),
        factories=RunnerDependencyFactories(),
    )
    root = "0123456789abcdef0123456789abcdef"
    for runtime in runner.runtimes:
        runtime._loop._planner = _ScriptedPlanner(runtime._loop._planner, root)
    async with runner:
        captured = await run_with_medical_beliefs_capture(runner, capture=True)
    assert captured.evidence is not None
    b_attempts = [
        row
        for row in captured.evidence.attempts
        if row.owner_id.value == "agent-2"
        and row.practice.value == "ritual_pause"
    ]
    assert b_attempts, "expected scripted ritual_pause attempt"
    assert b_attempts[0].command_kind == "wait"
    assert b_attempts[0].application_status is ActionResolutionStatus.APPLIED
    b_outcomes = [
        row
        for row in captured.evidence.outcomes
        if row.attempt_id == b_attempts[0].attempt_id
    ]
    assert b_outcomes and b_outcomes[0].outcome.value == "not_obviously_helped"
    assert len(b_outcomes) == 1
    b_interpretations = [
        row
        for row in captured.evidence.interpretations
        if row.attempt_id == b_attempts[0].attempt_id
    ]
    assert len(b_interpretations) == 1
    assert b_interpretations[0].outlook.value == "not_obviously_helped"
    c_transmissions = [
        row
        for row in captured.evidence.transmissions
        if row.owner_id.value == "agent-3"
        and row.root == root
        and row.speaker_id == EntityId("body-b")
    ]
    assert c_transmissions
    assert c_transmissions[0].hop == 1
    assert c_transmissions[0].outlook.value == "not_obviously_helped"


@pytest.mark.asyncio
async def test_mode_off_keeps_baseline_wait_unmarked() -> None:
    _definition, configs = _conditions()
    off = configs["beliefs-off"]
    runner = await SimulationRunner.from_config(
        replace(off, stop_policy=replace(off.stop_policy, max_ticks=2)),
        run_id=RunId("run-medical-off-baseline"),
        factories=RunnerDependencyFactories(),
    )
    async with runner:
        await runner.run()
        export = runner.export_medical_belief_ledgers()
    for runtime in runner.runtimes:
        assert runtime._loop.medical_belief_ledger_if_present() is None
    assert export.ledgers == ()
    assert len(export.unavailable_owner_ids) == len(runner.runtimes)
