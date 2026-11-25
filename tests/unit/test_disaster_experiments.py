# mypy: ignore-errors

"""Paired disasters@1 qualification: six kinds, seeds, twins, V1 exclusion."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import (
    EXPERIMENT_A_V1_CONDITION_IDS,
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    base_runner_config_from_scenario,
    experiment_disasters,
    v1_regression_profile,
)
from experiments.coordinator import ExperimentCoordinator
from experiments.disaster_scenario import (
    DISASTERS_EXPERIMENT_ID,
    disasters_scenario,
)
from tests.fakes.resilience_disaster_fixture import (
    drought_schedule_entry,
    drought_stock_base,
)
from experiments.models import (
    condition_fingerprint,
)
from simulation.clock import Tick
from simulation.disasters_checkpoint import (
    encode_disaster_state_section,
    section_from_disaster_state,
)
from simulation.disasters_config import DISASTERS_POLICY_ID, DisastersSpec
from simulation.disasters_randomness import spontaneous_occurrence_draw
from simulation.ecological_resources_config import (
    ECOLOGICAL_RESOURCES_POLICY_ID,
    EcologicalResourceNodeSpec,
    EcologicalResourcesSpec,
)
from simulation.journal import hash_snapshot
from simulation.models import RunId, SimulationRunConfig
from simulation.persistence import SnapshotId
from simulation.runner import (
    RunnerDependencyFactories,
    SimulationRunner,
    _engine_snapshot,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V63,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CollectiveProjectsSpec,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V4CapabilityFlags,
    WorldScenarioSpec,
    example_collective_projects_spec,
    example_public_goods_spec,
)
from simulation.serialization import encode_domain
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    make_resource,
    make_weather,
)
from world.disasters import (
    DisasterCollapseEffect,
    DisasterInfrastructureEffect,
    DisasterInfrastructureTarget,
    DisasterKind,
    DisasterLocationTarget,
    DisasterLossEffect,
    DisasterOrigin,
    DisasterResourceTarget,
    DisasterRule,
    DisasterScheduleEntry,
    DisasterSurgeEffect,
)
from world.environment import example_environmental_dynamics
from world.events import DisasterOutcome, DisasterResolved
from world.identifiers import EntityId, WorldId, WorldRevision
from world.infrastructure import InfrastructureKind, InfrastructureStatus
from world.models import default_physical_rules
from world.production import example_production_catalog
from world.supply_chain import supply_chain_production_catalog
from world.values import ItemKind, ResourceKind, WeatherCondition

pytestmark = pytest.mark.unit

_INJECT = 2
_INFRA_INJECT = 12
_SURGE_INJECT = 3
_MAX_TICKS = 8
_INFRA_MAX = 16


def _ecology(*resource_ids: str) -> EcologicalResourcesSpec:
    nodes = tuple(
        sorted(
            (
                EcologicalResourceNodeSpec(
                    resource_id=EntityId(resource_id),
                    minimum_capacity_tenths=5,
                    withdrawal_allowance_tenths=0,
                    recovery_tenths_per_idle_tick=1,
                )
                for resource_id in resource_ids
            ),
            key=lambda node: node.resource_id.value,
        )
    )
    return EcologicalResourcesSpec(
        policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
        nodes=nodes,
    )


def _disasters(
    rule: DisasterRule,
    *,
    schedule: tuple[DisasterScheduleEntry, ...] = (),
) -> DisastersSpec:
    return DisastersSpec(
        policy_id=DISASTERS_POLICY_ID,
        rules=(rule,),
        schedule=schedule,
    )


def _loss_rule(
    rule_id: str,
    *,
    kind: DisasterKind,
    resource_id: str,
    chance_ppm: int = 0,
    loss_tenths: int = 10,
) -> DisasterRule:
    return DisasterRule(
        rule_id=rule_id,
        kind=kind,
        chance_ppm=chance_ppm,
        target=DisasterResourceTarget(resource_id=EntityId(resource_id)),
        effect=DisasterLossEffect(loss_tenths=loss_tenths),
    )


def _collapse_rule(
    rule_id: str,
    *,
    resource_id: str,
    chance_ppm: int = 0,
) -> DisasterRule:
    return DisasterRule(
        rule_id=rule_id,
        kind=DisasterKind.RESOURCE_COLLAPSE,
        chance_ppm=chance_ppm,
        target=DisasterResourceTarget(resource_id=EntityId(resource_id)),
        effect=DisasterCollapseEffect(capacity_damage_tenths=25),
    )


def _infra_rule(rule_id: str = "infra-a") -> DisasterRule:
    return DisasterRule(
        rule_id=rule_id,
        kind=DisasterKind.INFRASTRUCTURE_DESTRUCTION,
        chance_ppm=0,
        target=DisasterInfrastructureTarget(
            location_id=EntityId("loc-a"),
            endpoint_location_id=None,
            infrastructure_kind=InfrastructureKind.WELL,
        ),
        effect=DisasterInfrastructureEffect(),
    )


def _surge_rule(rule_id: str = "surge-a") -> DisasterRule:
    return DisasterRule(
        rule_id=rule_id,
        kind=DisasterKind.EPIDEMIC_SURGE,
        chance_ppm=0,
        target=DisasterLocationTarget(location_id=EntityId("loc-settled")),
        effect=DisasterSurgeEffect(extra_opportunity_milli=1000),
    )


def _stock_base(
    *,
    rule: DisasterRule,
    target_kind: ResourceKind,
    weather: WeatherCondition,
    seed: int = 34,
    max_ticks: int = _MAX_TICKS,
    nontarget_kind: ResourceKind = ResourceKind.MATERIAL,
) -> SimulationRunnerConfig:
    body = alive_body("body-a", location_id="loc-a")
    agent_id = AgentId("agent-1")
    target = make_resource(
        "res-target",
        name="Target",
        kind=target_kind,
        location_id="loc-a",
        quantity=4.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    other = make_resource(
        "res-other",
        name="Other",
        kind=nontarget_kind,
        location_id="loc-a",
        quantity=3.0,
        maximum_quantity=3.0,
        regeneration_per_tick=0.5,
    )
    catalog = supply_chain_production_catalog(example_production_catalog())
    base = base_runner_config_from_scenario(
        seed=seed,
        stochastic_identity="disasters-pair",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-disasters-stock"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location("loc-a"),),
            bodies=(body,),
            weather=(make_weather("loc-a", condition=weather),),
            resources=(target, other),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=max_ticks,
    )
    agent = base.agents[0]
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V63,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=max_ticks, stop_on_all_agents_terminal=False
        ),
        environmental_dynamics=example_environmental_dynamics(),
        ecological_resources=_ecology("res-target", "res-other"),
        disasters=_disasters(rule),
        v4_capability_flags=V4CapabilityFlags(
            supply_chains=True,
            ecological_feedback=True,
            disasters=True,
        ),
        agents=(
            replace(
                agent,
                cognition=replace(agent.cognition, production_catalog=catalog),
            ),
        ),
    )


def _infra_base(*, max_ticks: int = _INFRA_MAX) -> SimulationRunnerConfig:
    stones = tuple(
        make_item(
            f"stone-{index}",
            name="stone",
            kind=ItemKind.MATERIAL,
            location_id=None,
            holder_id="body-a",
        )
        for index in range(2)
    )
    inventory = tuple(item.entity_id for item in stones)
    body = alive_body(
        "body-a",
        location_id="loc-a",
        inventory=inventory,
        carry_capacity=16,
    )
    agent_id = AgentId("agent-1")
    food = make_resource(
        "res-food",
        name="Food",
        kind=ResourceKind.FOOD,
        location_id="loc-a",
        quantity=4.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    catalog = supply_chain_production_catalog(example_production_catalog())
    base = base_runner_config_from_scenario(
        seed=56,
        stochastic_identity="disasters-infra",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-disasters-infra"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(
                make_location("loc-a", adjacent=("loc-b",)),
                make_location("loc-b", adjacent=("loc-a",)),
            ),
            bodies=(body,),
            weather=(make_weather("loc-a"), make_weather("loc-b")),
            items=stones,
            resources=(food,),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=max_ticks,
    )
    agent = base.agents[0]
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V63,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=max_ticks, stop_on_all_agents_terminal=False
        ),
        environmental_dynamics=example_environmental_dynamics(),
        ecological_resources=_ecology("res-food"),
        collective_projects=CollectiveProjectsSpec(idle_ticks=64),
        public_goods=example_public_goods_spec(),
        disasters=_disasters(_infra_rule()),
        v4_capability_flags=V4CapabilityFlags(
            supply_chains=True,
            ecological_feedback=True,
            infrastructure_networks=True,
            disasters=True,
        ),
        agents=(
            replace(
                agent,
                cognition=replace(agent.cognition, production_catalog=catalog),
            ),
        ),
    )


def _surge_base(*, max_ticks: int = _MAX_TICKS) -> SimulationRunnerConfig:
    from simulation.disease_config import DISEASE_POLICY_ID, DiseaseMechanicsSpec

    bodies = (
        alive_body("body-a", location_id="loc-settled"),
        alive_body("body-b", location_id="loc-settled"),
        alive_body("body-c", location_id="loc-remote"),
    )
    water = make_resource(
        "res-water",
        name="Remote Water",
        kind=ResourceKind.WATER,
        location_id="loc-remote",
        quantity=4.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    catalog = supply_chain_production_catalog(example_production_catalog())
    agents = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(f"agent-{index + 1}"),
            entity_id=body.entity_id,
            cognition=AgentCognitionSpec(agent_id=AgentId(f"agent-{index + 1}")),
        )
        for index, body in enumerate(bodies)
    )
    base = base_runner_config_from_scenario(
        seed=34,
        stochastic_identity="disasters-surge",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-disasters-surge"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(
                make_location("loc-settled", adjacent=("loc-remote",)),
                make_location("loc-remote", adjacent=("loc-settled",)),
            ),
            bodies=bodies,
            weather=(
                make_weather("loc-settled"),
                make_weather("loc-remote"),
            ),
            resources=(water,),
        ),
        agents=agents,
        max_ticks=max_ticks,
    )
    disease = DiseaseMechanicsSpec(
        policy_id=DISEASE_POLICY_ID,
        initial_latent_entity_ids=(EntityId("body-a"),),
        exposure_chance_milli=0,
        transmission_chance_milli=1000,
        symptom_chance_milli=1000,
        mortality_chance_milli=0,
        latent_ticks=1,
        active_ticks=2,
        immunity_after_recovery=True,
    )
    agents_with_catalog = tuple(
        replace(
            agent,
            cognition=replace(agent.cognition, production_catalog=catalog),
        )
        for agent in base.agents
    )
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V63,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=max_ticks, stop_on_all_agents_terminal=False
        ),
        environmental_dynamics=example_environmental_dynamics(),
        ecological_resources=_ecology("res-water"),
        collective_projects=example_collective_projects_spec(),
        disease_mechanics=disease,
        disasters=_disasters(_surge_rule()),
        v4_capability_flags=V4CapabilityFlags(
            supply_chains=True,
            ecological_feedback=True,
            infrastructure_networks=True,
            epidemics=True,
            disasters=True,
        ),
        agents=agents_with_catalog,
    )


def _commons_collapse_base(*, max_ticks: int = _MAX_TICKS) -> SimulationRunnerConfig:
    from simulation.commons_governance_config import (
        COMMONS_GOVERNANCE_POLICY_ID,
        CommonsGovernanceSpec,
    )
    from simulation.overexploitation_config import (
        OVEREXPLOITATION_POLICY_ID,
        OverexploitationSpec,
    )
    from simulation.runner_models import (
        InstitutionConceptMode,
        SocialNormMode,
    )

    bodies = (
        alive_body("body-a", location_id="loc-a"),
        alive_body("body-b", location_id="loc-a"),
        alive_body("body-c", location_id="loc-b"),
        alive_body("body-d", location_id="loc-b"),
    )
    water_a = make_resource(
        "res-water-a",
        name="Pool A",
        kind=ResourceKind.WATER,
        location_id="loc-a",
        quantity=4.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    water_b = make_resource(
        "res-water-b",
        name="Pool B",
        kind=ResourceKind.WATER,
        location_id="loc-b",
        quantity=4.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    catalog = supply_chain_production_catalog(example_production_catalog())
    agents = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(f"agent-{index + 1}"),
            entity_id=body.entity_id,
            cognition=AgentCognitionSpec(agent_id=AgentId(f"agent-{index + 1}")),
        )
        for index, body in enumerate(bodies)
    )
    base = base_runner_config_from_scenario(
        seed=34,
        stochastic_identity="disasters-commons",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-disasters-commons"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(
                make_location("loc-a", adjacent=("loc-b",), body_capacity=8),
                make_location("loc-b", adjacent=("loc-a",), body_capacity=8),
            ),
            bodies=bodies,
            weather=(make_weather("loc-a"), make_weather("loc-b")),
            resources=(water_a, water_b),
        ),
        agents=agents,
        max_ticks=max_ticks,
    )
    agents_with_modes = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                production_catalog=catalog,
                social_norm_mode=SocialNormMode.DETERMINISTIC,
                institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
            ),
        )
        for agent in base.agents
    )
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V63,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(
            max_ticks=max_ticks, stop_on_all_agents_terminal=False
        ),
        environmental_dynamics=example_environmental_dynamics(),
        ecological_resources=_ecology("res-water-a", "res-water-b"),
        overexploitation=OverexploitationSpec(
            policy_id=OVEREXPLOITATION_POLICY_ID
        ),
        commons_governance=CommonsGovernanceSpec(
            policy_id=COMMONS_GOVERNANCE_POLICY_ID,
            stock_ids=(EntityId("res-water-a"), EntityId("res-water-b")),
        ),
        disasters=_disasters(
            _collapse_rule("collapse-a", resource_id="res-water-a")
        ),
        v4_capability_flags=V4CapabilityFlags(
            supply_chains=True,
            ecological_feedback=True,
            formal_rules=True,
            disasters=True,
        ),
        agents=agents_with_modes,
    )


def _kind_cases() -> list[tuple[str, SimulationRunnerConfig, DisasterScheduleEntry]]:
    return [
        (
            "flood_like",
            _stock_base(
                rule=_loss_rule(
                    "flood-a",
                    kind=DisasterKind.FLOOD_LIKE,
                    resource_id="res-target",
                ),
                target_kind=ResourceKind.FOOD,
                weather=WeatherCondition.RAIN,
                nontarget_kind=ResourceKind.MATERIAL,
            ),
            DisasterScheduleEntry(tick=_INJECT, rule_id="flood-a"),
        ),
        (
            "fire",
            _stock_base(
                rule=_loss_rule(
                    "fire-a",
                    kind=DisasterKind.FIRE,
                    resource_id="res-target",
                ),
                target_kind=ResourceKind.MATERIAL,
                weather=WeatherCondition.CLEAR,
                nontarget_kind=ResourceKind.WATER,
            ),
            DisasterScheduleEntry(tick=_INJECT, rule_id="fire-a"),
        ),
        (
            "drought",
            drought_stock_base(),
            drought_schedule_entry(tick=_INJECT),
        ),
        (
            "resource_collapse",
            _commons_collapse_base(),
            DisasterScheduleEntry(tick=_INJECT, rule_id="collapse-a"),
        ),
        (
            "infrastructure_destruction",
            _infra_base(),
            DisasterScheduleEntry(tick=_INFRA_INJECT, rule_id="infra-a"),
        ),
        (
            "epidemic_surge",
            _surge_base(),
            DisasterScheduleEntry(tick=_SURGE_INJECT, rule_id="surge-a"),
        ),
    ]


def _disaster_receipts(events: tuple[object, ...]) -> list[object]:
    return [
        event
        for event in events
        if type(getattr(event, "details", None)) is DisasterResolved
    ]


def _physical_prefix(
    events: tuple[object, ...], *, before_tick: int
) -> tuple[tuple[object, ...], ...]:
    rows: list[tuple[object, ...]] = []
    for event in events:
        if event.tick >= before_tick:
            continue
        details = event.details
        if type(details) is not DisasterResolved:
            continue
        effect = details.effect
        target = details.target
        if hasattr(target, "resource_id"):
            target_key = ("resource", target.resource_id.value)
        elif hasattr(target, "infrastructure_kind"):
            target_key = (
                "infra",
                target.location_id.value,
                target.infrastructure_kind.value,
            )
        else:
            target_key = ("location", target.location_id.value)
        before = after = None
        if effect is not None and hasattr(effect, "quantity_before_tenths"):
            before = (
                effect.quantity_before_tenths,
                effect.quantity_after_tenths,
                effect.damage_before_tenths,
                effect.damage_after_tenths,
            )
            after = before
        elif effect is not None and hasattr(effect, "additional_latent_count"):
            before = effect.additional_latent_count
            after = before
        rows.append(
            (
                event.tick,
                details.disaster_kind.value,
                target_key,
                details.outcome.value,
                before,
                after,
            )
        )
    return tuple(rows)


def _targets_resource(receipt, resource_id: str) -> bool:
    target = receipt.details.target
    return hasattr(target, "resource_id") and target.resource_id.value == resource_id


@pytest.mark.asyncio
async def test_six_kind_qualification_matrix() -> None:
    for kind_name, base, entry in _kind_cases():
        definition = disasters_scenario(base, treatment_entry=entry)
        assert definition.experiment_id == DISASTERS_EXPERIMENT_ID
        assert [row.condition_id for row in definition.conditions] == [
            "control",
            "scheduled-shock",
        ]
        control_cfg = definition.conditions[0].runner_config
        treatment_cfg = definition.conditions[1].runner_config
        assert control_cfg.seed == treatment_cfg.seed == base.seed
        assert control_cfg.stochastic_identity == treatment_cfg.stochastic_identity
        assert control_cfg.disasters.schedule == ()
        assert treatment_cfg.disasters.schedule == (entry,)
        assert condition_fingerprint(definition.conditions[0]) != condition_fingerprint(
            definition.conditions[1]
        )

        results = await ExperimentCoordinator(definition).run_all()
        assert len(results) == 2
        control, treatment = results
        assert control.assignment.run_id != treatment.assignment.run_id
        assert control.assignment.seed == treatment.assignment.seed == base.seed
        assert (
            control.assignment.runner_config.stochastic_identity
            == treatment.assignment.runner_config.stochastic_identity
        )

        control_events = control.committed_events or ()
        treatment_events = treatment.committed_events or ()
        inject = entry.tick
        assert _physical_prefix(control_events, before_tick=inject) == _physical_prefix(
            treatment_events, before_tick=inject
        )

        control_receipts = _disaster_receipts(control_events)
        treatment_receipts = _disaster_receipts(treatment_events)
        assert control_receipts == []
        assert all(
            receipt.details.origin is DisasterOrigin.SCHEDULED
            for receipt in treatment_receipts
        )
        assert not any(
            receipt.details.origin is DisasterOrigin.SPONTANEOUS
            for receipt in (*control_receipts, *treatment_receipts)
        )
        applied = [
            receipt
            for receipt in treatment_receipts
            if receipt.details.outcome is DisasterOutcome.APPLIED
            and receipt.tick == inject
        ]
        assert len(applied) == 1, f"{kind_name} missing scheduled applied receipt"
        assert applied[0].details.disaster_kind.value == (
            base.disasters.rules[0].kind.value
        )

        # Measured deltas and non-target isolation from objective receipts.
        if kind_name in {"flood_like", "fire", "drought"}:
            effect = applied[0].details.effect
            assert effect.quantity_after_tenths < effect.quantity_before_tenths
            assert not any(
                _targets_resource(receipt, "res-other")
                for receipt in treatment_receipts
            )
        if kind_name == "resource_collapse":
            effect = applied[0].details.effect
            assert effect.damage_after_tenths > effect.damage_before_tenths
            assert _targets_resource(applied[0], "res-water-a")
            assert not any(
                _targets_resource(receipt, "res-water-b")
                for receipt in treatment_receipts
            )
        if kind_name == "infrastructure_destruction":
            infra = treatment.runner_result.final_infrastructure_assets
            destroyed = [
                asset
                for asset in infra
                if asset.kind is InfrastructureKind.WELL
                and asset.status is InfrastructureStatus.DESTROYED
            ]
            assert len(destroyed) == 1
            control_infra = control.runner_result.final_infrastructure_assets
            control_wells = [
                asset
                for asset in control_infra
                if asset.kind is InfrastructureKind.WELL
            ]
            assert control_wells
            assert all(
                asset.status is not InfrastructureStatus.DESTROYED
                for asset in control_wells
            )
        if kind_name == "epidemic_surge":
            effect = applied[0].details.effect
            assert effect.additional_latent_count >= 1


def test_factory_fail_closed_and_registration() -> None:
    base = _stock_base(
        rule=_loss_rule(
            "drought-a", kind=DisasterKind.DROUGHT, resource_id="res-target"
        ),
        target_kind=ResourceKind.WATER,
        weather=WeatherCondition.CLEAR,
    )
    entry = DisasterScheduleEntry(tick=_INJECT, rule_id="drought-a")
    definition = experiment_disasters(base, treatment_entry=entry)
    assert definition.experiment_id == DISASTERS_EXPERIMENT_ID
    assert DISASTERS_EXPERIMENT_ID in OFF_GATE_MATRIX_EXPERIMENT_IDS
    assert DISASTERS_EXPERIMENT_ID not in EXPERIMENT_A_V1_CONDITION_IDS
    plain = base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="disasters-v1-gate",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-disasters-v1"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location("loc-seed"),),
            bodies=(alive_body("body-seed"),),
            weather=(make_weather("loc-seed"),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=AgentId("agent-seed"),
                entity_id=EntityId("body-seed"),
                cognition=AgentCognitionSpec(agent_id=AgentId("agent-seed")),
            ),
        ),
        max_ticks=2,
    )
    profiled = v1_regression_profile(plain)
    assert profiled.schema_version != RUNNER_SCHEMA_VERSION_V63

    with pytest.raises(ValueError, match="disasters_experiment_base_invalid"):
        disasters_scenario(
            replace(base, disasters=_disasters(
                _loss_rule(
                    "drought-a",
                    kind=DisasterKind.DROUGHT,
                    resource_id="res-target",
                    chance_ppm=1,
                )
            )),
            treatment_entry=entry,
        )
    with pytest.raises(ValueError, match="disasters_experiment_schedule_invalid"):
        disasters_scenario(
            base,
            treatment_entry=DisasterScheduleEntry(tick=_INJECT, rule_id="missing"),
        )
    with pytest.raises(ValueError, match="disasters_experiment_schedule_invalid"):
        disasters_scenario(
            base,
            treatment_entry=DisasterScheduleEntry(
                tick=base.stop_policy.max_ticks, rule_id="drought-a"
            ),
        )


@pytest.mark.asyncio
async def test_skipped_scheduled_intervention_recorded() -> None:
    """Scheduled fire under rain is weather-ineligible; control has no receipt."""
    base = _stock_base(
        rule=_loss_rule(
            "fire-a", kind=DisasterKind.FIRE, resource_id="res-target"
        ),
        target_kind=ResourceKind.MATERIAL,
        weather=WeatherCondition.RAIN,
        nontarget_kind=ResourceKind.WATER,
    )
    entry = DisasterScheduleEntry(tick=_INJECT, rule_id="fire-a")
    results = await ExperimentCoordinator(
        disasters_scenario(base, treatment_entry=entry)
    ).run_all()
    control, treatment = results
    assert _disaster_receipts(control.committed_events or ()) == []
    receipts = _disaster_receipts(treatment.committed_events or ())
    assert len(receipts) == 1
    assert receipts[0].details.outcome is DisasterOutcome.WEATHER_INELIGIBLE
    assert receipts[0].details.origin is DisasterOrigin.SCHEDULED


@pytest.mark.asyncio
async def test_spontaneous_twins_byte_equal_and_seed_divergence() -> None:
    from simulation.disasters_randomness import DISASTERS_STREAM_NAMESPACE
    from simulation.randomness import StreamScope, create_named_stream
    from world.disasters import MAX_DISASTER_CHANCE_PPM

    rule_id = "drought-a"
    tick = 7
    # Task 1 stream keying: find a seed whose roll is within the configured ppm max.
    hit_seed = None
    hit_chance = None
    for seed in range(10_000):
        roll = create_named_stream(
            SimulationRunConfig(seed=seed),
            StreamScope(DISASTERS_STREAM_NAMESPACE, (str(tick), rule_id, "occurrence")),
        ).randrange(1_000_000)
        if roll < MAX_DISASTER_CHANCE_PPM:
            hit_seed = seed
            hit_chance = roll + 1
            break
    assert hit_seed is not None and hit_chance is not None
    assert spontaneous_occurrence_draw(
        SimulationRunConfig(seed=hit_seed),
        tick=tick,
        rule_id=rule_id,
        chance_ppm=hit_chance,
    )
    miss_seed = next(
        seed
        for seed in range(10_000)
        if seed != hit_seed
        and not spontaneous_occurrence_draw(
            SimulationRunConfig(seed=seed),
            tick=tick,
            rule_id=rule_id,
            chance_ppm=hit_chance,
        )
    )

    rule = _loss_rule(
        rule_id,
        kind=DisasterKind.DROUGHT,
        resource_id="res-target",
        chance_ppm=hit_chance,
    )
    base = _stock_base(
        rule=rule,
        target_kind=ResourceKind.WATER,
        weather=WeatherCondition.CLEAR,
        seed=hit_seed,
        max_ticks=tick + 2,
    )
    # Spontaneous-only: empty schedule, nonzero chance (not via disasters_scenario).
    assert base.disasters.schedule == ()
    assert base.disasters.rules[0].chance_ppm > 0

    async def _digest(seed: int, run_id: str) -> tuple[object, ...]:
        config = replace(base, seed=seed)
        runner = await SimulationRunner.from_config(
            config,
            run_id=RunId(run_id),
            factories=RunnerDependencyFactories(),
        )
        from experiments.disaster_scenario import disasters_arbiter

        runner.set_intervention_arbiter(
            disasters_arbiter("control", config, run_id=RunId(run_id))
        )
        async with runner:
            await runner.run()
            events = tuple(
                encode_domain(event)
                for event in runner.engine.export_events().events
            )
            section = section_from_disaster_state(
                runner.engine._snapshot.world.state.disaster_state
            )
            snap = _engine_snapshot(
                runner.engine,
                snapshot_id=SnapshotId("snap-disaster-twin"),
                next_tick=Tick(config.stop_policy.max_ticks),
            )
            return (events, encode_disaster_state_section(section), hash_snapshot(snap))

    left = await _digest(hit_seed, "run-disaster-twin")
    right = await _digest(hit_seed, "run-disaster-twin")
    assert left == right

    other = await _digest(miss_seed, "run-disaster-contrast")
    # Task 1 vectors: different seed yields a different trigger/receipt trace.
    assert other[0] != left[0] or other[1] != left[1]


@pytest.mark.asyncio
async def test_continuation_replay_parity_for_scheduled_shock() -> None:
    base = _stock_base(
        rule=_loss_rule(
            "drought-a", kind=DisasterKind.DROUGHT, resource_id="res-target"
        ),
        target_kind=ResourceKind.WATER,
        weather=WeatherCondition.CLEAR,
    )
    entry = DisasterScheduleEntry(tick=_INJECT, rule_id="drought-a")
    treatment = (
        disasters_scenario(base, treatment_entry=entry).conditions[1].runner_config
    )
    runner = await SimulationRunner.from_config(
        treatment,
        run_id=RunId("run-disaster-replay"),
        factories=RunnerDependencyFactories(),
    )
    from experiments.disaster_scenario import disasters_arbiter

    runner.set_intervention_arbiter(
        disasters_arbiter(
            "scheduled-shock",
            treatment,
            run_id=RunId("run-disaster-replay"),
        )
    )
    async with runner:
        await runner.run()
        live_events = tuple(runner.engine.export_events().events)
        live_qty = runner.engine._snapshot.world.state.resources[
            EntityId("res-target")
        ].quantity
        snap = _engine_snapshot(
            runner.engine,
            snapshot_id=SnapshotId("snap-disaster-end"),
            next_tick=Tick(treatment.stop_policy.max_ticks),
        )

    from simulation.engine import WorldEngine

    restored = WorldEngine.restore_from_snapshot(
        snap,
        events=(),
        committed_through_tick=None,
        ecological_resources=treatment.ecological_resources,
        environmental_dynamics=treatment.environmental_dynamics,
        disasters=treatment.disasters,
    )
    assert (
        restored._snapshot.world.state.resources[EntityId("res-target")].quantity
        == live_qty
    )
    assert any(
        type(event.details) is DisasterResolved
        and event.details.outcome is DisasterOutcome.APPLIED
        for event in live_events
    )
