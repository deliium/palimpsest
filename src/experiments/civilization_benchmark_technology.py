"""Bounded v55 compositions for benchmark cases 08-11 (technology).

The recipes declare physical operands, experimentation laws and lineage
channels only. They never seed a technique ledger, install a global technique
registry, or treat equal content keys as shared ancestry. Every knowledge entry
in these fixtures must come from an applied command result and the ordinary
owner-scoped acquisition path.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Final

from agents.models import AgentId
from analysis.technique_lifecycle import (
    TechniqueLifecycleState,
    classify_technique_lifecycle,
)
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
    V3_BENCH_08_TECHNOLOGY_DISCOVERY,
    V3_BENCH_09_TECHNOLOGY_DIFFUSION,
    V3_BENCH_10_TECHNOLOGY_LOSS,
    V3_BENCH_11_TECHNOLOGY_REDISCOVERY,
)
from experiments.interventions import (
    MilestoneInterventionArbiter,
    MilestoneOverride,
)
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
    NewAgentInitializationSpec,
    default_new_agent_initialization_spec,
)
from simulation.runner_models import (
    BoundedExperimentationSpec,
    ExperimentLaw,
    KnowledgeGenealogySpec,
    SimulationRunnerConfig,
    TechniqueLifecycleSpec,
    example_bounded_experimentation_spec,
    example_durable_records_spec,
    example_experiment_law,
    example_knowledge_genealogy_spec,
    example_knowledge_repositories_spec,
    example_mentorship_spec,
    example_technique_lifecycle_spec,
)
from world.actions import Craft, Experiment, Inscribe, Wait
from world.artifacts import ArtifactContent, ArtifactKind, DurableRecordGenre
from world.experimentation import ExperimentOperator, ExperimentProcessToken
from world.identifiers import EntityId, RecipeId
from world.models import Item, Resource
from world.production import example_production_catalog
from world.values import DayPhase, Hunger, ItemKind, ItemLoad, ResourceKind, Thirst

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_technology"
)

TECHNOLOGY_BENCHMARK_IDS: Final[tuple[str, ...]] = (
    V3_BENCH_08_TECHNOLOGY_DISCOVERY,
    V3_BENCH_09_TECHNOLOGY_DIFFUSION,
    V3_BENCH_10_TECHNOLOGY_LOSS,
    V3_BENCH_11_TECHNOLOGY_REDISCOVERY,
)

_FOUNDER_AGENT_ID: Final[str] = "agent-origin"
_DISCOVERY_LOCATION_ID: Final[str] = "loc-origin"
_DISCOVERY_HYPOTHESIS_ID: Final[str] = "hyp:v3-bench-technology"
_RECORD_MARKS: Final[tuple[str, ...]] = ("proposition_bench_technique",)
_TRANSMISSION_ORIGINS: Final[frozenset[str]] = frozenset(
    {"teaching", "written_record", "developmental", "imitation"}
)


def material_operand_ids(location_id: str) -> tuple[EntityId, EntityId]:
    """Declared ground item and resource ids for one spawn location."""
    return (
        EntityId(f"item-bench-material-{location_id}"),
        EntityId(f"resource-bench-material-{location_id}"),
    )


def _with_material_opportunities(
    config: SimulationRunnerConfig, *, held_body_ids: tuple[str, ...]
) -> SimulationRunnerConfig:
    """Add physical operands at spawn locations without installing knowledge."""
    scenario = config.scenario
    names = {location.entity_id.value for location in scenario.locations}
    items = list(scenario.items)
    resources = list(scenario.resources)
    bodies = list(scenario.bodies)
    existing_items = {item.entity_id.value for item in items}
    existing_resources = {resource.entity_id.value for resource in resources}
    held_ids = frozenset(held_body_ids)

    def _add_item(
        item_id: EntityId,
        name: str,
        *,
        location_id: str | None,
        holder_id: str | None,
    ) -> None:
        if item_id.value in existing_items:
            return
        items.append(
            Item(
                entity_id=item_id,
                name=name,
                kind=ItemKind.MATERIAL,
                load=ItemLoad(1),
                location_id=None if location_id is None else EntityId(location_id),
                holder_id=None if holder_id is None else EntityId(holder_id),
            )
        )
        existing_items.add(item_id.value)

    for location_id in sorted(names):
        item_id, resource_id = material_operand_ids(location_id)
        _add_item(
            item_id,
            f"Bench material at {location_id}",
            location_id=location_id,
            holder_id=None,
        )
        _add_item(
            EntityId(f"item-bench-wood-{location_id}"),
            "wood",
            location_id=location_id,
            holder_id=None,
        )
        _add_item(
            EntityId(f"item-bench-stone-{location_id}"),
            "stone",
            location_id=location_id,
            holder_id=None,
        )
        if resource_id.value not in existing_resources:
            resources.append(
                Resource(
                    entity_id=resource_id,
                    name=f"Bench material node at {location_id}",
                    kind=ResourceKind.MATERIAL,
                    location_id=EntityId(location_id),
                    quantity=8.0,
                    maximum_quantity=8.0,
                    regeneration_per_tick=0.0,
                    unit="units",
                )
            )
            existing_resources.add(resource_id.value)
    for body_index, body in enumerate(bodies):
        if body.entity_id.value not in held_ids:
            continue
        wood_id = EntityId(f"item-bench-wood-held-{body.entity_id.value}")
        stone_id = EntityId(f"item-bench-stone-held-{body.entity_id.value}")
        _add_item(wood_id, "wood", location_id=None, holder_id=body.entity_id.value)
        _add_item(stone_id, "stone", location_id=None, holder_id=body.entity_id.value)
        bodies[body_index] = replace(
            body,
            hunger=Hunger(0.0),
            thirst=Thirst(0.0),
            inventory=(*body.inventory, wood_id, stone_id),
        )
    return replace(
        config,
        scenario=replace(
            scenario,
            items=tuple(items),
            resources=tuple(resources),
            bodies=tuple(bodies),
        ),
    )


def _learner_initializer() -> NewAgentInitializationSpec:
    return replace(
        default_new_agent_initialization_spec(),
        species_defaults_id=SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
    )


def _success_experiment_law() -> ExperimentLaw:
    return example_experiment_law(
        outcome_class="success",
        delta="none",
        product_id="",
    )


def _experimentation() -> BoundedExperimentationSpec:
    return example_bounded_experimentation_spec(
        laws=(_success_experiment_law(),),
        learn_into_genealogy=True,
        repeat_threshold=2,
    )


def _genealogy(*, teaching: bool, written_record: bool) -> KnowledgeGenealogySpec:
    base = example_knowledge_genealogy_spec(
        independent_discovery=True,
        teaching=teaching,
    )
    return replace(
        base,
        uptake_compose=replace(
            base.uptake_compose,
            written_record=written_record,
        ),
    )


def _lifecycle() -> TechniqueLifecycleSpec:
    return example_technique_lifecycle_spec(
        diffusion_window_ticks=4,
        rare_max=1,
        rediscovery_latch_ticks=2,
    )


def _technology_config(
    scenario_id: str, base: SimulationRunnerConfig
) -> SimulationRunnerConfig:
    catalog = example_production_catalog()
    agents = tuple(
        replace(
            agent,
            cognition=replace(agent.cognition, production_catalog=catalog),
        )
        for agent in base.agents
    )
    base = replace(base, agents=agents)
    if scenario_id == V3_BENCH_08_TECHNOLOGY_DISCOVERY:
        return replace(
            base,
            bounded_experimentation=_experimentation(),
            knowledge_genealogy=_genealogy(teaching=False, written_record=False),
            technique_lifecycle=_lifecycle(),
            new_agent_initialization=_learner_initializer(),
        )
    if scenario_id == V3_BENCH_09_TECHNOLOGY_DIFFUSION:
        return replace(
            base,
            bounded_experimentation=_experimentation(),
            knowledge_genealogy=_genealogy(teaching=True, written_record=True),
            technique_lifecycle=_lifecycle(),
            mentorship=example_mentorship_spec(),
            durable_records=example_durable_records_spec(default_fidelity="perfect"),
            new_agent_initialization=_learner_initializer(),
        )
    if scenario_id == V3_BENCH_10_TECHNOLOGY_LOSS:
        return replace(
            base,
            bounded_experimentation=_experimentation(),
            knowledge_genealogy=_genealogy(teaching=False, written_record=False),
            technique_lifecycle=_lifecycle(),
            durable_records=example_durable_records_spec(default_fidelity="perfect"),
            knowledge_repositories=example_knowledge_repositories_spec(),
            new_agent_initialization=_learner_initializer(),
        )
    if scenario_id == V3_BENCH_11_TECHNOLOGY_REDISCOVERY:
        return replace(
            base,
            bounded_experimentation=_experimentation(),
            knowledge_genealogy=_genealogy(teaching=False, written_record=False),
            technique_lifecycle=_lifecycle(),
            new_agent_initialization=_learner_initializer(),
        )
    raise V3BenchmarkError(
        "unknown_scenario", f"not a technology benchmark: {scenario_id!r}"
    )


def build_technology_benchmark(
    scenario_id: str,
    *,
    seed: int | None = None,
    profile: V3BenchmarkProfile = V3BenchmarkProfile.SMOKE,
    lane: V3BenchmarkLane = V3BenchmarkLane.RESEARCH,
) -> V3BenchmarkScenarioBuild:
    """Materialize one Phase 4 technology case."""
    if scenario_id not in TECHNOLOGY_BENCHMARK_IDS:
        raise V3BenchmarkError(
            "unknown_scenario", f"not a technology benchmark: {scenario_id!r}"
        )
    build = build_v3_benchmark_scenario(
        scenario_id, seed=seed, profile=profile, lane=lane
    )
    held = (_FOUNDER_AGENT_ID,)
    held_bodies = tuple(
        agent.entity_id.value
        for agent in build.arms[0].config.agents
        if agent.agent_id.value in held
    )
    base = _with_material_opportunities(build.arms[0].config, held_body_ids=held_bodies)
    config = _technology_config(scenario_id, base)
    founder_ids = tuple(agent.agent_id.value for agent in config.agents)
    arms = tuple(
        replace(arm, config=config, founder_ids=founder_ids) for arm in build.arms
    )
    result = replace(build, arms=arms)
    _LOG.debug(
        "technology_benchmark_built scenario_id=%s lane=%s profile=%s "
        "experimentation=%s genealogy=%s lifecycle=%s",
        scenario_id,
        lane.value,
        profile.value,
        config.bounded_experimentation is not None,
        config.knowledge_genealogy is not None,
        config.technique_lifecycle is not None,
    )
    return result


def _experiment_command() -> Experiment:
    """One deliberate combine trial using declared physical operands."""
    item_id, resource_id = material_operand_ids(_DISCOVERY_LOCATION_ID)
    return Experiment(
        operator=ExperimentOperator.COMBINE,
        operand_a_id=item_id,
        operand_b_id=resource_id,
        process_token=ExperimentProcessToken.NONE,
        hypothesis_id=_DISCOVERY_HYPOTHESIS_ID,
    )


def _invalid_experiment_command() -> Experiment:
    """A syntactically valid trial whose operands are absent from the world."""
    return Experiment(
        operator=ExperimentOperator.COMBINE,
        operand_a_id=EntityId("item-bench-absent"),
        operand_b_id=EntityId("resource-bench-absent"),
        process_token=ExperimentProcessToken.NONE,
        hypothesis_id=_DISCOVERY_HYPOTHESIS_ID,
    )


def _inscribe_command() -> Inscribe:
    return Inscribe(
        kind=ArtifactKind.RECORD,
        content=ArtifactContent(marks=_RECORD_MARKS),
        record_genre=DurableRecordGenre.INSTRUCTION,
    )


def _entry_interval(config: SimulationRunnerConfig) -> int:
    lifecycle = config.population_lifecycle
    params = None if lifecycle is None else lifecycle.demographic_policy_params
    raw = {} if params is None else dict(params)
    interval = raw.get("interval_ticks", 8)
    return interval if type(interval) is int and interval >= 1 else 8


def _craft_command() -> Craft:
    """Practice the declared tool recipe with held physical inputs."""
    return Craft(recipe_id=RecipeId("craft_tool"))


def _wait_command() -> Wait:
    return Wait()


def technology_benchmark_arbiter(
    scenario_id: str, config: SimulationRunnerConfig
) -> MilestoneInterventionArbiter | None:
    """Schedule only declared ordinary commands; no ledger is seeded."""
    if scenario_id not in TECHNOLOGY_BENCHMARK_IDS:
        return None
    founder = AgentId(_FOUNDER_AGENT_ID)
    milestones: list[MilestoneOverride] = [
        MilestoneOverride(
            milestone_id="v3-bench-technology-practice",
            tick=0,
            agent_id=founder,
            build_command=_craft_command,
        ),
        MilestoneOverride(
            milestone_id="v3-bench-technology-practice-wait",
            tick=1,
            agent_id=founder,
            build_command=_wait_command,
        ),
    ]
    if scenario_id in {
        V3_BENCH_08_TECHNOLOGY_DISCOVERY,
        V3_BENCH_11_TECHNOLOGY_REDISCOVERY,
    }:
        milestones.extend(
            (
                MilestoneOverride(
                    milestone_id="v3-bench-technology-trial-0",
                    tick=2,
                    agent_id=founder,
                    build_command=_experiment_command,
                ),
                MilestoneOverride(
                    milestone_id="v3-bench-technology-trial-1",
                    tick=3,
                    agent_id=founder,
                    build_command=_experiment_command,
                ),
            )
        )
    if scenario_id == V3_BENCH_08_TECHNOLOGY_DISCOVERY:
        milestones.append(
            MilestoneOverride(
                milestone_id="v3-bench-technology-rejected-trial",
                tick=4,
                agent_id=founder,
                build_command=_invalid_experiment_command,
            )
        )
    if scenario_id == V3_BENCH_09_TECHNOLOGY_DIFFUSION:
        milestones.append(
            MilestoneOverride(
                milestone_id="v3-bench-technology-record",
                tick=2,
                agent_id=founder,
                build_command=_inscribe_command,
            )
        )
        entry_tick = _entry_interval(config)
        recipient = AgentId(f"entrant-{entry_tick:04d}-00")
        rules = config.scenario.physical_rules
        day_ticks = [
            tick
            for tick in range(entry_tick + 1, entry_tick + 9)
            if rules.day_phase_for_tick(tick) is DayPhase.DAY
        ]
        for index, tick in enumerate(day_ticks[:3]):
            milestones.append(
                MilestoneOverride(
                    milestone_id=(f"v3-bench-technology-recipient-wait-{index}"),
                    tick=tick,
                    agent_id=recipient,
                    build_command=_wait_command,
                )
            )
    budget = len(milestones)
    _LOG.debug(
        "technology_benchmark_arbiter_ready scenario_id=%s milestone_count=%s",
        scenario_id,
        budget,
    )
    return MilestoneInterventionArbiter(tuple(milestones), override_budget=budget)


def required_technology_milestones(scenario_id: str) -> tuple[str, ...]:
    """Milestone ids whose APPLIED acknowledgement the fixture requires."""
    if scenario_id == V3_BENCH_08_TECHNOLOGY_DISCOVERY:
        return (
            "v3-bench-technology-practice",
            "v3-bench-technology-trial-0",
            "v3-bench-technology-trial-1",
        )
    if scenario_id == V3_BENCH_09_TECHNOLOGY_DIFFUSION:
        return (
            "v3-bench-technology-practice",
            "v3-bench-technology-record",
        )
    if scenario_id == V3_BENCH_10_TECHNOLOGY_LOSS:
        return ("v3-bench-technology-practice",)
    if scenario_id == V3_BENCH_11_TECHNOLOGY_REDISCOVERY:
        return (
            "v3-bench-technology-practice",
            "v3-bench-technology-trial-0",
            "v3-bench-technology-trial-1",
        )
    return ()


def _window_complete(probe: BenchmarkBoundaryProbe, boundary_end_tick: int) -> bool:
    observations = probe.observations
    return (
        bool(observations)
        and observations[-1].boundary_tick == boundary_end_tick
        and not probe.failures
    )


def _audits(result: object) -> tuple[Any, ...]:
    rows = getattr(result, "practical_knowledge_audits", ()) or ()
    return tuple(rows)


def _origin_token(value: object) -> str | None:
    token = getattr(value, "value", value)
    return token if isinstance(token, str) else None


def _owner_ref(owner_id: str) -> V3BenchmarkSourceReference:
    return V3BenchmarkSourceReference(
        source_kind=V3BenchmarkSourceKind.SUBJECTIVE_DEBUG,
        reference_id=owner_id,
        owner_id=owner_id,
    )


def evaluate_knowledge_genealogy(
    probe: BenchmarkBoundaryProbe,
    result: object,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
    require_transmission: bool,
) -> V3BenchmarkCheck:
    """Measure real owner-scoped acquisition and, when required, delivery."""
    if not mechanism_available:
        return V3BenchmarkCheck(
            selector_id="knowledge_genealogy_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="knowledge_genealogy_disabled",
            evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
        )
    if not _window_complete(probe, boundary_end_tick):
        return V3BenchmarkCheck(
            selector_id="knowledge_genealogy_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="probe_unavailable",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
        )
    audits = _audits(result)
    owners = tuple(
        dict.fromkeys(
            audit.owner_id.value
            for audit in audits
            if getattr(audit, "owner_id", None) is not None
        )
    )
    sources = tuple(_owner_ref(owner) for owner in owners)
    if not audits:
        return V3BenchmarkCheck(
            selector_id="knowledge_genealogy_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_practical_knowledge_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=0,
            denominator=0,
        )
    if require_transmission:
        transmitted = [
            audit
            for audit in audits
            if _origin_token(getattr(audit, "origin", None)) in _TRANSMISSION_ORIGINS
            and getattr(audit, "hop_index", 0) >= 1
        ]
        if not transmitted:
            return V3BenchmarkCheck(
                selector_id="knowledge_genealogy_evidence",
                selector_version=1,
                status=V3BenchmarkCheckStatus.UNEXECUTED,
                reason_code="no_knowledge_transmission_observed",
                evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
                coverage=V3BenchmarkCoverage.NOT_EXERCISED,
                source_references=sources,
                boundary_start_tick=0,
                boundary_end_tick=boundary_end_tick,
                numerator=0,
                denominator=len(audits),
            )
        return V3BenchmarkCheck(
            selector_id="knowledge_genealogy_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.PASS,
            reason_code="knowledge_transmission_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=tuple(
                _owner_ref(owner)
                for owner in dict.fromkeys(
                    audit.owner_id.value for audit in transmitted
                )
            ),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=len(transmitted),
            denominator=len(audits),
        )
    return V3BenchmarkCheck(
        selector_id="knowledge_genealogy_evidence",
        selector_version=1,
        status=V3BenchmarkCheckStatus.PASS,
        reason_code="knowledge_lineage_retained",
        evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=sources,
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=len(owners),
        denominator=len(owners),
    )


def evaluate_technique_lifecycle(
    probe: BenchmarkBoundaryProbe,
    result: object,
    *,
    boundary_end_tick: int,
    spec: TechniqueLifecycleSpec | None,
) -> V3BenchmarkCheck:
    """Classify detached lifecycle states from measured audits and death ticks."""
    if spec is None:
        return V3BenchmarkCheck(
            selector_id="technique_lifecycle_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="technique_lifecycle_disabled",
            evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
        )
    if not _window_complete(probe, boundary_end_tick):
        return V3BenchmarkCheck(
            selector_id="technique_lifecycle_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="probe_unavailable",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
        )
    audits = _audits(result)
    if not audits:
        return V3BenchmarkCheck(
            selector_id="technique_lifecycle_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_practical_knowledge_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
        )
    rows = classify_technique_lifecycle(
        audits,
        as_of_tick=boundary_end_tick,
        spec=spec,
        death_ticks=probe.owner_death_ticks(),
    )
    global_rows = tuple(row for row in rows if row.scope == "global")
    keys = tuple(dict.fromkeys(row.content_key for row in global_rows))
    sources = tuple(
        _owner_ref(owner)
        for owner in dict.fromkeys(
            [
                *sorted(probe.living_owner_ids()),
                *(audit.owner_id.value for audit in audits),
            ]
        )
    )
    surviving_records = probe.event_total("ArtifactCreated") - probe.event_total(
        "ArtifactDestroyed"
    )
    rediscovered = [
        row for row in global_rows if row.state is TechniqueLifecycleState.REDISCOVERED
    ]
    lost = [
        row for row in global_rows if row.state is TechniqueLifecycleState.GLOBALLY_LOST
    ]
    holders = [row for row in global_rows if row.known_by_n > 0]

    def _check(
        *,
        status: V3BenchmarkCheckStatus,
        reason_code: str,
        evidence: V3BenchmarkEvidenceAvailability,
        numerator: int,
        denominator: int,
    ) -> V3BenchmarkCheck:
        return V3BenchmarkCheck(
            selector_id="technique_lifecycle_evidence",
            selector_version=1,
            status=status,
            reason_code=reason_code,
            evidence=evidence,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=sources,
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=numerator,
            denominator=denominator,
        )

    if rediscovered:
        _LOG.info("benchmark_technique_rediscovery content_keys=%s", len(rediscovered))
        return _check(
            status=V3BenchmarkCheckStatus.PASS,
            reason_code="technology_rediscovery_measured",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            numerator=len(rediscovered),
            denominator=len(keys),
        )
    if lost:
        if surviving_records > 0:
            return _check(
                status=V3BenchmarkCheckStatus.UNEXECUTED,
                reason_code="loss_censored",
                evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
                numerator=len(lost),
                denominator=len(keys),
            )
        return _check(
            status=V3BenchmarkCheckStatus.PASS,
            reason_code="technology_loss_measured",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            numerator=len(lost),
            denominator=len(keys),
        )
    if holders:
        return _check(
            status=V3BenchmarkCheckStatus.PASS,
            reason_code="technique_holders_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            numerator=len(holders),
            denominator=len(keys),
        )
    return _check(
        status=V3BenchmarkCheckStatus.UNEXECUTED,
        reason_code="technique_state_unresolved",
        evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
        numerator=0,
        denominator=len(keys),
    )


__all__ = [
    "TECHNOLOGY_BENCHMARK_IDS",
    "build_technology_benchmark",
    "evaluate_knowledge_genealogy",
    "evaluate_technique_lifecycle",
    "material_operand_ids",
    "required_technology_milestones",
    "technology_benchmark_arbiter",
]
