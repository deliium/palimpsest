"""Teaching audits copy the three stores and stay off the result document."""

from __future__ import annotations

import dataclasses
import logging

import pytest

from agents.cognition.competence import (
    CompetenceBelief,
    CompetenceDomain,
    empty_competence_model,
)
from agents.models import AgentId
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    SimulationRunnerResultDocument,
    TeachingAudit,
    TeachingAuditStore,
)
from tests.unit.test_simulation_runner_construction import _config

pytestmark = pytest.mark.unit


def _quantize(value: float) -> float:
    return round(value / 1e-6) * 1e-6


def test_result_document_has_no_teaching_field() -> None:
    names = {field.name for field in dataclasses.fields(SimulationRunnerResultDocument)}
    assert "teaching_audits" not in names
    assert "skill_audits" not in names


@pytest.mark.asyncio
async def test_export_copies_explain_belief_and_objective(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.cognition.teaching import (
        AdviceAct,
        AdviceBand,
        AdviceDomain,
        DeclarativeAdvice,
        empty_advice_store,
    )

    built = _teaching_config()
    caplog.set_level(logging.DEBUG, logger="simulation.runner")
    async with await SimulationRunner.from_config(
        built, run_id=RunId("run-teach-audit")
    ) as runner:
        runtime = runner.runtimes[0]
        believed = _quantize(0.08 / 1.08)
        model = empty_competence_model(runtime.agent_id)
        beliefs = list(model.beliefs)
        beliefs[0] = CompetenceBelief(
            domain=CompetenceDomain.FORAGING,
            believed_level=believed,
            support_mass=0.08,
            counter_mass=0.0,
        )
        runtime._competence = dataclasses.replace(model, beliefs=tuple(beliefs))
        runtime._advice = empty_advice_store(runtime.agent_id).record(
            DeclarativeAdvice(
                occurrence_id="occ-high",
                source_agent_id=AgentId("agent-2"),
                act=AdviceAct.EXPLAIN,
                domain=AdviceDomain.FORAGING,
                band=AdviceBand.HIGH,
                delivery_tick=1,
            )
        )
        rows = runner.export_teaching_audits()
    advice = next(row for row in rows if row.store is TeachingAuditStore.ADVICE)
    belief = next(
        row
        for row in rows
        if row.store is TeachingAuditStore.BELIEF and row.domain == "foraging"
    )
    objective = next(
        row
        for row in rows
        if row.store is TeachingAuditStore.OBJECTIVE and row.domain == "foraging"
    )
    assert advice.token == "explain"
    assert advice.band_or_level == "high"
    assert belief.band_or_level == format(believed, ".6f")
    assert objective.band_or_level == format(_quantize(0.0), ".6f")
    assert isinstance(advice, TeachingAudit)
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "teaching_audit" in messages
    assert "agent_id=" in messages
    assert "store=advice" in messages
    assert "domain=foraging" in messages
    assert "tick=1" in messages


def _teaching_config():
    from dataclasses import replace

    from simulation.runner_models import (
        RUNNER_SCHEMA_VERSION_V12,
        SkillLearningMode,
        TeachingInteractionMode,
    )

    base = _config()
    agents = []
    for agent in base.agents:
        cognition = replace(
            agent.cognition,
            skill_learning_mode=SkillLearningMode.DETERMINISTIC,
            teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
        )
        agents.append(replace(agent, cognition=cognition))
    return replace(
        base,
        agents=tuple(agents),
        schema_version=RUNNER_SCHEMA_VERSION_V12,
        stop_policy=replace(base.stop_policy, max_ticks=1),
    )


@pytest.mark.asyncio
async def test_two_runs_emit_the_same_teaching_audits() -> None:
    config = _teaching_config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-teach-a")
    ) as left:
        result_left = await left.run()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-teach-b")
    ) as right:
        result_right = await right.run()
    assert result_left.teaching_audits == result_right.teaching_audits
    assert result_left.teaching_audits
