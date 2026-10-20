"""Composition harvests office rows and emits detached metrics only."""

from __future__ import annotations

import asyncio
from dataclasses import replace

from analysis.offices import harvest_office_rows
from experiments.collectors import assemble_arm_metric_bundle
from experiments.coordinator import ExperimentCoordinator
from experiments.institutionalization_scenario import institutionalization_scenario
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V49,
    RUNNER_SCHEMA_VERSION_V50,
    InstitutionConceptMode,
    OfficeSuccessionMode,
)


def _definition(*, office: bool) -> ExperimentDefinition:
    base = institutionalization_scenario(seed=23, max_ticks=4)
    config = next(
        condition.runner_config
        for condition in base.conditions
        if condition.condition_id == "bf-institution-on"
    )
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                institution_concept_mode=InstitutionConceptMode.DISABLED,
                office_succession_mode=(
                    OfficeSuccessionMode.DETERMINISTIC
                    if office
                    else OfficeSuccessionMode.DISABLED
                ),
            ),
        )
        for agent in config.agents
    )
    if office:
        config = replace(
            config, schema_version=RUNNER_SCHEMA_VERSION_V50, agents=agents
        )
    else:
        config = replace(
            config,
            schema_version=RUNNER_SCHEMA_VERSION_V49,
            agents=tuple(
                replace(
                    agent,
                    cognition=replace(
                        agent.cognition,
                        institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
                    ),
                )
                for agent in agents
            ),
        )
    return ExperimentDefinition(
        experiment_id="office-composition@1",
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=ExperimentSeedMatrix(seeds=(23,)),
        conditions=(
            ExperimentCondition(
                condition_id="office-on" if office else "office-off",
                label_code="office_metric_composition",
                runner_config=config,
            ),
            ExperimentCondition(
                condition_id="office-control",
                label_code="office_metric_composition_control",
                runner_config=config,
            ),
        ),
        paired_world_group="office-composition-world",
    )


def test_office_metrics_are_emitted_from_real_exports() -> None:
    arms = asyncio.run(ExperimentCoordinator(_definition(office=True)).run_all())
    arm = next(item for item in arms if item.assignment.condition_id == "office-on")
    bundle = assemble_arm_metric_bundle(arm)
    documents = {doc.metric_family: doc for doc in bundle.documents}
    assert "office_continuity" in documents
    assert "office_succession" in documents
    direct = harvest_office_rows(arm.runner_result.office_concept_ledgers)
    assert documents["office_continuity"].values["role_row_count"] == len(direct)


def test_disabled_office_mode_emits_no_office_metrics() -> None:
    arms = asyncio.run(ExperimentCoordinator(_definition(office=False)).run_all())
    arm = next(item for item in arms if item.assignment.condition_id == "office-off")
    assert arm.runner_result.office_concept_ledgers == ()
    bundle = assemble_arm_metric_bundle(arm)
    families = {doc.metric_family for doc in bundle.documents}
    assert "office_continuity" not in families
    assert "office_succession" not in families


def test_real_exports_and_detached_snapshot_inputs_harvest_identically() -> None:
    from dataclasses import replace as dc_replace

    arm = next(
        item
        for item in asyncio.run(
            ExperimentCoordinator(_definition(office=True)).run_all()
        )
        if item.assignment.condition_id == "office-on"
    )
    exported = arm.runner_result.office_concept_ledgers
    detached = tuple(dc_replace(ledger) for ledger in exported)
    assert harvest_office_rows(exported) == harvest_office_rows(detached)
