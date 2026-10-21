"""Composition of real exported decay ledgers into detached analysis rows."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from agents.cognition.institutional_decay import InstitutionDecayLedger
from analysis.institution_lineage import compute_institution_lineage
from analysis.institutional_decay import (
    InstitutionTemporalRow,
    compute_institutional_decay,
    institution_decay_rows_from_ledgers,
)
from analysis.institutional_decay_metrics import (
    compute_institution_lifecycle_metric,
    compute_institution_lineage_metric,
    compute_institutional_decay_metric,
)
from analysis.serialization import decode_metric_document, encode_metric_document
from experiments.composition import institution_temporal_rows_from_ledgers
from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V54,
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    SimulationRunnerConfig,
)
from world.identifiers import EntityId


def _config() -> SimulationRunnerConfig:
    definition = institutionalization_scenario(seed=23, max_ticks=2)
    base = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
                institutional_memory_mode=InstitutionalMemoryMode.DISABLED,
                institutional_decay_mode=InstitutionalDecayMode.DETERMINISTIC,
            ),
        )
        for agent in base.agents
    )
    return replace(base, schema_version=RUNNER_SCHEMA_VERSION_V54, agents=agents)


@pytest.mark.asyncio
async def test_real_completed_run_projects_rows_and_classifies() -> None:
    config = _config()
    async with await SimulationRunner.from_config(
        config, run_id=RunId("run-decay-composition")
    ) as runner:
        await runner.run()
        ledgers = runner.export_institutional_decay_ledgers()
    assert all(isinstance(ledger, InstitutionDecayLedger) for ledger in ledgers)
    typed_ledgers = cast(tuple[InstitutionDecayLedger, ...], ledgers)
    rows = institution_temporal_rows_from_ledgers(typed_ledgers)
    assert rows
    assert rows == tuple(
        sorted(
            rows,
            key=lambda row: (
                row.owner_id,
                row.local_pattern_id,
                row.observation_tick,
            ),
        )
    )
    assert all(
        row.owner_id == ledger.owner_id.value
        for ledger in typed_ledgers
        for row in rows
        if row.owner_id == ledger.owner_id.value
    )
    result = compute_institutional_decay(
        rows, as_of_tick=max(r.observation_tick for r in rows)
    )
    assert result.policy_version == "institutional-lifecycle.v1"
    lineage = compute_institution_lineage(
        rows, as_of_tick=max(r.observation_tick for r in rows), lifecycle=result
    )
    assert lineage.policy_version == "institutional-lineage.v1"
    assert lineage.episodes
    for document in (
        compute_institutional_decay_metric(
            rows,
            run_id="run-decay-composition",
            input_revision="rev-1",
            as_of_tick=result.as_of_tick,
        ),
        compute_institution_lifecycle_metric(
            rows,
            run_id="run-decay-composition",
            input_revision="rev-1",
            as_of_tick=result.as_of_tick,
        ),
        compute_institution_lineage_metric(
            rows,
            run_id="run-decay-composition",
            input_revision="rev-1",
            as_of_tick=result.as_of_tick,
            lifecycle=result,
        ),
    ):
        assert decode_metric_document(encode_metric_document(document)) == document


def test_projection_rejects_invalid_ledgers() -> None:
    with pytest.raises((TypeError, ValueError)):
        institution_decay_rows_from_ledgers(("not-a-ledger",))


def test_objective_context_projects_to_matching_pattern_scope() -> None:
    from types import SimpleNamespace

    from experiments.composition import institution_decay_context_from_events

    row = _row_for_context()
    event = SimpleNamespace(
        tick=1,
        kind="Died",
        details=SimpleNamespace(location_id=EntityId("clearing")),
    )
    contexts = institution_decay_context_from_events((event,), (row,), as_of_tick=2)
    assert contexts
    assert contexts[0].kind == "population_loss"
    assert contexts[0].local_pattern_id == row.local_pattern_id


def _row_for_context() -> InstitutionTemporalRow:
    from analysis.institutional_decay import InstitutionTemporalRow

    return InstitutionTemporalRow(
        owner_id="owner",
        local_pattern_id="p" * 64,
        observation_tick=1,
        source_first_tick=1,
        source_last_tick=1,
        role_recognition=0.0,
        procedure_recurrence=0.0,
        social_expectation=0.0,
        legitimacy_belief=0.0,
        succession_observed=0.0,
        generational_continuity=0.0,
        recognized=False,
        context_key="clearing",
    )
