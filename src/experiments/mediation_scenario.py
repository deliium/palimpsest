"""Experiment BI: optional owner-scoped conflict mediation.

No dispute, account, mediator occupation, consent, or settlement is seeded.
Arms expose legitimate opportunities and configuration only; the experiment
reports whatever offers, refusals, silence, or follow-through occurs.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Final, cast

from experiments.institutionalization_scenario import (
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
    RUNNER_SCHEMA_VERSION_V52,
    AgentRunnerSpec,
    MediationMode,
    OfficeSuccessionMode,
    ReputationMode,
    SimulationRunnerConfig,
    SocialNormMode,
)

__all__ = [
    "assert_mediation_structure",
    "bi_unsupported_config",
    "mediation_opportunities_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.mediation_scenario")


def _mediation_agents(
    config: SimulationRunnerConfig, *, enabled: bool
) -> tuple[AgentRunnerSpec, ...]:
    return tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                mediation_mode=(
                    MediationMode.DETERMINISTIC if enabled else MediationMode.DISABLED
                ),
            ),
        )
        for agent in config.agents
    )


def mediation_opportunities_scenario(
    *,
    seed: int = 23,
    max_ticks: int = 16,
    seed_matrix: ExperimentSeedMatrix | None = None,
    base: SimulationRunnerConfig | None = None,
) -> ExperimentDefinition:
    """Build BI arms: v4 baseline, prior-schema off control, and v52 treatments."""
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
        agents=_mediation_agents(composed, enabled=False),
    )
    on_config = replace(
        composed,
        schema_version=RUNNER_SCHEMA_VERSION_V52,
        agents=_mediation_agents(composed, enabled=True),
    )
    limited = replace(
        on_config,
        collective_projects=None,
        public_goods=None,
    )

    def with_modes(
        config: SimulationRunnerConfig, **modes: object
    ) -> SimulationRunnerConfig:
        return replace(
            config,
            agents=tuple(
                replace(agent, cognition=replace(agent.cognition, **cast("Any", modes)))
                for agent in config.agents
            ),
        )

    relations = with_modes(on_config, reputation_mode=ReputationMode.DETERMINISTIC)
    roles = with_modes(
        on_config,
        office_succession_mode=OfficeSuccessionMode.DETERMINISTIC,
        social_norm_mode=SocialNormMode.DETERMINISTIC,
    )
    arms = (
        ("bi-baseline", "mediation_flags_off", baseline),
        ("bi-mediation-off", "mediation_mode_off", off_control),
        ("bi-mediation-on", "mediation_mode_on", on_config),
        (
            "bi-mediation-relations",
            "mediation_mode_on_relationships_reputation",
            relations,
        ),
        (
            "bi-mediation-roles",
            "mediation_mode_on_roles_norms_institutions",
            roles,
        ),
        (
            "bi-mediation-on-limited",
            "mediation_mode_on_opportunity_limited",
            limited,
        ),
    )
    _LOG.info(
        "mediation_experiment_built arms=%s ticks=%s agents=%s",
        len(arms),
        max_ticks,
        len(on_config.agents),
    )
    return ExperimentDefinition(
        experiment_id="mediation_opportunities@1",
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
        paired_world_group="mediation-opportunities-bi-world",
    )


def bi_unsupported_config() -> SimulationRunnerConfig:
    """Non-run fixture: v52 mediation mode on a historical schema fails closed."""
    definition = mediation_opportunities_scenario(max_ticks=4)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bi-mediation-on"
    )
    from simulation.runner_models import RUNNER_SCHEMA_VERSION_V51

    return replace(config, schema_version=RUNNER_SCHEMA_VERSION_V51)


def assert_mediation_structure(
    *,
    mediation_ledgers: tuple[Any, ...],
    deterministic_owner_ids: list[str],
) -> dict[str, int]:
    """Structural arbiter: ownership/availability only, never success."""
    if len(mediation_ledgers) != len(deterministic_owner_ids):
        raise AssertionError("mediation_owner_ledger_count_mismatch")
    typed = tuple(cast(Any, ledger) for ledger in mediation_ledgers)
    owners = [ledger.owner_id.value for ledger in typed]
    if owners != deterministic_owner_ids:
        raise AssertionError("mediation_owner_order_mismatch")
    counts: dict[str, int] = {}
    for ledger in typed:
        for case in ledger.cases:
            if case.owner_id.value not in deterministic_owner_ids:
                raise AssertionError("mediation_cross_owner_leak")
            counts["case"] = counts.get("case", 0) + 1
        for response in ledger.responses:
            if response.owner_id.value != ledger.owner_id.value:
                raise AssertionError("mediation_cross_owner_response")
            counts["response"] = counts.get("response", 0) + 1
    return counts
