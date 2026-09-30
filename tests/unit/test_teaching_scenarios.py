"""Engine scenarios for transmission, plus the post-run metric."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

import pytest

from agents.models import AgentId
from analysis.cultural_transmission_metrics import (
    CULTURAL_TRANSMISSION_METRIC_VERSION,
    compute_cultural_transmission,
)
from experiments.catalog import (
    experiment_s_cultural_transmission,
    experiment_t_skill_specialization,
    v1_regression_profile,
)
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V11,
    RUNNER_SCHEMA_VERSION_V12,
    TeachingAudit,
    TeachingAuditStore,
)
from tests.physical_helpers import physical_config, two_location_fixture
from tests.unit.test_v2_flag_defaults import _base
from world._skills import SkillDomain, default_objective_skill_policy
from world._teaching import default_teaching_interaction_policy
from world.actions import Help, Search, Talk
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId
from world.models import PhysicalRules

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _quantize(value: float) -> float:
    return round(value / 1e-6) * 1e-6


def _engine(*, teaching: bool) -> WorldEngine:
    fixture = two_location_fixture(item_on_ground=False)
    return WorldEngine(
        config=physical_config(9, rules=PhysicalRules(search_base_probability=1.0)),
        bootstrap=fixture.as_bootstrap(),
        skill_policy=default_objective_skill_policy(),
        skill_entity_ids=(EntityId("body-1"), EntityId("body-2")),
        teaching_policy=default_teaching_interaction_policy() if teaching else None,
        teaching_entity_ids=(
            (EntityId("body-1"), EntityId("body-2")) if teaching else ()
        ),
    )


def _submit(engine: WorldEngine, agent: str, command: object) -> None:
    batch = engine.observe()
    engine.resolve_tick((ActionSubmission(batch.token, AgentId(agent), command),))


def _talk(predicate: str, obj: str, communication_id: str) -> Talk:
    return Talk(
        EntityId("body-2"),
        origin_utterance(
            text="public",
            speaker_id=EntityId("body-1"),
            communication_id=communication_id,
            relations=(
                CommunicationRelation(subject="skill", predicate=predicate, object=obj),
            ),
        ),
    )


def _level(engine: WorldEngine, body: str, domain: SkillDomain) -> float:
    ledger = engine._skill_ledger
    assert ledger is not None
    return ledger.level(EntityId(body), domain)


def test_explain_leaves_objective_until_a_demonstration() -> None:
    engine = _engine(teaching=True)
    _submit(engine, "agent-1", _talk("explain", "foraging:high", "comm-ex"))
    assert _level(engine, "body-2", SkillDomain.FORAGING) == 0.0
    _submit(engine, "agent-1", _talk("demonstrate", "foraging", "comm-demo"))
    assert _level(engine, "body-2", SkillDomain.FORAGING) == 0.0
    _submit(engine, "agent-1", Search())
    assert _level(engine, "body-2", SkillDomain.FORAGING) > 0.0


def test_specialization_moves_mass_toward_the_practiced_domain() -> None:
    taught = _engine(teaching=True)
    plain = _engine(teaching=False)
    for engine in (taught, plain):
        _submit(engine, "agent-1", Search())
        _submit(engine, "agent-2", Help(EntityId("body-1")))
        _submit(engine, "agent-1", _talk("demonstrate", "foraging", "comm-spec"))
        _submit(engine, "agent-1", _talk("practice_together", "foraging", "comm-joint"))
        batch = engine.observe()
        engine.resolve_tick(
            (
                ActionSubmission(batch.token, AgentId("agent-1"), Search()),
                ActionSubmission(batch.token, AgentId("agent-2"), Search()),
            )
        )
    assert _level(taught, "body-1", SkillDomain.FORAGING) > _level(
        plain, "body-1", SkillDomain.FORAGING
    )
    assert _level(taught, "body-2", SkillDomain.HEALING) == _level(
        plain, "body-2", SkillDomain.HEALING
    )
    assert _level(taught, "body-2", SkillDomain.FORAGING) > _level(
        plain, "body-2", SkillDomain.FORAGING
    )
    peaked = compute_cultural_transmission(
        (
            TeachingAudit(
                agent_id=AgentId("agent-1"),
                store=TeachingAuditStore.OBJECTIVE,
                token="foraging",
                band_or_level=format(_quantize(0.8), ".6f"),
                tick=1,
                domain="foraging",
            ),
        ),
        (),
    )
    mixed = compute_cultural_transmission(
        (
            TeachingAudit(
                agent_id=AgentId("agent-1"),
                store=TeachingAuditStore.OBJECTIVE,
                token="foraging",
                band_or_level=format(_quantize(0.4), ".6f"),
                tick=1,
                domain="foraging",
            ),
            TeachingAudit(
                agent_id=AgentId("agent-1"),
                store=TeachingAuditStore.OBJECTIVE,
                token="healing",
                band_or_level=format(_quantize(0.4), ".6f"),
                tick=1,
                domain="healing",
            ),
        ),
        (),
    )
    assert peaked.normalized_entropy is not None
    assert mixed.normalized_entropy is not None
    assert peaked.normalized_entropy < mixed.normalized_entropy


def test_metric_counts_misinformation_without_guessing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = (_ROOT / "src/analysis/cultural_transmission_metrics.py").read_text()
    assert "fold_teaching_opportunities" not in source
    assert "apply_teaching_belief" not in source
    teaching = (_ROOT / "src/world/_teaching.py").read_text()
    assert "cultural_transmission_metrics" not in teaching
    advice = (_ROOT / "src/agents/cognition/teaching.py").read_text()
    assert "cultural_transmission_metrics" not in advice
    believed = format(_quantize(0.08 / 1.08), ".6f")
    rows = (
        TeachingAudit(
            agent_id=AgentId("agent-2"),
            store=TeachingAuditStore.ADVICE,
            token="explain",
            band_or_level="high",
            tick=1,
            domain="foraging",
            source_agent_id=AgentId("agent-1"),
        ),
        TeachingAudit(
            agent_id=AgentId("agent-2"),
            store=TeachingAuditStore.BELIEF,
            token="foraging",
            band_or_level=believed,
            tick=2,
            domain="foraging",
        ),
        TeachingAudit(
            agent_id=AgentId("agent-2"),
            store=TeachingAuditStore.OBJECTIVE,
            token="foraging",
            band_or_level=format(_quantize(0.0), ".6f"),
            tick=1,
            domain="foraging",
        ),
        TeachingAudit(
            agent_id=AgentId("agent-1"),
            store=TeachingAuditStore.OBJECTIVE,
            token="foraging",
            band_or_level=format(_quantize(0.0), ".6f"),
            tick=1,
            domain="foraging",
        ),
        TeachingAudit(
            agent_id=AgentId("agent-2"),
            store=TeachingAuditStore.ADVICE,
            token="demonstrate",
            band_or_level="unspecified",
            tick=3,
            domain="foraging",
            source_agent_id=AgentId("agent-1"),
        ),
    )
    caplog.set_level(logging.DEBUG, logger="analysis.cultural_transmission_metrics")
    result = compute_cultural_transmission(rows, ())
    assert CULTURAL_TRANSMISSION_METRIC_VERSION == "cultural_transmission@1"
    assert result.advice_count == 2
    assert result.belief_matches_advice == 0
    assert result.misinformation_count == 1
    assert result.objective_gains_without_practice == 0
    assert "advice_count=2" in caplog.text
    assert "misinformation_count=1" in caplog.text
    missing = compute_cultural_transmission(rows[:1], None)
    assert missing.misinformation_count == 0
    assert missing.unmatched_count > 0
    assert missing.availability == "unknown"


def test_experiments_share_identity_and_stay_off_the_v1_gate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    base = _base()
    caplog.set_level(logging.INFO, logger="experiments.catalog")
    cultural = experiment_s_cultural_transmission(base)
    specialization = experiment_t_skill_specialization(base)
    assert cultural.experiment_id == "experiment-s-cultural-transmission"
    assert specialization.experiment_id == "experiment-t-skill-specialization"
    for definition in (cultural, specialization):
        disabled, enabled = definition.conditions
        assert disabled.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V11
        assert enabled.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V12
        assert disabled.runner_config.seed == enabled.runner_config.seed
        assert (
            disabled.runner_config.stochastic_identity
            == enabled.runner_config.stochastic_identity
        )
        assert disabled.runner_config.scenario == enabled.runner_config.scenario
        assert all(
            agent.cognition.skill_learning_mode.value == "deterministic"
            for agent in disabled.runner_config.agents
        )
        assert all(
            agent.cognition.teaching_interaction_mode.value == "disabled"
            for agent in disabled.runner_config.agents
        )
        assert all(
            agent.cognition.teaching_interaction_mode.value == "deterministic"
            for agent in enabled.runner_config.agents
        )
        profiled = v1_regression_profile(disabled.runner_config)
        assert profiled.schema_version != RUNNER_SCHEMA_VERSION_V12
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "experiment_s_built" in messages
    assert "experiment_t_built" in messages
    assert "teaching_mode=deterministic" in messages
    gate = (_ROOT / "tests/unit/test_v1_regression_gate.py").read_text()
    assert "experiment_s_cultural_transmission" not in gate
    assert "experiment_t_skill_specialization" not in gate


@pytest.mark.asyncio
async def test_two_runner_invocations_match_audits() -> None:
    definition = experiment_s_cultural_transmission(_base())
    enabled = definition.conditions[1].runner_config
    enabled = replace(enabled, stop_policy=replace(enabled.stop_policy, max_ticks=1))

    async def _run(run_id: str):
        async with await SimulationRunner.from_config(
            enabled, run_id=RunId(run_id)
        ) as runner:
            return await runner.run()

    left = await _run("run-culture-a")
    right = await _run("run-culture-b")
    assert left.teaching_audits == right.teaching_audits
