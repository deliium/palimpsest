"""Off-gate experiment ``supply_chains@1``."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    MortalityMode,
    ProductionKnowledgeMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V3CapabilityFlags,
    V4CapabilityFlags,
)
from world.production import ProductionCatalog, example_production_catalog
from world.supply_chain import supply_chain_production_catalog

__all__ = ["SUPPLY_CHAINS_EXPERIMENT_ID", "supply_chain_scenario"]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.supply_chain_scenario")

SUPPLY_CHAINS_EXPERIMENT_ID: Final[str] = "supply_chains@1"


def _with_catalog(
    config: SimulationRunnerConfig, catalog: ProductionCatalog
) -> SimulationRunnerConfig:
    return replace(
        config,
        agents=tuple(
            replace(
                agent,
                cognition=replace(agent.cognition, production_catalog=catalog),
            )
            for agent in config.agents
        ),
    )


def _with_production_knowledge(
    config: SimulationRunnerConfig,
) -> SimulationRunnerConfig:
    return replace(
        config,
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    production_knowledge_mode=ProductionKnowledgeMode.DETERMINISTIC,
                ),
            )
            for agent in config.agents
        ),
    )


def supply_chain_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 48,
) -> ExperimentDefinition:
    """Control (legacy catalog) vs treatment (multi-stage chain catalog)."""
    if base.v4_capability_flags.supply_chains:
        raise ValueError("supply_chain_scenario_invalid")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    legacy = example_production_catalog()
    chain = supply_chain_production_catalog(legacy)

    def _condition(
        *, enabled: bool, catalog: ProductionCatalog
    ) -> SimulationRunnerConfig:
        config = replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V56,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(),
            v4_capability_flags=V4CapabilityFlags(supply_chains=enabled),
        )
        return _with_production_knowledge(_with_catalog(config, catalog))

    conditions = (
        ExperimentCondition(
            condition_id="supply-chain-off",
            label_code="supply_chains_control",
            runner_config=_condition(enabled=False, catalog=legacy),
        ),
        ExperimentCondition(
            condition_id="supply-chain-on",
            label_code="supply_chains_treatment",
            runner_config=_condition(enabled=True, catalog=chain),
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s conditions=%s",
        SUPPLY_CHAINS_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=SUPPLY_CHAINS_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group="supply-chains",
    )
