"""Experiment BG: owner-scoped offices and disputed succession.

No office type, legitimate successor, or desired consensus is seeded. The
scenario composes already-owned objective/communication channels and reports
whatever continuity, disagreement, vacancy, abandonment, or role change occurs.
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
    RUNNER_SCHEMA_VERSION_V50,
    AgentRunnerSpec,
    OfficeSuccessionMode,
    SimulationRunnerConfig,
)

__all__ = [
    "assert_office_structure",
    "bg_unsupported_config",
    "office_succession_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.offices_succession_scenario"
)

_ENABLED_ARMS: Final[frozenset[str]] = frozenset(
    {"bg-offices-on", "bg-offices-on-contested"}
)


def _office_agents(
    config: SimulationRunnerConfig, *, enabled: bool
) -> tuple[AgentRunnerSpec, ...]:
    return tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                office_succession_mode=(
                    OfficeSuccessionMode.DETERMINISTIC
                    if enabled
                    else OfficeSuccessionMode.DISABLED
                ),
            ),
        )
        for agent in config.agents
    )


def office_succession_scenario(
    *,
    seed: int = 23,
    max_ticks: int = 16,
    seed_matrix: ExperimentSeedMatrix | None = None,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition:
    """Build BG arms: v4 baseline, v50 office-off control, v50 office-on arms."""
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
        agents=_office_agents(composed, enabled=False),
    )
    on_config = replace(
        composed,
        schema_version=RUNNER_SCHEMA_VERSION_V50,
        agents=_office_agents(composed, enabled=True),
    )
    contested = replace(
        on_config,
        collective_projects=None,
        public_goods=None,
    )
    arms = (
        ("bg-baseline", "offices_flags_off", baseline),
        ("bg-offices-off", "offices_mode_off", off_control),
        ("bg-offices-on", "offices_mode_on", on_config),
        (
            "bg-offices-on-contested",
            "offices_mode_on_support_limited",
            contested,
        ),
    )
    _LOG.info(
        "offices_experiment_built arms=%s ticks=%s agents=%s",
        len(arms),
        max_ticks,
        len(on_config.agents),
    )
    return ExperimentDefinition(
        experiment_id="offices_succession@1",
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
        paired_world_group="offices-succession-bg-world",
    )


def bg_unsupported_config() -> SimulationRunnerConfig:
    """Non-run fixture: office mode on a v49 config fails closed."""
    definition = office_succession_scenario(max_ticks=4)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bg-offices-on"
    )
    return replace(config, schema_version=RUNNER_SCHEMA_VERSION_V49)


def office_succession_arbiter(
    condition_id: str, config: SimulationRunnerConfig
) -> object | None:
    if condition_id not in _ENABLED_ARMS:
        return None
    return institutionalization_arbiter("bf-institution-on", config)


def assert_office_structure(
    *,
    office_ledgers: tuple[Any, ...],
    deterministic_owner_ids: list[str],
    required_outcomes: tuple[str, ...] = (),
) -> dict[str, int]:
    """Structural arbiter: privacy/availability only, never political success."""
    if len(office_ledgers) != len(deterministic_owner_ids):
        raise AssertionError("office_owner_ledger_count_mismatch")
    typed_ledgers = tuple(cast(Any, ledger) for ledger in office_ledgers)
    owners = [ledger.owner_id.value for ledger in typed_ledgers]
    if owners != deterministic_owner_ids:
        raise AssertionError("office_owner_order_mismatch")
    seen: set[str] = set()
    outcomes: dict[str, int] = {}
    for ledger in typed_ledgers:
        for concept in ledger.concepts:
            if concept.owner_id.value not in deterministic_owner_ids:
                raise AssertionError("office_cross_owner_leak")
            if concept.office_id in seen:
                raise AssertionError("office_id_not_owner_local")
            seen.add(concept.office_id)
            if concept.office_id != concept.office_id:
                raise AssertionError("office_identity_unstable")
            for occupant in concept.occupants:
                if occupant.occupant_id.value == "":
                    raise AssertionError("office_empty_occupant")
            status = concept.status.value
            outcomes[status] = outcomes.get(status, 0) + 1
    return outcomes
