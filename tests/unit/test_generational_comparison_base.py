"""Canonical generational base and comparability gate."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from types import SimpleNamespace

import pytest

from experiments.generational_comparison_base import (
    _spawn_locations,
    assert_comparable_generational_conditions,
    generational_comparison_base,
)
from simulation.generational_models import GenerationalRunSpec
from simulation.models import StochasticIdentity
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V55,
    LifespanDistributionSpec,
    PopulationLifecycleSpec,
    SimulationRunnerConfig,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
from world.identifiers import WorldId
from world.lifecycle import LifecycleStageId


def _base() -> SimulationRunnerConfig:
    return generational_comparison_base(seed=23, max_ticks=8)


def _replace_lifecycle(
    base: SimulationRunnerConfig, lifecycle: PopulationLifecycleSpec
) -> SimulationRunnerConfig:
    return replace(base, population_lifecycle=lifecycle)


def test_canonical_base_contract() -> None:
    base = _base()
    assert base.schema_version == RUNNER_SCHEMA_VERSION_V55
    assert base.generational_run is not None
    assert base.regions_migration is not None
    assert base.mortality_mode.value == "enabled"
    assert base.stop_policy.max_ticks == 8
    assert base.stop_policy.stop_on_all_agents_terminal is False
    assert base.v3_capability_flags.generational_population is True
    assert base.v3_capability_flags.multi_polity_migration is True
    assert base.v3_capability_flags.cultural_historical_memory is True
    assert base.v3_capability_flags.kinship_inheritance is False
    assert base.v3_capability_flags.institutional_economy is False
    assert base.cultural_feature_provenance is not None
    assert base.durable_records is None
    assert [agent.agent_id.value for agent in base.agents] == [
        "agent-origin",
        "agent-spring",
        "agent-grain",
        "agent-remote",
    ]
    assert [agent.entity_id.value for agent in base.agents] == [
        "body-origin",
        "body-spring",
        "body-grain",
        "body-remote",
    ]
    for agent in base.agents:
        assert agent.cognition.skill_learning_mode.value == "deterministic"
        assert agent.cognition.teaching_interaction_mode.value == "deterministic"
        assert agent.cognition.communication_strategy_mode.value == "deterministic"
    assert base.population_lifecycle is not None
    assert base.population_lifecycle.lifespan_ticks == 12
    assert base.population_lifecycle.max_population == 9
    assert [
        item.inclusive_max_age
        for item in base.population_lifecycle.stage_thresholds
    ] == [2, 4, 11]
    assert base.population_lifecycle.lifespan_distribution.is_passthrough_default()
    assert base.new_agent_initialization is not None
    assert (
        base.new_agent_initialization.parameter_distributions.distribution_id
        == "none"
    )
    assert decode_runner_config(encode_runner_config(base)) == base


def test_spawn_locations_preserve_canonical_order_and_truncate() -> None:
    base = _base()
    assert _spawn_locations(base.scenario) == (
        "loc-origin",
        "loc-spring",
        "loc-grain",
        "loc-remote",
    )
    shortened = replace(base.scenario, locations=base.scenario.locations[:2])
    assert _spawn_locations(shortened) == (
        "loc-origin",
        "loc-spring",
    )
    empty = SimpleNamespace(locations=())
    with pytest.raises(ValueError, match="generational_base_spawn_locations_required"):
        _spawn_locations(empty)  # type: ignore[arg-type]


def test_comparable_identical_configs_pass() -> None:
    base = _base()
    assert_comparable_generational_conditions((base, base))


@pytest.mark.parametrize(
    ("mutator", "code"),
    (
        (lambda base: replace(base, seed=24), "comparison_seed_mismatch"),
        (
            lambda base: replace(
                base, stochastic_identity=StochasticIdentity("other-identity")
            ),
            "comparison_identity_mismatch",
        ),
        (
            lambda base: replace(
                base,
                scenario=replace(
                    base.scenario, world_id=WorldId("other-world")
                ),
            ),
            "comparison_scenario_mismatch",
        ),
        (
            lambda base: replace(
                base,
                agents=(
                    replace(base.agents[0], name="renamed"),
                    *base.agents[1:],
                ),
            ),
            "comparison_roster_mismatch",
        ),
        (
            lambda base: replace(
                base,
                stop_policy=replace(base.stop_policy, max_ticks=9),
            ),
            "comparison_stop_policy_mismatch",
        ),
        (
            lambda base: replace(
                base,
                generational_run=GenerationalRunSpec(
                    max_generation_index=5,
                    stop_on_extinction=False,
                    criterion_cadence_ticks=1,
                ),
            ),
            "comparison_generational_run_mismatch",
        ),
        (
            lambda base: _replace_lifecycle(
                base,
                replace(
                    base.population_lifecycle,
                    dependent_until_stage=LifecycleStageId("adult"),
                ),
            ),
            "comparison_lifecycle_mismatch",
        ),
        (
            lambda base: _replace_lifecycle(
                base,
                replace(
                    base.population_lifecycle,
                    demographic_policy_params={
                        **base.population_lifecycle.demographic_policy_params,
                        "interval_ticks": 4,
                    },
                ),
            ),
            "comparison_schedule_mismatch",
        ),
        (
            lambda base: _replace_lifecycle(
                base,
                replace(
                    base.population_lifecycle,
                    lifespan_distribution=LifespanDistributionSpec(
                        distribution_id="uniform_int",
                        params={"min_ticks": 8, "max_ticks": 12},
                    ),
                ),
            ),
            "comparison_lifespan_distribution_not_passthrough",
        ),
    ),
)
def test_comparability_failures(
    mutator: Callable[[SimulationRunnerConfig], SimulationRunnerConfig],
    code: str,
) -> None:
    base = _base()
    altered = mutator(base)
    with pytest.raises(ValueError) as error:
        assert_comparable_generational_conditions((base, altered))
    assert str(error.value) == code


def test_resource_quantities_may_differ_but_identity_may_not() -> None:
    base = _base()
    changed = replace(
        base.scenario.resources[0],
        quantity=base.scenario.resources[0].quantity + 1.0,
        maximum_quantity=base.scenario.resources[0].maximum_quantity + 1.0,
    )
    quantity_only = replace(
        base,
        scenario=replace(
            base.scenario,
            resources=(changed, *base.scenario.resources[1:]),
        ),
    )
    assert_comparable_generational_conditions((base, quantity_only))

    renamed = replace(
        base.scenario.resources[0], name="renamed-resource"
    )
    identity_changed = replace(
        base,
        scenario=replace(
            base.scenario,
            resources=(renamed, *base.scenario.resources[1:]),
        ),
    )
    with pytest.raises(ValueError) as error:
        assert_comparable_generational_conditions((base, identity_changed))
    assert str(error.value) == "comparison_resource_identity_mismatch"


def test_population_size_may_differ_only_with_flag() -> None:
    base = _base()
    lifecycle = base.population_lifecycle
    assert lifecycle is not None
    smaller = _replace_lifecycle(
        base, replace(lifecycle, max_population=6)
    )
    with pytest.raises(ValueError) as error:
        assert_comparable_generational_conditions((base, smaller))
    assert str(error.value) == "comparison_population_capacity_mismatch"
    assert_comparable_generational_conditions(
        (base, smaller), allow_population_size=True
    )

    schedule_changed = _replace_lifecycle(
        base,
        replace(
            lifecycle,
            max_population=6,
            demographic_policy_params={
                **lifecycle.demographic_policy_params,
                "interval_ticks": 4,
            },
        ),
    )
    with pytest.raises(ValueError) as error:
        assert_comparable_generational_conditions(
            (base, schedule_changed), allow_population_size=True
        )
    assert str(error.value) == "comparison_schedule_mismatch"


def test_non_passthrough_initialization_fails() -> None:
    base = _base()
    assert base.new_agent_initialization is not None
    initialization = replace(
        base.new_agent_initialization,
        provenance_policy=replace(
            base.new_agent_initialization.provenance_policy,
            record_origin_refs=True,
        ),
    )
    altered = replace(base, new_agent_initialization=initialization)
    with pytest.raises(ValueError) as error:
        assert_comparable_generational_conditions((base, altered))
    assert str(error.value) == "comparison_initialization_mismatch"
