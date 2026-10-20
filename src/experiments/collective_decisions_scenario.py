"""Experiment BH: owner-scoped collective deliberation and coordination.

No opinion, delegate, winner, institution, or successful decision is seeded.
The scenario composes already-owned channels and reports whatever proposals,
disagreement, blocked attempts, noncompliance, or silence occurs.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Final, cast

from experiments.institutionalization_scenario import (
    institutionalization_arbiter,
    institutionalization_scenario,
)
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V49,
    RUNNER_SCHEMA_VERSION_V51,
    AgentRunnerSpec,
    CollectiveDecisionMode,
    SimulationRunnerConfig,
)

__all__ = [
    "assert_collective_decision_structure",
    "bh_unsupported_config",
    "collective_decisions_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.collective_decisions_scenario"
)

_ENABLED_ARMS: Final[frozenset[str]] = frozenset(
    {"bh-decisions-on", "bh-decisions-on-limited"}
)


def _decision_agents(
    config: SimulationRunnerConfig, *, enabled: bool
) -> tuple[AgentRunnerSpec, ...]:
    return tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                collective_decision_mode=(
                    CollectiveDecisionMode.DETERMINISTIC
                    if enabled
                    else CollectiveDecisionMode.DISABLED
                ),
            ),
        )
        for agent in config.agents
    )


def collective_decisions_scenario(
    *,
    seed: int = 23,
    max_ticks: int = 16,
    seed_matrix: ExperimentSeedMatrix | None = None,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition:
    """Build BH arms: v4 baseline, decisions-off control, and v51 treatments."""
    reference = institutionalization_scenario(
        seed=seed,
        max_ticks=max_ticks,
        seed_matrix=seed_matrix,
        base=base,
    )
    by_id = {
        condition.condition_id: condition.runner_config
        for condition in reference.conditions
    }
    baseline = by_id["bf-baseline"]
    composed = by_id["bf-institution-on"]
    off_control = replace(
        composed,
        schema_version=RUNNER_SCHEMA_VERSION_V49,
        agents=_decision_agents(composed, enabled=False),
    )
    on_config = replace(
        composed,
        schema_version=RUNNER_SCHEMA_VERSION_V51,
        agents=_decision_agents(composed, enabled=True),
    )
    limited = replace(
        on_config,
        collective_projects=None,
        public_goods=None,
    )
    arms = (
        ("bh-baseline", "collective_decisions_flags_off", baseline),
        ("bh-decisions-off", "collective_decisions_mode_off", off_control),
        ("bh-decisions-on", "collective_decisions_mode_on", on_config),
        (
            "bh-decisions-on-limited",
            "collective_decisions_mode_on_opportunity_limited",
            limited,
        ),
    )
    _LOG.info(
        "collective_decisions_experiment_built arms=%s ticks=%s agents=%s",
        len(arms),
        max_ticks,
        len(on_config.agents),
    )
    return ExperimentDefinition(
        experiment_id="collective_decisions@1",
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=reference.seed_matrix,
        conditions=tuple(
            ExperimentCondition(
                condition_id=condition_id,
                label_code=label,
                runner_config=config,
            )
            for condition_id, label, config in arms
        ),
        paired_world_group="collective-decisions-bh-world",
    )


def bh_unsupported_config() -> SimulationRunnerConfig:
    """Non-run fixture: decision mode on a v50 config fails closed."""
    definition = collective_decisions_scenario(max_ticks=4)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bh-decisions-on"
    )
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V50

    return replace(config, schema_version=RUNNER_SCHEMA_VERSION_V50)


def collective_decisions_arbiter(
    condition_id: str, config: SimulationRunnerConfig
) -> object | None:
    if condition_id not in _ENABLED_ARMS:
        return None
    return institutionalization_arbiter("bf-institution-on", config)


def assert_collective_decision_structure(
    *,
    decision_ledgers: tuple[Any, ...],
    deterministic_owner_ids: list[str],
) -> dict[str, int]:
    """Structural arbiter: privacy/availability only, never consensus."""
    if len(decision_ledgers) != len(deterministic_owner_ids):
        raise AssertionError("collective_owner_ledger_count_mismatch")
    typed = tuple(cast(Any, ledger) for ledger in decision_ledgers)
    owners = [ledger.owner_id.value for ledger in typed]
    if owners != deterministic_owner_ids:
        raise AssertionError("collective_owner_order_mismatch")
    counts: dict[str, int] = {}
    for ledger in typed:
        for proposal in ledger.proposals:
            if proposal.owner_id.value not in deterministic_owner_ids:
                raise AssertionError("collective_cross_owner_leak")
            counts["proposal"] = counts.get("proposal", 0) + 1
        for position in ledger.positions:
            if position.actor_id.value not in deterministic_owner_ids:
                raise AssertionError("collective_unknown_actor")
            if position.actor_id.value == ledger.owner_id.value:
                counts["own_position"] = counts.get("own_position", 0) + 1
            else:
                counts["attributed_position"] = counts.get("attributed_position", 0) + 1
    return counts
