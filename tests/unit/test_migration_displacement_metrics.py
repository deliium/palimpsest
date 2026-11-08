# mypy: ignore-errors
"""Four detached migration-displacement metric documents."""

from __future__ import annotations

import pytest

from agents.cognition.migration_displacement import (
    MigrationCauseKind,
    MigrationCauseSource,
)
from analysis import migration_displacement_rows as rows_module
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.migration_displacement_metrics import (
    compute_migration_cause_evidence,
    compute_migration_cluster_cohesion,
    compute_migration_integration_outcome,
    compute_migration_wave_structure,
)
from analysis.migration_displacement_rows import (
    MigrationDisplacementHarvestRows,
    harvest_migration_displacement_rows,
)
from analysis.specifications import MetricFamilyId, metric_specification
from simulation.migration_displacement_export import (
    migration_displacement_owner_export,
)
from tests.unit.migration_displacement_analysis_helpers import (
    POLICY,
    evidence,
    movement,
    p,
)
from tests.unit.migration_displacement_helpers import OWNER, PEER, cause, ledger

pytestmark = pytest.mark.unit

KW = {"run_id": "run-1", "input_revision": "rev-1"}
FAMILIES = (
    MetricFamilyId.MIGRATION_WAVE_STRUCTURE,
    MetricFamilyId.MIGRATION_CAUSE_EVIDENCE,
    MetricFamilyId.MIGRATION_CLUSTER_COHESION,
    MetricFamilyId.MIGRATION_INTEGRATION_OUTCOME,
)


def _movements():
    return (
        movement("agent-1", "loc-a", "loc-b", 1),
        movement("agent-2", "loc-a", "loc-b", 2),
        movement("agent-3", "loc-a", "loc-b", 3),
        movement("agent-4", "loc-a", "loc-c", 50),
        movement("agent-5", "loc-a", "loc-c", 51),
    )


def _harvest(*, with_owner=True, with_movements=True):
    owner_rows = (
        migration_displacement_owner_export(
            [
                ledger(
                    owner=OWNER,
                    causes=(
                        cause(
                            MigrationCauseKind.ENVIRONMENTAL_HAZARD,
                            MigrationCauseSource.DIRECT_OBSERVATION,
                            tick=1,
                        ),
                    ),
                ),
                ledger(
                    owner=PEER,
                    causes=(
                        cause(
                            MigrationCauseKind.OPPORTUNITY,
                            MigrationCauseSource.TESTIMONY,
                            tick=2,
                            owner=PEER,
                        ),
                    ),
                ),
            ]
        )
        if with_owner
        else ()
    )
    return harvest_migration_displacement_rows(
        owner_rows,
        _movements() if with_movements else (),
        (
            evidence("agent-1", "loc-b", "resource_access", 2, 5, 9),
            evidence("agent-2", "loc-b", "relationships", 1, 4, 4),
        ),
        kinship_pairs=(tuple(sorted((p("agent-1"), p("agent-2")))),),
        policy=POLICY,
    )


def test_wave_structure_counts_and_ratios() -> None:
    document = compute_migration_wave_structure(_harvest(), **KW)
    values = document.values
    assert document.availability.value == "present"
    assert values["wave_count"] == 2
    assert values["participant_count"] == 5
    assert values["distinct_origin_count"] == 1
    assert values["distinct_destination_count"] == 2
    assert values["wave_participant_mean"] == 2.5
    assert values["wave_participant_max"] == 3
    assert values["route_length_counts"] == "2=2"
    assert values["wave_duration_ticks"] == 2
    assert values["return_count"] == 0 and values["onward_count"] == 0
    assert values["same_origin_share"] == 1.0
    assert values["same_destination_share"] == 0.6
    assert values["cluster_overlap_count"] == 2
    assert (
        values["coverage_complete"],
        values["coverage_partial"],
        values["coverage_missing"],
    ) == (2, 0, 0)
    assert set(values) == set(metric_specification(FAMILIES[0]).value_keys)


def test_cause_evidence_counts_and_coverage() -> None:
    document = compute_migration_cause_evidence(_harvest(), **KW)
    values = document.values
    assert values["cause_count:environmental_hazard"] == 1
    assert values["cause_count:opportunity"] == 1
    assert values["cause_count:conflict"] == 0
    # The owner export carries no cause source, so sources stay explicit unknown.
    assert values["source_count:unknown"] == 2
    assert values["owner_coverage_ratio"] == 0.4
    assert values["wave_with_cause_count"] == 1
    assert values["wave_without_cause_count"] == 1
    assert values["mixed_count"] == 1
    assert values["unknown_count"] == 1
    assert values["displacement_like_count"] == 0
    assert values["not_displacement_like_count"] == 0
    assert values["independent_cause_mean"] == 1.0
    assert values["contradicted_cause_count"] == 0
    assert values["same_root_suppressed_count"] == 0
    assert set(values) == set(metric_specification(FAMILIES[1]).value_keys)
    assert document.coverage.observed == 2 and document.coverage.expected == 5


def test_cluster_cohesion_counts_independent_support() -> None:
    document = compute_migration_cluster_cohesion(_harvest(), **KW)
    values = document.values
    assert values["cluster_count"] == 2
    assert values["cluster_size:2"] == 1 and values["cluster_size:3"] == 1
    assert values["cluster_size:4"] == 0
    assert values["co_movement_pair_count"] == 4
    assert values["kinship_supported_pair_count"] == 1
    assert values["organization_supported_pair_count"] == 0
    assert values["communication_supported_pair_count"] == 0
    assert values["relationship_supported_pair_count"] == 0
    assert values["independent_support_ratio"] == 0.5
    assert values["cluster_wave_overlap_count"] == 2
    assert values["unknown_cluster_count"] == 0
    assert values["coverage_complete"] == 2 and values["coverage_partial"] == 0
    assert set(values) == set(metric_specification(FAMILIES[2]).value_keys)


def test_integration_outcome_counts_and_censoring() -> None:
    document = compute_migration_integration_outcome(_harvest(), **KW)
    values = document.values
    assert values["outcome:settled"] == 2
    assert values["outcome:transient"] == 3
    assert values["outcome:returned"] == 0
    assert values["residence_ticks:32_plus"] == 3
    assert values["residence_ticks:1_to_3"] == 1
    assert values["residence_ticks:0"] == 1
    assert values["access_evidence_count"] == 2
    assert values["relationship_evidence_count"] == 1
    assert values["participation_evidence_count"] == 0
    assert values["conflict_evidence_count"] == 0
    assert values["censored_count"] == 2
    assert values["unknown_count"] == 0
    assert values["complete_coverage_count"] == 5
    assert values["partial_coverage_count"] == 0
    assert values["missing_coverage_count"] == 0
    assert set(values) == set(metric_specification(FAMILIES[3]).value_keys)


def test_empty_harvest_is_explicit_not_zero_cause() -> None:
    empty = MigrationDisplacementHarvestRows()
    for compute in (
        compute_migration_wave_structure,
        compute_migration_cause_evidence,
        compute_migration_cluster_cohesion,
        compute_migration_integration_outcome,
    ):
        document = compute(empty, **KW)
        assert document.availability.value == "unknown"
        assert document.values == {}
        assert document.coverage.observed == 0 and document.coverage.expected == 0
    # Movements without any owner export: causes are unknown, never zero.
    movements_only = _harvest(with_owner=False)
    assert movements_only.coverage == "missing"
    cause_document = compute_migration_cause_evidence(movements_only, **KW)
    assert cause_document.availability.value == "unknown"
    assert cause_document.values == {}
    wave_document = compute_migration_wave_structure(movements_only, **KW)
    assert wave_document.availability.value == "partial"
    assert wave_document.values["wave_count"] == 2
    # An owner export without movements: no waves, but causes are retained.
    owner_only = _harvest(with_movements=False)
    cause_document = compute_migration_cause_evidence(owner_only, **KW)
    assert cause_document.values["cause_count:opportunity"] == 1
    assert cause_document.values["owner_coverage_ratio"] is None
    assert (
        compute_migration_wave_structure(owner_only, **KW).availability.value
        == "unknown"
    )
    with pytest.raises(ValueError, match="migration_metrics: invalid_harvest"):
        compute_migration_wave_structure(object(), **KW)


def test_no_composite_or_refugee_value_key_exists() -> None:
    forbidden = ("score", "refugee", "forced", "wellbeing", "assimilation", "composite")
    harvest = _harvest()
    for family, compute in zip(
        FAMILIES,
        (
            compute_migration_wave_structure,
            compute_migration_cause_evidence,
            compute_migration_cluster_cohesion,
            compute_migration_integration_outcome,
        ),
        strict=True,
    ):
        spec = metric_specification(family)
        document = compute(harvest, **KW)
        for key in (*spec.value_keys, *document.values):
            assert not any(word in key for word in forbidden), key
        for value in document.values.values():
            if isinstance(value, float):
                assert 0.0 <= value <= 1000.0
            assert not isinstance(value, (tuple, list, dict))
    ratio_values = [
        v
        for family, compute in zip(
            FAMILIES,
            (
                compute_migration_wave_structure,
                compute_migration_cause_evidence,
                compute_migration_cluster_cohesion,
                compute_migration_integration_outcome,
            ),
            strict=True,
        )
        for v in compute(harvest, **KW).values.values()
        if isinstance(v, float)
    ]
    assert ratio_values
    assert all(round(v, 6) == v for v in ratio_values)


def test_collector_then_metric_service_does_not_double_harvest(monkeypatch) -> None:
    harvest = _harvest()

    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("raw owner rows were projected twice")

    monkeypatch.setattr(rows_module, "_owner_rows_to_subjective", explode)
    bundle = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-1",
            input_revision="rev-1",
            window_end=60,
            migration_displacement_rows=harvest,
        )
    )
    documents = {doc.metric_family: doc for doc in bundle.documents}
    for family in FAMILIES:
        assert family.value in documents
    assert documents["migration_wave_structure"].values["wave_count"] == 2
    absent = assemble_metric_documents(
        MetricComputationInputs(run_id="run-1", input_revision="rev-1", window_end=60)
    )
    assert not [d for d in absent.documents if d.metric_family.startswith("migration_")]


def test_raw_owner_rows_in_metric_service_are_harvested_once() -> None:
    owner_rows = migration_displacement_owner_export([ledger(causes=(cause(),))])
    bundle = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-1",
            input_revision="rev-1",
            window_end=60,
            migration_displacement_rows=owner_rows,
            migration_displacement_movement_rows=_movements(),
        )
    )
    documents = {doc.metric_family: doc for doc in bundle.documents}
    assert documents["migration_wave_structure"].values["wave_count"] == 2
    assert (
        documents["migration_cause_evidence"].values["cause_count:resource_scarcity"]
        == 1
    )
