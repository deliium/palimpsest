"""Immutable experiment definition contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from simulation.models import StochasticIdentity
from simulation.runner_models import SimulationRunnerConfig
from simulation.runner_serialization import (
    cognition_fingerprint,
    runner_config_fingerprint,
    scenario_fingerprint,
)
from world.identifiers import require_stable_id

EXPERIMENT_SCHEMA_VERSION: Final[str] = "experiment-definition-v1"


@dataclass(frozen=True, slots=True)
class ExperimentSeedMatrix:
    """Ordered seed/replicate matrix shared by paired conditions."""

    seeds: tuple[int, ...]
    replicates_per_seed: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.seeds, (set, frozenset)):
            raise TypeError("seeds must be ordered")
        if isinstance(self.seeds, (str, bytes)) or not isinstance(self.seeds, Sequence):
            raise TypeError("seeds must be ordered")
        seeds = tuple(self.seeds)
        if not seeds:
            raise ValueError("seeds must be non-empty")
        for seed in seeds:
            if isinstance(seed, bool) or type(seed) is not int or seed < 0:
                raise ValueError("seeds must be non-negative ints")
        object.__setattr__(self, "seeds", seeds)
        if type(self.replicates_per_seed) is not int or self.replicates_per_seed < 1:
            raise ValueError("replicates_per_seed must be a positive int")


def _scenario_layout(config: SimulationRunnerConfig) -> object:
    """Scenario identity with resource quantities removed.

    Paired arms share locations and bodies. A resource maximum may differ,
    as in the scarce and abundant territorial worlds.
    """
    return replace(config.scenario, resources=())


@dataclass(frozen=True, slots=True)
class ExperimentCondition:
    """One named arm with a complete immutable runner configuration."""

    condition_id: str
    label_code: str
    runner_config: SimulationRunnerConfig

    def __post_init__(self) -> None:
        require_stable_id("condition_id", self.condition_id)
        require_stable_id("label_code", self.label_code)
        if type(self.runner_config) is not SimulationRunnerConfig:
            raise TypeError("runner_config must be SimulationRunnerConfig")


@dataclass(frozen=True, slots=True)
class ExperimentDefinition:
    """Reusable experiment with paired conditions over a shared seed matrix."""

    experiment_id: str
    schema_version: str
    seed_matrix: ExperimentSeedMatrix
    conditions: tuple[ExperimentCondition, ...]
    paired_world_group: str

    def __post_init__(self) -> None:
        require_stable_id("experiment_id", self.experiment_id)
        if self.schema_version != EXPERIMENT_SCHEMA_VERSION:
            raise ValueError("unsupported experiment schema_version")
        if type(self.seed_matrix) is not ExperimentSeedMatrix:
            raise TypeError("seed_matrix must be ExperimentSeedMatrix")
        require_stable_id("paired_world_group", self.paired_world_group)
        if isinstance(self.conditions, (set, frozenset)):
            raise TypeError("conditions must be ordered")
        if isinstance(self.conditions, (str, bytes)) or not isinstance(
            self.conditions, Sequence
        ):
            raise TypeError("conditions must be ordered")
        conditions = tuple(self.conditions)
        if len(conditions) < 2:
            raise ValueError("conditions must include at least two arms")
        seen: set[str] = set()
        base_scenario = None
        base_layout = None
        base_seed = None
        base_stochastic = None
        for condition in conditions:
            if type(condition) is not ExperimentCondition:
                raise TypeError("conditions entries must be ExperimentCondition")
            if condition.condition_id in seen:
                raise ValueError("condition_id must be unique")
            seen.add(condition.condition_id)
            cfg = condition.runner_config
            if base_scenario is None:
                base_scenario = scenario_fingerprint(cfg)
                base_layout = _scenario_layout(cfg)
                base_seed = cfg.seed
                base_stochastic = cfg.stochastic_identity
            else:
                if scenario_fingerprint(cfg) != base_scenario and _scenario_layout(
                    cfg
                ) != base_layout:
                    raise ValueError("paired conditions require identical scenario")
                if cfg.seed != base_seed:
                    raise ValueError("paired conditions require identical seed")
                if cfg.stochastic_identity != base_stochastic:
                    raise ValueError(
                        "paired conditions require identical stochastic_identity"
                    )
        object.__setattr__(self, "conditions", conditions)


def condition_fingerprint(condition: ExperimentCondition) -> str:
    if type(condition) is not ExperimentCondition:
        raise TypeError("condition_fingerprint requires ExperimentCondition")
    document = {
        "condition_id": condition.condition_id,
        "label_code": condition.label_code,
        "config_fingerprint": runner_config_fingerprint(condition.runner_config),
        "cognition_fingerprint": cognition_fingerprint(condition.runner_config),
        "scenario_fingerprint": scenario_fingerprint(condition.runner_config),
    }
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def definition_fingerprint(definition: ExperimentDefinition) -> str:
    if type(definition) is not ExperimentDefinition:
        raise TypeError("definition_fingerprint requires ExperimentDefinition")
    document = {
        "experiment_id": definition.experiment_id,
        "schema_version": definition.schema_version,
        "paired_world_group": definition.paired_world_group,
        "seeds": list(definition.seed_matrix.seeds),
        "replicates_per_seed": definition.seed_matrix.replicates_per_seed,
        "conditions": [
            {
                "condition_id": item.condition_id,
                "label_code": item.label_code,
                "fingerprint": condition_fingerprint(item),
            }
            for item in definition.conditions
        ],
    }
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def require_stochastic(identity: StochasticIdentity | str) -> StochasticIdentity:
    if type(identity) is StochasticIdentity:
        return identity
    if type(identity) is not str:
        raise TypeError("stochastic_identity must be StochasticIdentity or str")
    return StochasticIdentity(identity)
