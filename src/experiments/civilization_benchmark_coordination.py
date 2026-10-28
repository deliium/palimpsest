"""Bounded v55 compositions for benchmark cases 16-17 (coordination).

The fixtures declare physical materials and ordinary project commands. They do
not appoint a leader, seed a crew, reward virtue, or label a free rider.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from agents.models import AgentId
from experiments.civilization_benchmark_base import (
    V3BenchmarkScenarioBuild,
    build_v3_benchmark_scenario,
)
from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheck,
    V3BenchmarkCheckStatus,
    V3BenchmarkCoverage,
    V3BenchmarkError,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkLane,
    V3BenchmarkProfile,
    V3BenchmarkSourceKind,
    V3BenchmarkSourceReference,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_16_COLLECTIVE_PROJECT,
    V3_BENCH_17_PUBLIC_GOOD_PATTERNS,
)
from experiments.interventions import (
    MilestoneInterventionArbiter,
    MilestoneOverride,
)
from simulation import canonical_admission_keys, derive_request_id
from simulation.models import RunId, SimulationRunConfig
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    CommunicationStrategyMode,
    SimulationRunnerConfig,
    SkillLearningMode,
    TeachingInteractionMode,
    example_collective_projects_spec,
    example_public_goods_spec,
)
from world.actions import (
    ContributeCollectiveProject,
    StartCollectiveProject,
    UsePublicGood,
    Wait,
)
from world.identifiers import EntityId
from world.models import AgentBody, Item, LifeStatus
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    TemperatureCelsius,
    Thirst,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_coordination"
)

COORDINATION_BENCHMARK_IDS: Final[tuple[str, ...]] = (
    V3_BENCH_16_COLLECTIVE_PROJECT,
    V3_BENCH_17_PUBLIC_GOOD_PATTERNS,
)

_ORIGIN_AGENT_ID: Final[str] = "agent-origin"
_ORIGIN_BODY_ID: Final[str] = "body-origin"
_EXTRA_AGENT_ID: Final[str] = "agent-extra-1"
_EXTRA_BODY_ID: Final[str] = "body-extra-1"
_SPECTATOR_AGENT_ID: Final[str] = "agent-extra-2"
_SPECTATOR_BODY_ID: Final[str] = "body-extra-2"
_LOCATION_ID: Final[str] = "loc-origin"


def _material(item_id: str, holder_id: str, name: str) -> Item:
    return Item(
        entity_id=EntityId(item_id),
        name=name,
        kind=ItemKind.MATERIAL,
        load=ItemLoad(1),
        holder_id=EntityId(holder_id),
    )


def _extra_body(body_id: str, inventory: tuple[str, ...]) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(body_id),
        location_id=EntityId(_LOCATION_ID),
        health=Health(100.0),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=tuple(EntityId(item) for item in inventory),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(12),
    )


def _extra_agent(agent_id: str, body_id: str) -> AgentRunnerSpec:
    return AgentRunnerSpec(
        agent_id=AgentId(agent_id),
        entity_id=EntityId(body_id),
        cognition=AgentCognitionSpec(
            agent_id=AgentId(agent_id),
            skill_learning_mode=SkillLearningMode.DETERMINISTIC,
            teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
            communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
        ),
        initial_goals=(),
    )


def _with_contributors(
    config: SimulationRunnerConfig, *, spectator: bool
) -> SimulationRunnerConfig:
    scenario = config.scenario
    bodies = []
    for body in scenario.bodies:
        if body.entity_id.value == _ORIGIN_BODY_ID:
            bodies.append(
                replace(
                    body,
                    location_id=EntityId(_LOCATION_ID),
                    hunger=Hunger(0.0),
                    thirst=Thirst(0.0),
                    inventory=(
                        EntityId("item-bench-wood-origin-0"),
                        EntityId("item-bench-stone-origin-0"),
                    ),
                )
            )
        else:
            bodies.append(body)
    existing = {body.entity_id.value for body in bodies}
    if _EXTRA_BODY_ID not in existing:
        bodies.append(
            _extra_body(
                _EXTRA_BODY_ID,
                ("item-bench-wood-extra-0", "item-bench-stone-extra-0"),
            )
        )
    if spectator and _SPECTATOR_BODY_ID not in existing:
        bodies.append(_extra_body(_SPECTATOR_BODY_ID, ()))
    items = list(scenario.items)
    present = {item.entity_id.value for item in items}
    declarations = [
        ("item-bench-wood-origin-0", _ORIGIN_BODY_ID, "wood"),
        ("item-bench-stone-origin-0", _ORIGIN_BODY_ID, "stone"),
        ("item-bench-stone-extra-0", _EXTRA_BODY_ID, "stone"),
        ("item-bench-wood-extra-0", _EXTRA_BODY_ID, "wood"),
    ]
    for item_id, holder, name in declarations:
        if item_id not in present:
            items.append(_material(item_id, holder, name))
    agents = list(config.agents)
    known = {agent.agent_id.value for agent in agents}
    if _EXTRA_AGENT_ID not in known:
        agents.append(_extra_agent(_EXTRA_AGENT_ID, _EXTRA_BODY_ID))
    if spectator and _SPECTATOR_AGENT_ID not in known:
        agents.append(_extra_agent(_SPECTATOR_AGENT_ID, _SPECTATOR_BODY_ID))
    return replace(
        config,
        scenario=replace(scenario, bodies=tuple(bodies), items=tuple(items)),
        agents=tuple(agents),
    )


def _coordination_config(
    scenario_id: str, base: SimulationRunnerConfig
) -> SimulationRunnerConfig:
    if scenario_id == V3_BENCH_16_COLLECTIVE_PROJECT:
        return replace(base, collective_projects=example_collective_projects_spec())
    if scenario_id == V3_BENCH_17_PUBLIC_GOOD_PATTERNS:
        return replace(
            base,
            collective_projects=example_collective_projects_spec(),
            public_goods=example_public_goods_spec(),
        )
    raise V3BenchmarkError(
        "unknown_scenario", f"not a coordination benchmark: {scenario_id!r}"
    )


def build_coordination_benchmark(
    scenario_id: str,
    *,
    seed: int | None = None,
    profile: V3BenchmarkProfile = V3BenchmarkProfile.SMOKE,
    lane: V3BenchmarkLane = V3BenchmarkLane.RESEARCH,
) -> V3BenchmarkScenarioBuild:
    """Materialize one Phase 5 coordination case."""
    if scenario_id not in COORDINATION_BENCHMARK_IDS:
        raise V3BenchmarkError(
            "unknown_scenario", f"not a coordination benchmark: {scenario_id!r}"
        )
    build = build_v3_benchmark_scenario(
        scenario_id, seed=seed, profile=profile, lane=lane
    )
    base = _with_contributors(
        build.arms[0].config,
        spectator=scenario_id == V3_BENCH_17_PUBLIC_GOOD_PATTERNS,
    )
    config = _coordination_config(scenario_id, base)
    founder_ids = tuple(agent.agent_id.value for agent in config.agents)
    arms = tuple(
        replace(arm, config=config, founder_ids=founder_ids) for arm in build.arms
    )
    result = replace(build, arms=arms)
    _LOG.debug(
        "coordination_benchmark_built scenario_id=%s lane=%s profile=%s "
        "projects=%s public_goods=%s",
        scenario_id,
        lane.value,
        profile.value,
        config.collective_projects is not None,
        config.public_goods is not None,
    )
    return result


def _ordinal(config: SimulationRunnerConfig, agent_id: AgentId) -> int:
    for index, agent in enumerate(config.agents):
        if agent.agent_id == agent_id:
            return index
    raise V3BenchmarkError("unknown_agent", f"agent {agent_id.value!r} missing")


def _wait(agent_id: str, tick: int, label: str) -> MilestoneOverride:
    return MilestoneOverride(
        milestone_id=f"v3-bench-{label}-wait-{tick:04d}",
        tick=tick,
        agent_id=AgentId(agent_id),
        build_command=lambda: Wait(),
    )


def project_id_for(
    config: SimulationRunnerConfig,
    *,
    run_id: RunId,
    tick: int,
    agent_id: AgentId,
) -> EntityId:
    """Reproduce the engine-owned project id without inspecting world state."""
    from simulation.clock import Tick

    run_config = SimulationRunConfig(
        seed=config.seed,
        physical_rules=config.resolve_physical_rules(),
        derivation_version=config.derivation_version,
        stochastic_identity=config.stochastic_identity,
    )
    keys = canonical_admission_keys(
        run_id=run_id,
        world_id=config.scenario.world_id,
        tick=Tick(tick),
        ordinal=_ordinal(config, agent_id),
        agent_id=agent_id,
    )
    return EntityId(f"project-{derive_request_id(run_config, 'admit', *keys).value}")


def coordination_benchmark_arbiter(
    scenario_id: str,
    config: SimulationRunnerConfig,
    *,
    run_id: RunId,
) -> MilestoneInterventionArbiter | None:
    """Start and contribute with ordinary commands; no leader is appointed."""
    if scenario_id not in COORDINATION_BENCHMARK_IDS:
        return None
    origin = AgentId(_ORIGIN_AGENT_ID)
    extra = AgentId(_EXTRA_AGENT_ID)
    kind = "shared_shelter" if scenario_id == V3_BENCH_16_COLLECTIVE_PROJECT else "well"
    material = "wood" if kind == "shared_shelter" else "stone"
    project_id = project_id_for(config, run_id=run_id, tick=0, agent_id=origin)
    milestones: list[MilestoneOverride] = [
        MilestoneOverride(
            milestone_id="v3-bench-project-start",
            tick=0,
            agent_id=origin,
            build_command=lambda: StartCollectiveProject(project_kind=kind),
        ),
        MilestoneOverride(
            milestone_id="v3-bench-project-contribute-origin-0",
            tick=1,
            agent_id=origin,
            build_command=lambda: ContributeCollectiveProject(
                project_id=project_id,
                item_id=EntityId(f"item-bench-{material}-origin-0"),
            ),
        ),
        MilestoneOverride(
            milestone_id="v3-bench-project-contribute-extra",
            tick=1,
            agent_id=extra,
            build_command=lambda: ContributeCollectiveProject(
                project_id=project_id,
                item_id=EntityId(f"item-bench-{material}-extra-0"),
            ),
        ),
        MilestoneOverride(
            milestone_id="v3-bench-project-contribute-origin-1",
            tick=2,
            agent_id=origin,
            build_command=lambda: ContributeCollectiveProject(
                project_id=project_id,
                item_id=None,
            ),
        ),
    ]
    if scenario_id == V3_BENCH_17_PUBLIC_GOOD_PATTERNS:
        spectator = AgentId(_SPECTATOR_AGENT_ID)
        milestones.extend(
            _wait(_SPECTATOR_AGENT_ID, tick, "spectator") for tick in range(4)
        )
        milestones.append(
            MilestoneOverride(
                milestone_id="v3-bench-public-good-benefit",
                tick=4,
                agent_id=spectator,
                build_command=lambda: UsePublicGood(project_id=project_id),
            )
        )
    _LOG.debug(
        "coordination_arbiter_ready scenario_id=%s milestone_count=%s",
        scenario_id,
        len(milestones),
    )
    return MilestoneInterventionArbiter(
        tuple(milestones), override_budget=len(milestones)
    )


def required_coordination_milestones(scenario_id: str) -> tuple[str, ...]:
    if scenario_id == V3_BENCH_16_COLLECTIVE_PROJECT:
        return (
            "v3-bench-project-start",
            "v3-bench-project-contribute-origin-0",
            "v3-bench-project-contribute-extra",
            "v3-bench-project-contribute-origin-1",
        )
    if scenario_id == V3_BENCH_17_PUBLIC_GOOD_PATTERNS:
        return (
            "v3-bench-project-start",
            "v3-bench-project-contribute-origin-0",
            "v3-bench-project-contribute-extra",
            "v3-bench-project-contribute-origin-1",
            "v3-bench-public-good-benefit",
        )
    return ()


def _window_complete(probe: BenchmarkBoundaryProbe, boundary_end_tick: int) -> bool:
    observations = probe.observations
    return (
        bool(observations)
        and observations[-1].boundary_tick == boundary_end_tick
        and not probe.failures
    )


def _event_ref(kind: str, tick: int) -> V3BenchmarkSourceReference:
    return V3BenchmarkSourceReference(
        source_kind=V3BenchmarkSourceKind.OBJECTIVE_INSPECTION,
        reference_id=f"event-kind:{kind}",
        tick=tick,
    )


def _unexecuted(selector: str, reason: str) -> V3BenchmarkCheck:
    return V3BenchmarkCheck(
        selector_id=selector,
        selector_version=1,
        status=V3BenchmarkCheckStatus.UNEXECUTED,
        reason_code=reason,
        evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
        coverage=V3BenchmarkCoverage.NOT_EXERCISED,
        source_references=(),
    )


def evaluate_collective_projects(
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Objective contributions and completion; never leadership or virtue."""
    selector = "collective_project_evidence"
    if not mechanism_available:
        return _unexecuted(selector, "collective_projects_disabled")
    if not _window_complete(probe, boundary_end_tick):
        return V3BenchmarkCheck(
            selector_id=selector,
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="probe_unavailable",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
        )
    created = probe.event_total("ProjectCreated")
    contributed = probe.event_total("ProjectContributed")
    if created < 1 or contributed < 2:
        return V3BenchmarkCheck(
            selector_id=selector,
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_project_contribution_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=contributed,
            denominator=max(created, 1),
        )
    completed = probe.event_total("ProjectCompleted")
    reasons = ("project_completed_observed", "project_open_observed")
    return V3BenchmarkCheck(
        selector_id=selector,
        selector_version=1,
        status=V3BenchmarkCheckStatus.PASS,
        reason_code=reasons[0] if completed else reasons[1],
        evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=(
            _event_ref("ProjectCreated", 0),
            _event_ref("ProjectContributed", boundary_end_tick),
        ),
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=completed,
        denominator=1,
    )


def evaluate_public_goods(
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """A benefit event is measured; it is not an access grant or a moral role."""
    selector = "public_goods_evidence"
    if not mechanism_available:
        return _unexecuted(selector, "public_goods_disabled")
    if not _window_complete(probe, boundary_end_tick):
        return V3BenchmarkCheck(
            selector_id=selector,
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="probe_unavailable",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
        )
    completed = probe.event_total("ProjectCompleted")
    if completed < 1:
        return V3BenchmarkCheck(
            selector_id=selector,
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_completed_project_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=0,
            denominator=1,
        )
    benefits = probe.event_total("PublicGoodBenefit")
    return V3BenchmarkCheck(
        selector_id=selector,
        selector_version=1,
        status=V3BenchmarkCheckStatus.PASS,
        reason_code=(
            "public_good_benefit_observed"
            if benefits > 0
            else "public_good_available_without_draw"
        ),
        evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=(
            _event_ref("ProjectCompleted", 0),
            _event_ref("PublicGoodBenefit", boundary_end_tick),
        ),
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=benefits,
        denominator=max(benefits, 1),
    )


__all__ = [
    "COORDINATION_BENCHMARK_IDS",
    "build_coordination_benchmark",
    "coordination_benchmark_arbiter",
    "evaluate_collective_projects",
    "evaluate_public_goods",
    "project_id_for",
    "required_coordination_milestones",
]
