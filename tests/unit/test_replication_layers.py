# mypy: ignore-errors
"""V4-28 detached rows keep objective, owner, and analytical layers separate."""

from __future__ import annotations

import pytest

from analysis.replication_analysis import harvest_replication_analysis
from analysis.replication_rows import (
    ReplicationExecutionFact,
    ReplicationFacts,
    ReplicationLayer,
    ReplicationMeasurementFact,
    ReplicationReportFact,
)
from experiments.replication_publication import compose_replication_snapshot
from simulation.replication_codec import encode_replication_snapshot

pytestmark = pytest.mark.unit

RUN = "run-replication-layers"


def _execution() -> ReplicationExecutionFact:
    return ReplicationExecutionFact(
        execution_token="rpe-" + "a" * 32,
        result_root_token="rpt-" + "b" * 32,
        participant_token="rpp-" + "c" * 32,
        execution_tick=2,
        operator="apply_tool",
        process_token="craft",
        operand_a_token="rpen-" + "d" * 32,
        operand_b_token=None,
        outcome="success",
    )


def _report(*, outcome: str = "failure") -> ReplicationReportFact:
    return ReplicationReportFact(
        local_report_token="rplr-" + "e" * 32,
        origin_report_token="rpr-" + "f" * 32,
        participant_token="rpp-" + "c" * 32,
        performer_claim_token="rpart-" + "g" * 32,
        design_token="rpd-" + "h" * 32,
        attempt_token="rpa-" + "i" * 32,
        source_trial_token="rpt-" + "j" * 32,
        result_root_token="rpt-" + "k" * 32,
        report_tick=4,
        measurement=ReplicationMeasurementFact(
            outcome=outcome,
            resolution="outcome_class",
            uncertainty_kind="unreported",
            possible_outcomes=(),
            basis="communicated",
        ),
        declared_measurement_basis="own_observation",
        condition_snapshot=(),
        collaboration_token=None,
        delivery_token="rpdl-" + "l" * 32,
        provenance_kind="communicated",
        claim_digest="m" * 64,
    )


def test_each_row_type_carries_its_declared_layer() -> None:
    analysis = harvest_replication_analysis(
        ReplicationFacts(executions=(_execution(),), reports=(_report(),))
    )
    assert all(
        row.layer is ReplicationLayer.OWNER_SCOPED for row in analysis.reports
    )
    assert all(
        row.layer is ReplicationLayer.OBJECTIVE for row in analysis.executions
    )
    assert all(
        row.layer is ReplicationLayer.DETACHED_ANALYSIS
        for row in analysis.comparisons
    )


def test_results_keep_both_variants_under_their_own_record_types() -> None:
    snapshot = compose_replication_snapshot(
        harvest_replication_analysis(
            ReplicationFacts(executions=(_execution(),), reports=(_report(),))
        ),
        run_id=RUN,
        generated_from_tick=7,
    )
    record_types = {row["record_type"] for row in snapshot.results}
    assert record_types == {"execution", "report"}
    for row in snapshot.results:
        if row["record_type"] == "execution":
            assert row["layer"] == "objective"
            assert "measurement" not in row
        else:
            assert row["layer"] == "owner_scoped"
            assert "outcome" not in row


def test_equal_counts_with_different_content_keep_distinct_row_tokens() -> None:
    success = compose_replication_snapshot(
        harvest_replication_analysis(ReplicationFacts(reports=(_report(outcome="success"),))),
        run_id=RUN,
        generated_from_tick=7,
    )
    failure = compose_replication_snapshot(
        harvest_replication_analysis(ReplicationFacts(reports=(_report(outcome="failure"),))),
        run_id=RUN,
        generated_from_tick=7,
    )
    assert len(success.results) == len(failure.results) == 1
    assert success.results[0]["row_token"] != failure.results[0]["row_token"]


def test_published_bytes_never_carry_raw_agent_or_body_identifiers() -> None:
    snapshot = compose_replication_snapshot(
        harvest_replication_analysis(
            ReplicationFacts(executions=(_execution(),), reports=(_report(),))
        ),
        run_id=RUN,
        generated_from_tick=7,
    )
    material = encode_replication_snapshot(snapshot)
    for canary in (b"body-source", b"agent-source", b"agent-receiver"):
        assert canary not in material
