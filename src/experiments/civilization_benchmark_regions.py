"""Bounded v55 compositions for benchmark cases 18-20 (regions and contact).

Journeys use the ordinary WorldEngine route commands. Contact is co-presence
evidence, not a polity, border, or shared culture. No coordinate is used.
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
    V3_BENCH_18_REGIONAL_MIGRATION,
    V3_BENCH_19_ISOLATED_DIVERGENCE,
    V3_BENCH_20_RECONTACT_EXCHANGE,
)
from experiments.interventions import (
    MilestoneInterventionArbiter,
    MilestoneOverride,
)
from simulation.runner_models import (
    KnowledgeGenealogySpec,
    SimulationRunnerConfig,
    example_knowledge_genealogy_spec,
)
from world.actions import Move, Tell, Wait
from world.communications import CommunicationRelation, origin_utterance
from world.contact import ContactMode, CulturalContactSpec
from world.identifiers import EntityId
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_regions"
)

REGION_BENCHMARK_IDS: Final[tuple[str, ...]] = (
    V3_BENCH_18_REGIONAL_MIGRATION,
    V3_BENCH_19_ISOLATED_DIVERGENCE,
    V3_BENCH_20_RECONTACT_EXCHANGE,
)

_SPRING_AGENT_ID: Final[str] = "agent-spring"
_SPRING_BODY_ID: Final[str] = "body-spring"
_GRAIN_AGENT_ID: Final[str] = "agent-grain"
_GRAIN_BODY_ID: Final[str] = "body-grain"
_ORIGIN_AGENT_ID: Final[str] = "agent-origin"


def _contact() -> CulturalContactSpec:
    return CulturalContactSpec(mode=ContactMode.DETERMINISTIC)


def _teaching_genealogy() -> KnowledgeGenealogySpec:
    return example_knowledge_genealogy_spec(
        independent_discovery=True,
        teaching=True,
    )


def _isolated_regions(horizon_ticks: int | None = None) -> RegionsMigrationSpec:
    """Two region clusters with no joining route; intra-cluster routes remain."""
    origin, spring, crossroads = (
        EntityId("loc-origin"),
        EntityId("loc-spring"),
        EntityId("loc-crossroads"),
    )
    grain, remote = EntityId("loc-grain"), EntityId("loc-remote")
    return RegionsMigrationSpec(
        regions=(
            RegionDefinition(region_id="north-a", label="NorthA"),
            RegionDefinition(region_id="dryland-b", label="DrylandB"),
        ),
        location_regions=(
            LocationRegion(location_id=origin, region_id="north-a"),
            LocationRegion(location_id=spring, region_id="north-a"),
            LocationRegion(location_id=crossroads, region_id="north-a"),
            LocationRegion(location_id=grain, region_id="dryland-b"),
            LocationRegion(location_id=remote, region_id="dryland-b"),
        ),
        routes=(
            RouteSpec(origin, spring, duration_ticks=2, fatigue_cost=3.0),
            RouteSpec(spring, crossroads, duration_ticks=1, fatigue_cost=2.0),
            RouteSpec(grain, remote, duration_ticks=4, fatigue_cost=7.0),
            RouteSpec(
                crossroads,
                grain,
                duration_ticks=(horizon_ticks or 8) + 1,
                fatigue_cost=7.0,
            ),
        ),
        max_arrival_wait_ticks=8,
        residence_min_ticks=4,
        destination_memory_limit=4,
        destination_hop_limit=4,
        cognition_mode=CognitionMode.DETERMINISTIC,
    )


def _recontact_regions(spec: RegionsMigrationSpec) -> RegionsMigrationSpec:
    """Make the north->dryland crossing a real multi-tick journey."""
    routes = []
    for route in spec.routes:
        if route.edge_key == ("loc-crossroads", "loc-spring"):
            routes.append(replace(route, duration_ticks=4))
        else:
            routes.append(route)
    return replace(spec, routes=tuple(routes))


def _region_config(
    scenario_id: str, base: SimulationRunnerConfig
) -> SimulationRunnerConfig:
    if scenario_id == V3_BENCH_18_REGIONAL_MIGRATION:
        return base
    if scenario_id == V3_BENCH_19_ISOLATED_DIVERGENCE:
        return replace(
            base,
            regions_migration=_isolated_regions(base.stop_policy.max_ticks),
            cultural_contact=_contact(),
        )
    if scenario_id == V3_BENCH_20_RECONTACT_EXCHANGE:
        spec = base.regions_migration
        assert spec is not None
        return replace(
            base,
            regions_migration=_recontact_regions(spec),
            cultural_contact=_contact(),
            knowledge_genealogy=_teaching_genealogy(),
        )
    raise V3BenchmarkError(
        "unknown_scenario", f"not a region benchmark: {scenario_id!r}"
    )


def build_region_benchmark(
    scenario_id: str,
    *,
    seed: int | None = None,
    profile: V3BenchmarkProfile = V3BenchmarkProfile.SMOKE,
    lane: V3BenchmarkLane = V3BenchmarkLane.RESEARCH,
) -> V3BenchmarkScenarioBuild:
    """Materialize one Phase 5 regional/contact case."""
    if scenario_id not in REGION_BENCHMARK_IDS:
        raise V3BenchmarkError(
            "unknown_scenario", f"not a region benchmark: {scenario_id!r}"
        )
    build = build_v3_benchmark_scenario(
        scenario_id, seed=seed, profile=profile, lane=lane
    )
    config = _region_config(scenario_id, build.arms[0].config)
    arms = tuple(replace(arm, config=config) for arm in build.arms)
    result = replace(build, arms=arms)
    _LOG.debug(
        "region_benchmark_built scenario_id=%s lane=%s profile=%s "
        "contact=%s genealogy=%s route_count=%s",
        scenario_id,
        lane.value,
        profile.value,
        config.cultural_contact is not None,
        config.knowledge_genealogy is not None,
        len(config.regions_migration.routes) if config.regions_migration else 0,
    )
    return result


def _wait(agent_id: str, tick: int, label: str) -> MilestoneOverride:
    return MilestoneOverride(
        milestone_id=f"v3-bench-{label}-wait-{tick:04d}",
        tick=tick,
        agent_id=AgentId(agent_id),
        build_command=lambda: Wait(),
    )


def _teaching_command() -> Tell:
    utterance = origin_utterance(
        text="shared practice",
        speaker_id=EntityId(_SPRING_BODY_ID),
        communication_id="v3-bench-recontact-teach",
        concepts=("practice",),
        relations=(
            CommunicationRelation(
                subject="speaker",
                predicate="explain",
                object="crafting:high",
            ),
        ),
    )
    return Tell(recipient_id=EntityId(_GRAIN_BODY_ID), utterance=utterance)


def region_benchmark_arbiter(
    scenario_id: str, config: SimulationRunnerConfig
) -> MilestoneInterventionArbiter | None:
    """Schedule ordinary journeys, waits and one addressed teaching delivery."""
    if scenario_id not in REGION_BENCHMARK_IDS:
        return None
    origin = AgentId(_ORIGIN_AGENT_ID)
    spring = AgentId(_SPRING_AGENT_ID)
    grain = AgentId(_GRAIN_AGENT_ID)
    milestones: list[MilestoneOverride] = []
    if scenario_id == V3_BENCH_18_REGIONAL_MIGRATION:
        milestones.extend(
            (
                MilestoneOverride(
                    milestone_id="v3-bench-migration-journey",
                    tick=0,
                    agent_id=origin,
                    build_command=lambda: Move(destination_id=EntityId("loc-spring")),
                ),
                _wait(_ORIGIN_AGENT_ID, 1, "migration"),
                _wait(_ORIGIN_AGENT_ID, 2, "migration"),
            )
        )
    elif scenario_id == V3_BENCH_19_ISOLATED_DIVERGENCE:
        milestones.extend(
            (
                MilestoneOverride(
                    milestone_id="v3-bench-isolation-local-journey",
                    tick=0,
                    agent_id=spring,
                    build_command=lambda: Move(
                        destination_id=EntityId("loc-crossroads")
                    ),
                ),
                _wait(_SPRING_AGENT_ID, 1, "isolation"),
                MilestoneOverride(
                    milestone_id="v3-bench-isolation-cross-region",
                    tick=2,
                    agent_id=spring,
                    build_command=lambda: Move(destination_id=EntityId("loc-grain")),
                ),
            )
        )
    else:
        milestones.extend(
            (
                MilestoneOverride(
                    milestone_id="v3-bench-recontact-journey-north",
                    tick=0,
                    agent_id=spring,
                    build_command=lambda: Move(
                        destination_id=EntityId("loc-crossroads")
                    ),
                ),
                MilestoneOverride(
                    milestone_id="v3-bench-recontact-journey-dryland",
                    tick=0,
                    agent_id=grain,
                    build_command=lambda: Move(
                        destination_id=EntityId("loc-crossroads")
                    ),
                ),
                _wait(_SPRING_AGENT_ID, 5, "recontact-north"),
                _wait(_GRAIN_AGENT_ID, 4, "recontact-dryland"),
                _wait(_GRAIN_AGENT_ID, 5, "recontact-dryland"),
                MilestoneOverride(
                    milestone_id="v3-bench-recontact-teach",
                    tick=6,
                    agent_id=spring,
                    build_command=_teaching_command,
                ),
            )
        )
    _LOG.debug(
        "region_arbiter_ready scenario_id=%s milestone_count=%s",
        scenario_id,
        len(milestones),
    )
    return MilestoneInterventionArbiter(
        tuple(milestones), override_budget=len(milestones)
    )


def required_region_milestones(scenario_id: str) -> tuple[str, ...]:
    if scenario_id == V3_BENCH_18_REGIONAL_MIGRATION:
        return ("v3-bench-migration-journey",)
    if scenario_id == V3_BENCH_19_ISOLATED_DIVERGENCE:
        return ("v3-bench-isolation-local-journey",)
    if scenario_id == V3_BENCH_20_RECONTACT_EXCHANGE:
        return (
            "v3-bench-recontact-journey-north",
            "v3-bench-recontact-journey-dryland",
            "v3-bench-recontact-teach",
        )
    return ()


def _window_complete(probe: BenchmarkBoundaryProbe, boundary_end_tick: int) -> bool:
    observations = probe.observations
    return (
        bool(observations)
        and observations[-1].boundary_tick == boundary_end_tick
        and not probe.failures
    )


def _event_ref(kind: str) -> V3BenchmarkSourceReference:
    return V3BenchmarkSourceReference(
        source_kind=V3BenchmarkSourceKind.OBJECTIVE_INSPECTION,
        reference_id=f"event-kind:{kind}",
    )


def _disabled(selector: str, reason: str) -> V3BenchmarkCheck:
    return V3BenchmarkCheck(
        selector_id=selector,
        selector_version=1,
        status=V3BenchmarkCheckStatus.UNEXECUTED,
        reason_code=reason,
        evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
        coverage=V3BenchmarkCoverage.NOT_EXERCISED,
        source_references=(),
    )


def _partial(selector: str, boundary_end_tick: int) -> V3BenchmarkCheck:
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


def evaluate_migration(
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Require an engine journey start and a committed arrival or pending wait."""
    selector = "migration_evidence"
    if not mechanism_available:
        return _disabled(selector, "regions_migration_disabled")
    if not _window_complete(probe, boundary_end_tick):
        return _partial(selector, boundary_end_tick)
    started = probe.event_total("JourneyStarted")
    if started < 1:
        return V3BenchmarkCheck(
            selector_id=selector,
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_journey_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=0,
            denominator=1,
        )
    arrived = probe.event_total("JourneyArrived")
    ended = probe.event_total("JourneyEnded")
    return V3BenchmarkCheck(
        selector_id=selector,
        selector_version=1,
        status=V3BenchmarkCheckStatus.PASS,
        reason_code=(
            "journey_arrived"
            if arrived > 0
            else ("journey_ended_without_arrival" if ended > 0 else "journey_pending")
        ),
        evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=(
            _event_ref("JourneyStarted"),
            _event_ref("JourneyArrived"),
        ),
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=arrived,
        denominator=started,
    )


def evaluate_cultural_contact(
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Zero contact over a complete window is a valid isolation null result."""
    selector = "cultural_contact_evidence"
    if not mechanism_available:
        return _disabled(selector, "cultural_contact_disabled")
    if not _window_complete(probe, boundary_end_tick):
        return _partial(selector, boundary_end_tick)
    contacts = probe.event_total("ContactRecorded")
    return V3BenchmarkCheck(
        selector_id=selector,
        selector_version=1,
        status=V3BenchmarkCheckStatus.PASS,
        reason_code=("contact_observed" if contacts > 0 else "no_contact_observed"),
        evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=(_event_ref("ContactRecorded"),),
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=contacts,
        denominator=max(contacts, 1),
    )


__all__ = [
    "REGION_BENCHMARK_IDS",
    "build_region_benchmark",
    "evaluate_cultural_contact",
    "evaluate_migration",
    "region_benchmark_arbiter",
    "required_region_milestones",
]
