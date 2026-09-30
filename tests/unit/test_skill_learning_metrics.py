"""Skill-gap metric and seeded runner identity for learnable skills."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from agents.models import AgentId
from analysis.skill_learning_metrics import (
    SKILL_LEARNING_METRIC_VERSION,
    compute_skill_learning,
)
from experiments.catalog import experiment_r_skill_learning
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import SkillAudit, SkillAuditSide
from tests.unit.test_v2_flag_defaults import _base
from world.events import Searched

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _quantize(value: float) -> float:
    return round(value / 1e-6) * 1e-6


def test_metric_joins_sides_and_does_not_guess(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = (_ROOT / "src/analysis/skill_learning_metrics.py").read_text()
    assert "fold_skill_growth" not in source
    assert "update_competence" not in source
    objective = SkillAudit(
        agent_id=AgentId("agent-1"),
        side=SkillAuditSide.OBJECTIVE,
        domain="foraging",
        level=_quantize(0.07),
        tick=1,
    )
    believed = SkillAudit(
        agent_id=AgentId("agent-1"),
        side=SkillAuditSide.SUBJECTIVE,
        domain="foraging",
        level=_quantize(0.10 / 1.10),
        tick=1,
    )
    missing = SkillAudit(
        agent_id=AgentId("agent-1"),
        side=SkillAuditSide.OBJECTIVE,
        domain="navigation",
        level=0.0,
        tick=1,
    )
    caplog.set_level(logging.DEBUG, logger="analysis.skill_learning_metrics")
    result = compute_skill_learning(
        (objective, believed, missing),
        run_id="run-skill",
        input_revision="rev-1",
    )
    assert SKILL_LEARNING_METRIC_VERSION == "skill_learning@1"
    matched = next(row for row in result.rows if row.domain == "foraging")
    assert matched.empirical_status == "matched"
    assert matched.gap == _quantize(abs(objective.level - believed.level))
    unmatched = next(row for row in result.rows if row.domain == "navigation")
    assert unmatched.empirical_status == "unmatched"
    assert unmatched.believed_level is None
    assert unmatched.gap is None
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "skill_gap" in messages
    assert "agent_id=agent-1" in messages
    assert "domain=foraging" in messages
    assert "utterance" not in messages


def _search_bits(runner: SimulationRunner) -> tuple[bool, ...]:
    exported = runner.engine.export_events()
    return tuple(
        event.details.success
        for event in exported.events
        if type(event.details) is Searched and type(event.details.success) is bool
    )


def _level(
    runner: SimulationRunner, side: SkillAuditSide, domain: str
) -> float | None:
    matches = [
        row
        for row in runner.export_skill_audits()
        if row.domain == domain and row.side is side
    ]
    if not matches:
        return None
    return matches[0].level


@pytest.mark.asyncio
async def test_two_deterministic_runs_match_and_belief_lags_one_tick() -> None:
    definition = experiment_r_skill_learning(_base())
    disabled = definition.conditions[0].runner_config
    enabled = definition.conditions[1].runner_config
    first, first_bits = await _run(enabled, "run-skill-a")
    second, second_bits = await _run(enabled, "run-skill-b")
    assert _audit_key(first) == _audit_key(second)
    assert first_bits == second_bits
    off, off_bits = await _run(disabled, "run-skill-off")
    twin, twin_bits = await _run(disabled, "run-skill-off-b")
    assert off.skill_audits == ()
    assert twin.skill_audits == ()
    assert off_bits == twin_bits
    async with await SimulationRunner.from_config(
        enabled, run_id=RunId("run-skill-lag")
    ) as runner:
        await runner.run_tick()
        objective_foraging = _level(runner, SkillAuditSide.OBJECTIVE, "foraging")
        objective_detection = _level(
            runner, SkillAuditSide.OBJECTIVE, "resource_detection"
        )
        belief_foraging = _level(runner, SkillAuditSide.SUBJECTIVE, "foraging")
        belief_detection = _level(
            runner, SkillAuditSide.SUBJECTIVE, "resource_detection"
        )
        await runner.run_tick()
        belief_foraging_after = _level(runner, SkillAuditSide.SUBJECTIVE, "foraging")
        belief_detection_after = _level(
            runner, SkillAuditSide.SUBJECTIVE, "resource_detection"
        )
        searches = _search_bits(runner)
    if searches:
        assert belief_foraging == 0.0
        assert belief_detection == 0.0
        if searches[0]:
            expected = _quantize(0.07)
            believed = _quantize(0.10 / 1.10)
            assert objective_foraging == expected or objective_detection == expected
            assert (
                belief_foraging_after == believed or belief_detection_after == believed
            )
        else:
            missed = _quantize(0.03)
            assert objective_foraging == missed or objective_detection == missed
            assert belief_foraging_after == 0.0
            assert belief_detection_after == 0.0
    else:
        assert belief_foraging == belief_foraging_after


def _audit_key(result: object) -> tuple[object, ...]:
    return tuple(
        (row.agent_id.value, row.side.value, row.domain, row.level)
        for row in result.skill_audits
    )


async def _run(config: object, run_id: str):
    async with await SimulationRunner.from_config(
        config, run_id=RunId(run_id)
    ) as runner:
        result = await runner.run()
        return result, _search_bits(runner)
