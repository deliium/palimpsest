"""Unit tests for matrix-aggregate-v1 builder."""

from __future__ import annotations

from experiments.collectors import CollectorMetricDocument
from experiments.coordinator import ExperimentArmResult, ExperimentAssignment
from experiments.matrix_aggregate import (
    MATRIX_AGGREGATE_SCHEMA_VERSION,
    build_matrix_aggregate,
    encode_matrix_aggregate,
    matrix_aggregate_fingerprint,
)
from experiments.matrix_expand import expand_matrix
from experiments.matrix_factors import matrix_reference_fixture_base
from experiments.matrix_models import (
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    ExperimentMatrixSpec,
    GroupRole,
    MatrixEmbeddedBase,
    MatrixFactor,
    MatrixFactorId,
    MatrixFactorLevel,
)
from experiments.models import ExperimentSeedMatrix
from simulation.models import RunId
from simulation.runner_models import (
    RunnerStopReasonCode,
    SimulationRunnerResult,
)


def _spec() -> ExperimentMatrixSpec:
    return ExperimentMatrixSpec(
        matrix_id="matrix-aggregate-demo",
        schema_version=EXPERIMENT_MATRIX_SCHEMA_VERSION,
        base=MatrixEmbeddedBase(
            runner_config=matrix_reference_fixture_base(max_ticks=1)
        ),
        factors=(
            MatrixFactor(
                factor_id=MatrixFactorId.MEMORY_TYPE,
                levels=(
                    MatrixFactorLevel(
                        level_id="reference",
                        label_code="ref",
                        group_role=GroupRole.CONTROL,
                    ),
                    MatrixFactorLevel(
                        level_id="reconstructive",
                        label_code="recon",
                        group_role=GroupRole.TREATMENT,
                    ),
                ),
            ),
            MatrixFactor(
                factor_id=MatrixFactorId.MORTALITY,
                levels=(
                    MatrixFactorLevel(level_id="disabled", label_code="mort_off"),
                    MatrixFactorLevel(level_id="enabled", label_code="mort_on"),
                ),
            ),
        ),
        seed_matrix=ExperimentSeedMatrix(seeds=(11,)),
    )


def _fake_metrics(
    run_id: str, condition_id: str
) -> tuple[CollectorMetricDocument, ...]:
    return (
        CollectorMetricDocument(
            schema_version="experiment-collector-v2",
            family="summary",
            run_id=run_id,
            condition_id=condition_id,
            fields=(("ticks_committed", 1),),
        ),
        CollectorMetricDocument(
            schema_version="experiment-collector-v2",
            family="trajectory",
            run_id=run_id,
            condition_id=condition_id,
            fields=(("exact_trajectory_hash_prefix", "aaaaaaaaaaaa"),),
        ),
        CollectorMetricDocument(
            schema_version="experiment-collector-v2",
            family="catalog",
            run_id=run_id,
            condition_id=condition_id,
            fields=(("catalog_code", "matrix"),),
        ),
    )


def test_aggregate_deterministic_and_matrix_collector_fallback_ids() -> None:
    definition, cells = expand_matrix(_spec())
    assert not definition.experiment_id.startswith("experiment-a")
    arms: list[ExperimentArmResult] = []
    for index, cell in enumerate(cells):
        condition = next(
            item
            for item in definition.conditions
            if item.condition_id == cell.condition_id
        )
        assignment = ExperimentAssignment(
            experiment_id=definition.experiment_id,
            condition_id=cell.condition_id,
            condition_ordinal=index,
            seed=cell.seed,
            seed_ordinal=cell.seed_ordinal,
            replicate_index=cell.replicate_index,
            run_id=RunId(f"run-{index}"),
            runner_config=condition.runner_config,
        )
        result = SimulationRunnerResult(
            run_id=assignment.run_id,
            ticks_committed=1,
            stop_reason=RunnerStopReasonCode.MAX_TICKS,
            attempt_receipts=(),
        )
        arms.append(
            ExperimentArmResult(
                assignment=assignment,
                runner_result=result,
                config_fingerprint=cell.config_fingerprint,
                metrics=_fake_metrics(assignment.run_id.value, cell.condition_id),
            )
        )

    # Matrix experiment ids do not match catalog experiment-a…e prefixes, so
    # collect_for_experiment uses summary+trajectory+catalog fallback.
    assert not definition.experiment_id.startswith("experiment-a")
    assert definition.experiment_id.startswith("matrix-")

    doc1 = build_matrix_aggregate(
        matrix_id=definition.experiment_id,
        matrix_fingerprint="a" * 64,
        cells=cells,
        arm_results=arms,
    )
    doc2 = build_matrix_aggregate(
        matrix_id=definition.experiment_id,
        matrix_fingerprint="a" * 64,
        cells=cells,
        arm_results=tuple(reversed(arms)),
    )
    assert doc1.schema_version == MATRIX_AGGREGATE_SCHEMA_VERSION
    assert matrix_aggregate_fingerprint(doc1) == matrix_aggregate_fingerprint(doc2)
    assert encode_matrix_aggregate(doc1) == encode_matrix_aggregate(doc2)
    assert dict(doc1.group_role_counts)["treatment"] >= 1
    assert doc1.cell_refs[0].metric_family_codes == (
        "catalog",
        "summary",
        "trajectory",
    )
