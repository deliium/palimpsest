"""Seed-derived assigned-lifespan draws for developmental stages.

Uses a dedicated ``lifespan_distribution`` stream namespace so draws never
couple to ``new_agent_init`` order. Assigned lifespan is stored on
``AgentLifecycleRecord`` only — never in Observation or init fingerprints.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Mapping
from typing import Final

from simulation.models import SimulationRunConfig
from simulation.randomness import StreamScope, create_named_stream
from simulation.runner_models import (
    LifespanDistributionSpec,
    PopulationLifecycleSpec,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id
from world.lifecycle import (
    require_assigned_lifespan_ticks,
    validate_assigned_lifespan_stage_coverage,
)

_LOGGER: Final[logging.Logger] = logging.getLogger("simulation.lifespan_distribution")

__all__ = [
    "assign_lifespan_ticks",
    "lifespan_distribution_stream",
]


def lifespan_distribution_stream(
    run_config: SimulationRunConfig,
    *,
    run_id: str,
    world_id: str,
    agent_id: str,
    entry_tick: int,
) -> random.Random:
    """Named RNG stream scoped under ``lifespan_distribution`` (never wall clock)."""
    if type(run_config) is not SimulationRunConfig:
        raise TypeError("run_config must be SimulationRunConfig")
    entry = require_exact_nonneg_int("entry_tick", entry_tick)
    scope = StreamScope(
        namespace="lifespan_distribution",
        names=(
            require_stable_id("run_id", run_id),
            require_stable_id("world_id", world_id),
            require_stable_id("agent_id", agent_id),
            str(entry),
            "assigned_lifespan",
        ),
    )
    _LOGGER.debug(
        "lifespan_distribution_stream namespace=%s agent_id=%s entry_tick=%s",
        scope.namespace,
        agent_id,
        entry,
    )
    return create_named_stream(run_config, scope)


def assign_lifespan_ticks(
    *,
    spec: PopulationLifecycleSpec,
    distribution: LifespanDistributionSpec | None = None,
    run_config: SimulationRunConfig | None = None,
    run_id: str | None = None,
    world_id: str | None = None,
    agent_id: str | None = None,
    entry_tick: int = 0,
) -> int:
    """Draw or copy assigned lifespan once for an agent entry.

    ``fixed`` / absent distribution copies ``spec.lifespan_ticks``. Non-fixed
    distributions require a seed-derived stream (run_config + ids).
    """
    if type(spec) is not PopulationLifecycleSpec:
        raise TypeError("spec must be PopulationLifecycleSpec")
    dist = (
        spec.lifespan_distribution
        if distribution is None
        else distribution
    )
    if type(dist) is not LifespanDistributionSpec:
        raise TypeError("distribution must be LifespanDistributionSpec")

    if dist.distribution_id == "fixed":
        assigned = require_assigned_lifespan_ticks(
            "assigned_lifespan_ticks", spec.lifespan_ticks
        )
        validate_assigned_lifespan_stage_coverage(
            assigned, spec.stage_thresholds
        )
        _LOGGER.info(
            "lifespan_assigned agent_id=%s distribution_id=fixed "
            "assigned_lifespan_ticks=%s",
            agent_id or "-",
            assigned,
        )
        return assigned

    if run_config is None or run_id is None or world_id is None or agent_id is None:
        _LOGGER.error(
            "lifespan_draw_missing_stream_context code=lifespan_draw_context "
            "distribution_id=%s",
            dist.distribution_id,
        )
        raise ValueError(
            "non-fixed lifespan distribution requires run_config, run_id, "
            "world_id, and agent_id (code=lifespan_draw_context)"
        )

    rng = lifespan_distribution_stream(
        run_config,
        run_id=run_id,
        world_id=world_id,
        agent_id=agent_id,
        entry_tick=entry_tick,
    )
    if dist.distribution_id == "uniform_int":
        min_ticks = int(dist.params["min_ticks"])
        max_ticks = int(dist.params["max_ticks"])
        _LOGGER.debug(
            "lifespan_draw_inputs distribution_id=uniform_int "
            "min_ticks=%s max_ticks=%s agent_id=%s",
            min_ticks,
            max_ticks,
            agent_id,
        )
        assigned = rng.randint(min_ticks, max_ticks)
    elif dist.distribution_id == "discrete_table":
        weights_raw = dist.params["weights"]
        if not isinstance(weights_raw, Mapping):
            raise TypeError("discrete_table weights must be a mapping")
        ages: list[int] = []
        weights: list[float] = []
        for age_key in sorted(weights_raw, key=lambda item: int(str(item))):
            ages.append(int(str(age_key)))
            weights.append(float(weights_raw[age_key]))
        total = sum(weights)
        if total <= 0.0:
            raise ValueError(
                "discrete_table weights must sum to a positive value "
                "(code=lifespan_distribution_weights_empty)"
            )
        _LOGGER.debug(
            "lifespan_draw_inputs distribution_id=discrete_table "
            "age_count=%s agent_id=%s",
            len(ages),
            agent_id,
        )
        # Categorical draw without depending on random.choices global state.
        pick = rng.random() * total
        cumulative = 0.0
        assigned = ages[-1]
        for age, weight in zip(ages, weights, strict=True):
            cumulative += weight
            if pick <= cumulative:
                assigned = age
                break
    else:
        raise ValueError(
            f"unknown lifespan distribution_id {dist.distribution_id!r} "
            "(code=unknown_lifespan_distribution_id)"
        )

    assigned = require_assigned_lifespan_ticks("assigned_lifespan_ticks", assigned)
    validate_assigned_lifespan_stage_coverage(assigned, spec.stage_thresholds)
    _LOGGER.info(
        "lifespan_assigned agent_id=%s distribution_id=%s "
        "assigned_lifespan_ticks=%s",
        agent_id,
        dist.distribution_id,
        assigned,
    )
    return assigned
