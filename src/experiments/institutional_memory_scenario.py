"""Experiment BJ: opportunities for owner-scoped institutional memory."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Final

from experiments.institutionalization_scenario import institutionalization_scenario
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V52,
    RUNNER_SCHEMA_VERSION_V53,
    ArtifactInterpretationMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    MediationMode,
    OfficeSuccessionMode,
    TeachingInteractionMode,
)

__all__ = [
    "assert_institutional_memory_structure",
    "experiment_bj_institutional_memory",
    "institutional_memory_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.institutional_memory_scenario"
)


def _with_modes(config: Any, **modes: object) -> Any:
    return replace(
        config,
        agents=tuple(
            replace(
                agent,
                cognition=replace(agent.cognition, **modes),
            )
            for agent in config.agents
        ),
    )


def institutional_memory_scenario(
    *,
    seed: int = 23,
    max_ticks: int = 16,
    seed_matrix: object = None,
    base: object = None,
) -> ExperimentDefinition:
    """Build six BJ arms; none preseed roles, records, or learned content."""
    if base is not None and not hasattr(base, "agents"):
        raise TypeError("base must be SimulationRunnerConfig or None")
    reference = institutionalization_scenario(
        seed=seed,
        max_ticks=max_ticks,
        seed_matrix=seed_matrix,  # type: ignore[arg-type]
        base=base,  # type: ignore[arg-type]
    )
    by_id = {
        condition.condition_id: condition.runner_config
        for condition in reference.conditions
    }
    baseline = by_id["bf-baseline"]
    composed = by_id["bf-institution-on"]
    memory_off = replace(
        composed,
        schema_version=RUNNER_SCHEMA_VERSION_V52,
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    institutional_memory_mode=InstitutionalMemoryMode.DISABLED,
                    mediation_mode=MediationMode.DETERMINISTIC,
                ),
            )
            for agent in composed.agents
        ),
    )
    memory_on = replace(
        composed,
        schema_version=RUNNER_SCHEMA_VERSION_V53,
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    office_succession_mode=OfficeSuccessionMode.DETERMINISTIC,
                    institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
                    institutional_memory_mode=InstitutionalMemoryMode.DETERMINISTIC,
                    mediation_mode=MediationMode.DISABLED,
                ),
            )
            for agent in composed.agents
        ),
    )
    record_opportunities = _with_modes(
        memory_on,
        artifact_interpretation_mode=ArtifactInterpretationMode.DETERMINISTIC,
    )
    teaching_opportunities = replace(
        _with_modes(
            memory_on,
            teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
        ),
        artifacts_enabled=False,
        durable_records=None,
        knowledge_repositories=None,
    )
    limited = replace(
        teaching_opportunities,
        collective_projects=None,
        public_goods=None,
    )
    arms = (
        ("bj-baseline", "institutional_memory_opportunities_off", baseline),
        ("bj-memory-off", "institutional_memory_mode_off", memory_off),
        ("bj-memory-on", "institutional_memory_mode_on", memory_on),
        (
            "bj-record-opportunities",
            "institutional_memory_record_opportunities",
            record_opportunities,
        ),
        (
            "bj-teaching-opportunities",
            "institutional_memory_teaching_opportunities",
            teaching_opportunities,
        ),
        (
            "bj-limited-opportunities",
            "institutional_memory_opportunity_limited",
            limited,
        ),
    )
    _LOG.info(
        "institutional_memory_experiment_built arms=%s ticks=%s agents=%s",
        len(arms),
        max_ticks,
        len(memory_on.agents),
    )
    return ExperimentDefinition(
        experiment_id="institutional_memory@1",
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
        paired_world_group="institutional-memory-bj-world",
    )


def experiment_bj_institutional_memory(
    base: object,
    *,
    seed_matrix: object = None,
    max_ticks: int = 16,
) -> ExperimentDefinition:
    """Off-gate Experiment BJ opportunity arms."""
    definition = institutional_memory_scenario(
        base=base, seed_matrix=seed_matrix, max_ticks=max_ticks
    )
    _LOG.info(
        "experiment_registered experiment_id=institutional_memory@1 arms=%s",
        len(definition.conditions),
    )
    return definition


def assert_institutional_memory_structure(
    *,
    ledgers: tuple[Any, ...],
    deterministic_owner_ids: list[str],
) -> dict[str, int]:
    """Structural arbiter: ownership/receipts only, never learning success."""
    if len(ledgers) != len(deterministic_owner_ids):
        raise AssertionError("institutional_memory_owner_ledger_count_mismatch")
    seen: list[str] = []
    for ledger in ledgers:
        if not all(
            hasattr(ledger, field)
            for field in ("owner_id", "entries", "channels", "uses")
        ):
            raise AssertionError("institutional_memory_ledger_type")
        if ledger.owner_id.value not in deterministic_owner_ids:
            raise AssertionError("institutional_memory_foreign_owner")
        seen.append(ledger.owner_id.value)
    if seen != deterministic_owner_ids:
        raise AssertionError("institutional_memory_owner_order")
    return {
        "owner_count": len(ledgers),
        "entry_count": sum(len(ledger.entries) for ledger in ledgers),
        "channel_count": sum(len(ledger.channels) for ledger in ledgers),
    }
